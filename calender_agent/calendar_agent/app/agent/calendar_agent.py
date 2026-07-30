import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ..services.calendar_service import CalendarService
from ..services.sync_service import SyncService
from ..schemas.calendar import CalendarEventCreate, CalendarEventUpdate, SyncSummary, CalendarStatus

logger = logging.getLogger(__name__)

class CalendarAgent:
    """
    Standalone Calendar Agent for AgentOS.
    Encapsulates schedule management, input normalization, duplicate prevention,
    and Google Calendar synchronization.
    """
    def __init__(self, db: Session, user_id: str = "user_1"):
        self.db = db
        self.user_id = user_id
        self.calendar_service = CalendarService(db)
        self.sync_service = SyncService(db)

    def sync(self) -> SyncSummary:
        """
        Triggers full Calendar Agent synchronization workflow across meeting_tasks and applications.
        """
        logger.info(f"CalendarAgent starting synchronization for user_id={self.user_id}")
        return self.sync_service.run_sync(user_id=self.user_id)

    def create_event(self, event_data: CalendarEventCreate):
        return self.calendar_service.create_manual_event(event_data)

    def update_event(self, event_id: str, update_data: CalendarEventUpdate):
        return self.calendar_service.update_event(event_id, update_data, user_id=self.user_id)

    def cancel_event(self, event_id: str):
        return self.calendar_service.cancel_event(event_id, user_id=self.user_id)

    def get_today_schedule(self):
        return self.calendar_service.get_today_events(user_id=self.user_id)

    def get_upcoming_deadlines(self):
        return self.calendar_service.get_upcoming_deadlines(user_id=self.user_id)

    def schedule_with_gemini(self, user_input: Dict[str, Any]):
        from ..services.gemini_service import GeminiService
        gemini = GeminiService()
        intent = gemini.schedule_custom_event(user_input)

        event_create = CalendarEventCreate(
            user_id=self.user_id,
            source_type=intent.source_type,
            source_id=intent.source_id,
            event_type=intent.event_type,
            title=intent.title,
            description=intent.description,
            start_datetime=intent.start_datetime,
            end_datetime=intent.end_datetime,
            deadline=intent.deadline,
            all_day=intent.all_day,
            priority=intent.priority,
            location=intent.location,
            external_url=intent.meeting_url,
            reminders=intent.suggested_reminders
        )
        return self.calendar_service.create_manual_event(event_create)

    def analyze_manual_input(self, text: str):
        from ..services.gemini_service import GeminiService
        gemini = GeminiService()
        return gemini.analyze_manual_input(text)

    def clear_all_events(self) -> int:
        return self.calendar_service.repo.delete_all_events(user_id=self.user_id)


    def get_status(self) -> CalendarStatus:
        return self.calendar_service.get_status(user_id=self.user_id)

