import uuid
from typing import List, Optional
from datetime import datetime, date, timedelta, timezone as tz
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .models import (
    CalendarEventModel,
    CalendarReminderModel,
    GoogleCalendarConnectionModel,
    NotificationJobModel
)

def _format_reminder_label(mins: int) -> str:
    if mins <= 0:
        return "Now"
    if mins < 60:
        return f"{mins} mins before"
    if mins < 1440:
        hours = mins // 60
        return f"{hours} hr{'s' if hours > 1 else ''} before"
    days = mins // 1440
    return f"{days} day{'s' if days > 1 else ''} before"

class CalendarRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_event_by_id(self, event_id: str) -> Optional[CalendarEventModel]:
        return self.db.query(CalendarEventModel).filter(CalendarEventModel.id == event_id).first()

    def get_event_by_source(
        self, user_id: str, source_type: str, source_id: str, event_type: str
    ) -> Optional[CalendarEventModel]:
        return self.db.query(CalendarEventModel).filter(
            CalendarEventModel.user_id == user_id,
            CalendarEventModel.source_type == source_type,
            CalendarEventModel.source_id == source_id,
            CalendarEventModel.event_type == event_type
        ).first()

    def list_events(
        self, user_id: str = "user_1", status: Optional[str] = None, event_type: Optional[str] = None
    ) -> List[CalendarEventModel]:
        query = self.db.query(CalendarEventModel)
        if user_id:
            query = query.filter(
                or_(
                    CalendarEventModel.user_id == user_id,
                    CalendarEventModel.user_id == "user_1",
                    CalendarEventModel.user_id == "dharanivasan"
                )
            )
        if status:
            query = query.filter(CalendarEventModel.status == status)
        if event_type:
            query = query.filter(CalendarEventModel.event_type == event_type)
        return query.order_by(
            CalendarEventModel.start_datetime.asc().nullslast(),
            CalendarEventModel.deadline.asc().nullslast()
        ).all()

    def get_today_events(self, user_id: str = "user_1", reference_date: Optional[date] = None) -> List[CalendarEventModel]:
        if reference_date is None:
            reference_date = datetime.now().date()

        date_prefix = reference_date.strftime("%Y-%m-%d")
        all_events = self.list_events(user_id=user_id, status="ACTIVE")

        today_events = []
        for e in all_events:
            start_str = str(e.start_datetime) if e.start_datetime else ""
            dead_str = str(e.deadline) if e.deadline else ""
            if date_prefix in start_str or date_prefix in dead_str:
                today_events.append(e)

        return today_events

    def get_upcoming_events(self, user_id: str = "user_1", limit: int = 20) -> List[CalendarEventModel]:
        now = datetime.now(tz.utc)
        query = self.db.query(CalendarEventModel).filter(CalendarEventModel.status == "ACTIVE")
        if user_id:
            query = query.filter(
                or_(
                    CalendarEventModel.user_id == user_id,
                    CalendarEventModel.user_id == "user_1",
                    CalendarEventModel.user_id == "dharanivasan"
                )
            )
        events = query.all()
        upcoming = []
        for e in events:
            dt = e.start_datetime or e.deadline
            if dt:
                dt_aware = dt.replace(tzinfo=tz.utc) if getattr(dt, 'tzinfo', None) is None else dt
                if dt_aware >= now:
                    upcoming.append(e)
        return upcoming[:limit]

    def get_upcoming_deadlines(self, user_id: str = "user_1", limit: int = 20) -> List[CalendarEventModel]:
        now = datetime.now(tz.utc)
        query = self.db.query(CalendarEventModel).filter(
            CalendarEventModel.status == "ACTIVE",
            CalendarEventModel.deadline.isnot(None)
        )
        if user_id:
            query = query.filter(
                or_(
                    CalendarEventModel.user_id == user_id,
                    CalendarEventModel.user_id == "user_1",
                    CalendarEventModel.user_id == "dharanivasan"
                )
            )
        all_deadlines = query.all()
        upcoming = []
        for e in all_deadlines:
            d = e.deadline
            if d:
                d_aware = d.replace(tzinfo=tz.utc) if getattr(d, 'tzinfo', None) is None else d
                if d_aware >= now:
                    upcoming.append(e)
        upcoming.sort(key=lambda x: x.deadline)
        return upcoming[:limit]

    def create_event(self, event: CalendarEventModel, reminders: List[int] = None) -> CalendarEventModel:
        self.db.add(event)
        self.db.flush()

        target_raw = event.start_datetime or event.deadline
        if target_raw:
            if getattr(target_raw, 'tzinfo', None) is None:
                event_target_time = target_raw.replace(tzinfo=tz.utc)
            else:
                event_target_time = target_raw
        else:
            event_target_time = datetime.now(tz.utc)

        time_str = event_target_time.strftime("%b %d, %Y at %I:%M %p")

        # 1. Immediate Notification Job so Notification Agent alerts user RIGHT NOW on event creation
        instant_job = NotificationJobModel(
            id=uuid.uuid4(),
            calendar_event_id=uuid.UUID(str(event.id)) if event.id and len(str(event.id)) == 36 else None,
            user_id=event.user_id or "dharanivasan",
            title=f"Event Scheduled: {event.title}",
            description=f"Event '{event.title}' ({event.event_type}) has been scheduled for {time_str}. Priority: {event.priority or 'Medium'}.",
            category=event.event_type,
            priority=event.priority or "Medium",
            notification_time=datetime.now(tz.utc),
            channels=["Browser", "Dashboard", "Desktop", "Email"],
            sound="bell.mp3",
            action_buttons=["Join Meeting", "Open Calendar", "Dismiss"],
            action_url=event.external_url or event.google_event_link,
            status="Pending"
        )
        self.db.add(instant_job)

        # 2. Schedule future reminder jobs prior to deadline/event time
        if reminders:
            for mins in reminders:
                reminder = CalendarReminderModel(
                    calendar_event_id=event.id,
                    reminder_method="popup",
                    minutes_before=mins
                )
                self.db.add(reminder)

                notif_time = event_target_time - timedelta(minutes=mins)
                rel_label = _format_reminder_label(mins)

                if mins == 0:
                    title_str = f"Scheduled: {event.title}"
                    desc_str = f"Event '{event.title}' ({event.event_type}) is scheduled for {time_str}. Priority: {event.priority or 'Medium'}."
                else:
                    title_str = f"Upcoming Reminder ({rel_label}): {event.title}"
                    desc_str = f"Reminder for '{event.title}' ({event.event_type}) due on {time_str} ({rel_label}). Priority: {event.priority or 'Medium'}."

                job = NotificationJobModel(
                    id=uuid.uuid4(),
                    calendar_event_id=uuid.UUID(str(event.id)) if event.id and len(str(event.id)) == 36 else None,
                    user_id=event.user_id or "dharanivasan",
                    title=title_str,
                    description=event.description or desc_str,
                    category=event.event_type,
                    priority=event.priority or "Medium",
                    notification_time=notif_time,
                    channels=["Browser", "Dashboard", "Desktop", "Email"],
                    sound="bell.mp3",
                    action_buttons=["Join Meeting", "Open Calendar", "Dismiss"],
                    action_url=event.external_url or event.google_event_link,
                    status="Pending"
                )
                self.db.add(job)

        self.db.commit()
        self.db.refresh(event)
        return event

    def update_event(self, event: CalendarEventModel, reminders: List[int] = None) -> CalendarEventModel:
        event.updated_at = datetime.now(tz.utc)
        if reminders is not None:
            self.db.query(CalendarReminderModel).filter(
                CalendarReminderModel.calendar_event_id == event.id
            ).delete()

            target_raw = event.start_datetime or event.deadline
            if target_raw:
                if getattr(target_raw, 'tzinfo', None) is None:
                    event_target_time = target_raw.replace(tzinfo=tz.utc)
                else:
                    event_target_time = target_raw
            else:
                event_target_time = datetime.now(tz.utc)

            time_str = event_target_time.strftime("%b %d, %Y at %I:%M %p")

            # 1. Immediate notification for event update / change
            change_job = NotificationJobModel(
                id=uuid.uuid4(),
                calendar_event_id=uuid.UUID(str(event.id)) if event.id and len(str(event.id)) == 36 else None,
                user_id=event.user_id or "dharanivasan",
                title=f"Event Changed: {event.title}",
                description=f"Schedule / details updated for '{event.title}'. New time: {time_str}. Priority: {event.priority or 'Medium'}.",
                category=event.event_type,
                priority=event.priority or "Medium",
                notification_time=datetime.now(tz.utc),
                channels=["Browser", "Dashboard", "Desktop", "Email"],
                sound="bell.mp3",
                action_buttons=["Open Calendar", "Dismiss"],
                action_url=event.external_url or event.google_event_link,
                status="Pending"
            )
            self.db.add(change_job)

            # 2. Re-schedule reminder notifications
            for mins in reminders:
                reminder = CalendarReminderModel(
                    calendar_event_id=event.id,
                    reminder_method="popup",
                    minutes_before=mins
                )
                self.db.add(reminder)

                notif_time = event_target_time - timedelta(minutes=mins)
                rel_label = _format_reminder_label(mins)

                job = NotificationJobModel(
                    id=uuid.uuid4(),
                    calendar_event_id=uuid.UUID(str(event.id)) if event.id and len(str(event.id)) == 36 else None,
                    user_id=event.user_id or "dharanivasan",
                    title=f"Updated Reminder ({rel_label}): {event.title}",
                    description=f"Updated reminder for '{event.title}' scheduled for {time_str}. Priority: {event.priority or 'Medium'}.",
                    category=event.event_type,
                    priority=event.priority or "Medium",
                    notification_time=notif_time,
                    channels=["Browser", "Dashboard", "Desktop", "Email"],
                    sound="bell.mp3",
                    action_buttons=["Join Meeting", "Open Calendar", "Dismiss"],
                    action_url=event.external_url or event.google_event_link,
                    status="Pending"
                )
                self.db.add(job)

        self.db.commit()
        self.db.refresh(event)
        return event

    def delete_or_cancel_event(self, event_id: str) -> Optional[CalendarEventModel]:
        event = self.get_event_by_id(event_id)
        if event:
            event.status = "CANCELLED"
            event.updated_at = datetime.now(tz.utc)

            # Cancel associated pending notification jobs
            self.db.query(NotificationJobModel).filter(
                NotificationJobModel.calendar_event_id == event_id,
                NotificationJobModel.status == "Pending"
            ).update({"status": "Cancelled"})

            # Immediate cancellation notification job
            cancel_job = NotificationJobModel(
                id=uuid.uuid4(),
                calendar_event_id=uuid.UUID(str(event.id)) if event.id and len(str(event.id)) == 36 else None,
                user_id=event.user_id or "dharanivasan",
                title=f"Event Cancelled: {event.title}",
                description=f"The event '{event.title}' has been cancelled.",
                category=event.event_type,
                priority="HIGH",
                notification_time=datetime.now(tz.utc),
                channels=["Browser", "Dashboard", "Desktop", "Email"],
                sound="bell.mp3",
                action_buttons=["Open Calendar", "Dismiss"],
                action_url=event.external_url or event.google_event_link,
                status="Pending"
            )
            self.db.add(cancel_job)

            self.db.commit()
            self.db.refresh(event)
        return event

    def delete_all_events(self, user_id: str = "user_1") -> int:
        count = self.db.query(CalendarEventModel).filter(
            CalendarEventModel.user_id == user_id
        ).delete()
        self.db.commit()
        return count

    def delete_mock_events(self, user_id: str = "user_1") -> int:
        count = self.db.query(CalendarEventModel).filter(
            CalendarEventModel.user_id == user_id,
            CalendarEventModel.source_type.in_(["meeting_tasks", "applications"])
        ).delete()
        self.db.commit()
        return count

    def get_google_connection(self, user_id: str = "user_1") -> Optional[GoogleCalendarConnectionModel]:
        return self.db.query(GoogleCalendarConnectionModel).filter(
            GoogleCalendarConnectionModel.user_id == user_id
        ).first()

    def save_google_connection(
        self, user_id: str, email: str, access_token: str, refresh_token: str, expiry: datetime
    ) -> GoogleCalendarConnectionModel:
        conn = self.get_google_connection(user_id)
        if not conn:
            conn = GoogleCalendarConnectionModel(user_id=user_id)
            self.db.add(conn)
        conn.google_account_email = email
        conn.access_token_encrypted = access_token
        if refresh_token:
            conn.refresh_token_encrypted = refresh_token
        conn.token_expiry = expiry
        conn.updated_at = datetime.now(tz.utc)
        self.db.commit()
        self.db.refresh(conn)
        return conn
