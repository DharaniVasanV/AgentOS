import os
import json
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone as tz
from sqlalchemy.orm import Session

from ..database.repository import CalendarRepository
from ..database.models import CalendarEventModel
from ..schemas.calendar import SyncSummary
from .gemini_service import GeminiService
from .date_service import DateService
from .reminder_service import ReminderService
from .google_calendar_service import GoogleCalendarService

logger = logging.getLogger(__name__)

MOCK_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "mock_data")

def _dt_equals(dt1: Any, dt2: Any) -> bool:
    if dt1 is None and dt2 is None:
        return True
    if dt1 is None or dt2 is None:
        return False
    if isinstance(dt1, str):
        dt1 = DateService.parse_datetime(dt1)
    if isinstance(dt2, str):
        dt2 = DateService.parse_datetime(dt2)
    if hasattr(dt1, "tzinfo") and dt1.tzinfo is not None:
        dt1 = dt1.astimezone(tz.utc).replace(tzinfo=None)
    if hasattr(dt2, "tzinfo") and dt2.tzinfo is not None:
        dt2 = dt2.astimezone(tz.utc).replace(tzinfo=None)
    return dt1 == dt2

class SyncService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CalendarRepository(db)
        self.gemini_service = GeminiService()

    def load_mock_data(self) -> Dict[str, List[Dict[str, Any]]]:
        possible_dirs = [
            MOCK_DATA_DIR,
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "mock_data"),
            "e:/meeting-agent/mock_data"
        ]

        meeting_tasks = []
        applications = []

        for d in possible_dirs:
            mt_path = os.path.join(d, "meeting_tasks.json")
            if not meeting_tasks and os.path.exists(mt_path):
                try:
                    with open(mt_path, "r", encoding="utf-8") as f:
                        meeting_tasks = json.load(f)
                except Exception as e:
                    logger.error(f"Error loading {mt_path}: {e}")

            app_path = os.path.join(d, "applications.json")
            if not applications and os.path.exists(app_path):
                try:
                    with open(app_path, "r", encoding="utf-8") as f:
                        applications = json.load(f)
                except Exception as e:
                    logger.error(f"Error loading {app_path}: {e}")

        # Fallback default data if empty
        if not meeting_tasks:
            meeting_tasks = [
                {
                    "id": "task_sync_101",
                    "title": "AgentOS Core Microservice Review",
                    "description": "Sync calendar events with notification service.",
                    "due_date": "2026-08-02T14:00:00Z",
                    "priority": "HIGH",
                    "category": "MEETING"
                }
            ]

        if not applications:
            applications = [
                {
                    "application_id": "app_sync_201",
                    "title": "Google Developer AI Competition",
                    "organization": "Google",
                    "registration_deadline": "2026-08-05T23:59:59Z",
                    "event_start_date": "2026-08-10T10:00:00Z",
                    "category": "HACKATHON",
                    "priority": "URGENT",
                    "description": "AI Hackathon Application Deadline."
                }
            ]

        return {
            "meeting_tasks": meeting_tasks,
            "applications": applications
        }

    def run_sync(self, user_id: str = "user_1") -> SyncSummary:
        """
        Executes full synchronization of meeting_tasks and applications.
        Processes each record independently for maximum fault tolerance.
        """
        summary = SyncSummary()
        sources = self.load_mock_data()

        connection = self.repo.get_google_connection(user_id)
        g_service = GoogleCalendarService(connection)

        # 1. Process meeting_tasks
        for task_rec in sources.get("meeting_tasks", []):
            summary.total_processed += 1
            try:
                self._process_single_source(
                    raw_record=task_rec,
                    source_type="meeting_tasks",
                    user_id=user_id,
                    g_service=g_service,
                    summary=summary
                )
            except Exception as e:
                logger.error(f"Error processing meeting_task {task_rec.get('id')}: {e}", exc_info=True)
                summary.failed_count += 1
                summary.details.append({"source": "meeting_tasks", "id": task_rec.get("id"), "error": str(e)})

        # 2. Process applications
        for app_rec in sources.get("applications", []):
            summary.total_processed += 1
            try:
                self._process_application_source(
                    raw_record=app_rec,
                    user_id=user_id,
                    g_service=g_service,
                    summary=summary
                )
            except Exception as e:
                logger.error(f"Error processing application {app_rec.get('application_id')}: {e}", exc_info=True)
                summary.failed_count += 1
                summary.details.append({"source": "applications", "id": app_rec.get("application_id"), "error": str(e)})

        return summary

    def _process_single_source(
        self,
        raw_record: Dict[str, Any],
        source_type: str,
        user_id: str,
        g_service: GoogleCalendarService,
        summary: SyncSummary
    ):
        intent = self.gemini_service.normalize_record(raw_record, source_type)
        
        # Date Validation
        start_dt = DateService.parse_datetime(intent.start_datetime)
        end_dt = DateService.parse_datetime(intent.end_datetime)
        deadline_dt = DateService.parse_datetime(intent.deadline)

        if not start_dt and not deadline_dt:
            logger.info(f"Skipping record {intent.source_id}: No valid start date or deadline.")
            summary.skipped_invalid_date += 1
            summary.details.append({
                "source": source_type,
                "id": intent.source_id,
                "title": intent.title,
                "action": "SKIPPED_NO_DATE"
            })
            return

        reminders = intent.suggested_reminders or ReminderService.get_default_reminders(intent.event_type, intent.priority)

        # Check existing DB event
        existing_event = self.repo.get_event_by_source(
            user_id=user_id,
            source_type=source_type,
            source_id=intent.source_id,
            event_type=intent.event_type
        )

        if existing_event:
            # Check if fields changed using timezone-agnostic comparison
            has_changed = (
                existing_event.title != intent.title or
                not _dt_equals(existing_event.start_datetime, start_dt) or
                not _dt_equals(existing_event.end_datetime, end_dt) or
                not _dt_equals(existing_event.deadline, deadline_dt) or
                (existing_event.description or "") != (intent.description or "") or
                existing_event.priority != intent.priority or
                (existing_event.location or "") != (intent.location or "") or
                (existing_event.external_url or "") != (intent.meeting_url or "")
            )

            if not has_changed:
                summary.unchanged_count += 1
                summary.details.append({
                    "source": source_type,
                    "id": intent.source_id,
                    "title": intent.title,
                    "action": "UNCHANGED"
                })
                return

            # Update existing event
            existing_event.title = intent.title
            existing_event.description = intent.description
            existing_event.start_datetime = start_dt
            existing_event.end_datetime = end_dt
            existing_event.deadline = deadline_dt
            existing_event.all_day = intent.all_day
            existing_event.priority = intent.priority
            existing_event.location = intent.location
            existing_event.external_url = intent.meeting_url

            if existing_event.google_event_id:
                g_res = g_service.update_event(existing_event.google_event_id, {
                    "title": intent.title,
                    "description": intent.description,
                    "start_datetime": start_dt,
                    "end_datetime": end_dt,
                    "deadline": deadline_dt,
                    "all_day": intent.all_day,
                    "location": intent.location,
                    "external_url": intent.meeting_url,
                    "reminders": reminders
                })
                existing_event.sync_status = g_res.get("sync_status", "SYNCED")

            existing_event.synced_at = datetime.now(tz.utc)
            self.repo.update_event(existing_event, reminders=reminders)
            summary.updated_count += 1
            summary.details.append({
                "source": source_type,
                "id": intent.source_id,
                "title": intent.title,
                "action": "UPDATED"
            })
        else:
            # Create NEW event
            g_res = g_service.create_event({
                "title": intent.title,
                "description": intent.description,
                "start_datetime": start_dt,
                "end_datetime": end_dt,
                "deadline": deadline_dt,
                "all_day": intent.all_day,
                "location": intent.location,
                "external_url": intent.meeting_url,
                "reminders": reminders
            })

            new_event = CalendarEventModel(
                user_id=user_id,
                source_type=source_type,
                source_id=intent.source_id,
                event_type=intent.event_type,
                title=intent.title,
                description=intent.description,
                start_datetime=start_dt,
                end_datetime=end_dt,
                deadline=deadline_dt,
                all_day=intent.all_day,
                location=intent.location,
                external_url=intent.meeting_url,
                priority=intent.priority,
                status="ACTIVE",
                google_calendar_id=g_res.get("google_calendar_id"),
                google_event_id=g_res.get("google_event_id"),
                google_event_link=g_res.get("google_event_link"),
                sync_status=g_res.get("sync_status", "SYNCED"),
                synced_at=datetime.now(tz.utc)
            )

            self.repo.create_event(new_event, reminders=reminders)
            summary.created_count += 1
            summary.google_synced_count += 1
            summary.details.append({
                "source": source_type,
                "id": intent.source_id,
                "title": intent.title,
                "action": "CREATED"
            })

    def _process_application_source(
        self,
        raw_record: Dict[str, Any],
        user_id: str,
        g_service: GoogleCalendarService,
        summary: SyncSummary
    ):
        app_id = str(raw_record.get("application_id") or "app_unknown")
        title = raw_record.get("title", "Application")
        reg_deadline_str = raw_record.get("registration_deadline")
        event_start_str = raw_record.get("event_start_date") or raw_record.get("event_date")
        event_end_str = raw_record.get("event_end_date")

        # Event 1: Registration Deadline Event (if deadline provided)
        if reg_deadline_str:
            deadline_record = {
                "id": f"{app_id}_deadline",
                "application_id": app_id,
                "title": f"{title} - Registration Deadline",
                "category": "APPLICATION_DEADLINE",
                "registration_deadline": reg_deadline_str,
                "event_start_date": None,
                "event_end_date": None,
                "description": f"Registration deadline for {title} ({raw_record.get('organization', '')})",
                "priority": raw_record.get("priority", "HIGH"),
                "registration_url": raw_record.get("registration_url"),
                "location": raw_record.get("location")
            }
            self._process_single_source(
                raw_record=deadline_record,
                source_type="applications",
                user_id=user_id,
                g_service=g_service,
                summary=summary
            )

        # Event 2: Actual Event Duration (if event dates provided)
        if event_start_str:
            category = (raw_record.get("category") or "GENERAL_EVENT").upper()
            event_record = {
                "id": f"{app_id}_event",
                "application_id": app_id,
                "title": title,
                "category": category,
                "registration_deadline": None,
                "event_start_date": event_start_str,
                "event_end_date": event_end_str,
                "description": raw_record.get("description") or f"Event participation for {title}",
                "priority": raw_record.get("priority", "HIGH"),
                "registration_url": raw_record.get("registration_url"),
                "location": raw_record.get("location")
            }
            self._process_single_source(
                raw_record=event_record,
                source_type="applications",
                user_id=user_id,
                g_service=g_service,
                summary=summary
            )
