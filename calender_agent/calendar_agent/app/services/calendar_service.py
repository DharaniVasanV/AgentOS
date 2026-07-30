import uuid
import logging
from typing import Optional, List
from datetime import datetime, timezone as tz
from sqlalchemy.orm import Session

from .reminder_service import ReminderService
from .google_calendar_service import GoogleCalendarService
from ..database.models import CalendarEventModel
from ..database.repository import CalendarRepository
from ..schemas.calendar import CalendarEventCreate, CalendarEventUpdate, CalendarStatus

logger = logging.getLogger(__name__)

class CalendarService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CalendarRepository(db)

    def create_manual_event(self, event_in: CalendarEventCreate) -> CalendarEventModel:
        # Determine reminders
        reminders = event_in.reminders
        if not reminders:
            reminders = ReminderService.get_default_reminders(event_in.event_type, event_in.priority)

        source_id = event_in.source_id or f"manual_{uuid.uuid4().hex[:8]}"

        # Google sync safe wrapper
        g_res = {}
        try:
            connection = self.repo.get_google_connection(event_in.user_id)
            g_service = GoogleCalendarService(connection)
            
            g_res = g_service.create_event({
                "title": event_in.title,
                "description": event_in.description,
                "start_datetime": event_in.start_datetime,
                "end_datetime": event_in.end_datetime,
                "deadline": event_in.deadline,
                "all_day": event_in.all_day,
                "timezone": event_in.timezone,
                "location": event_in.location,
                "external_url": event_in.external_url,
                "reminders": reminders
            })
        except Exception as e:
            logger.warning(f"Google Calendar sync skipped or failed ({e}). Using mock sync status.")
            g_res = {
                "google_event_id": f"g_evt_{uuid.uuid4().hex[:12]}",
                "google_calendar_id": "primary",
                "google_event_link": None,
                "sync_status": "MOCK_SYNCED"
            }

        db_event = CalendarEventModel(
            id=str(uuid.uuid4()),
            user_id=event_in.user_id or "user_1",
            source_type=event_in.source_type or "manual",
            source_id=source_id,
            event_type=event_in.event_type or "GENERAL_EVENT",
            title=event_in.title,
            description=event_in.description,
            start_datetime=event_in.start_datetime,
            end_datetime=event_in.end_datetime,
            deadline=event_in.deadline,
            all_day=event_in.all_day,
            timezone=event_in.timezone or "Asia/Kolkata",
            location=event_in.location,
            external_url=event_in.external_url,
            priority=event_in.priority or "Medium",
            status="ACTIVE",
            google_calendar_id=g_res.get("google_calendar_id"),
            google_event_id=g_res.get("google_event_id"),
            google_event_link=g_res.get("google_event_link"),
            sync_status=g_res.get("sync_status", "SYNCED"),
            synced_at=datetime.now(tz.utc)
        )

        return self.repo.create_event(db_event, reminders=reminders)

    def get_event(self, event_id: str) -> Optional[CalendarEventModel]:
        return self.repo.get_event_by_id(event_id)

    def list_events(self, user_id: str = "user_1", status: Optional[str] = None, event_type: Optional[str] = None):
        return self.repo.list_events(user_id=user_id, status=status, event_type=event_type)

    def get_today_events(self, user_id: str = "user_1"):
        return self.repo.get_today_events(user_id=user_id)

    def get_upcoming_events(self, user_id: str = "user_1"):
        return self.repo.get_upcoming_events(user_id=user_id)

    def get_upcoming_deadlines(self, user_id: str = "user_1"):
        return self.repo.get_upcoming_deadlines(user_id=user_id)

    def update_event(self, event_id: str, update_in: CalendarEventUpdate, user_id: str = "user_1") -> Optional[CalendarEventModel]:
        event = self.repo.get_event_by_id(event_id)
        if not event:
            return None

        # Update fields if provided
        for field in ["title", "description", "start_datetime", "end_datetime", "deadline", "all_day", "timezone", "location", "external_url", "priority", "status"]:
            val = getattr(update_in, field, None)
            if val is not None:
                setattr(event, field, val)

        # Sync update to Google
        try:
            connection = self.repo.get_google_connection(user_id)
            g_service = GoogleCalendarService(connection)
            g_res = g_service.update_event(event.google_event_id, {
                "title": event.title,
                "description": event.description,
                "start_datetime": event.start_datetime,
                "end_datetime": event.end_datetime,
                "deadline": event.deadline,
                "all_day": event.all_day,
                "timezone": event.timezone,
                "location": event.location,
                "external_url": event.external_url
            })
            event.google_event_link = g_res.get("google_event_link")
            event.sync_status = g_res.get("sync_status", event.sync_status)
            event.synced_at = datetime.now(tz.utc)
        except Exception as e:
            logger.warning(f"Google update sync error: {e}")

        reminders = ReminderService.get_default_reminders(event.event_type, event.priority)
        return self.repo.update_event(event, reminders=reminders)

    def cancel_event(self, event_id: str, user_id: str = "user_1") -> Optional[CalendarEventModel]:
        event = self.repo.get_event_by_id(event_id)
        if not event:
            return None

        # Google Sync Delete
        try:
            connection = self.repo.get_google_connection(user_id)
            g_service = GoogleCalendarService(connection)
            if event.google_event_id:
                g_service.delete_event(event.google_event_id)
        except Exception as e:
            logger.warning(f"Google delete sync error: {e}")

        return self.repo.delete_or_cancel_event(event_id)

    def get_status(self, user_id: str = "user_1") -> CalendarStatus:
        conn = self.repo.get_google_connection(user_id)
        all_events = self.repo.list_events(user_id=user_id)
        active_events = [e for e in all_events if e.status == "ACTIVE"]
        today_events = self.repo.get_today_events(user_id=user_id)
        upcoming_deadlines = self.repo.get_upcoming_deadlines(user_id=user_id)

        last_synced = None
        for e in all_events:
            if e.synced_at:
                if not last_synced or e.synced_at > last_synced:
                    last_synced = e.synced_at

        return CalendarStatus(
            google_connected=bool(conn and conn.access_token_encrypted),
            google_account_email=conn.google_account_email if conn else None,
            total_events=len(all_events),
            active_events=len(active_events),
            today_events_count=len(today_events),
            upcoming_deadlines_count=len(upcoming_deadlines),
            last_synced_at=last_synced,
            default_timezone="Asia/Kolkata"
        )
