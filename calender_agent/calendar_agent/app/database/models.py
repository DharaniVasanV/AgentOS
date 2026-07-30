import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DateTime, ForeignKey, UniqueConstraint, Index, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .database import Base

def generate_uuid():
    return str(uuid.uuid4())

def utc_now():
    return datetime.now(timezone.utc)

class CalendarEventModel(Base):
    __tablename__ = "calendar_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=False, default="user_1")
    source_type = Column(String(50), nullable=False) # meeting_tasks, applications, manual
    source_id = Column(String(100), nullable=True)
    event_type = Column(String(50), nullable=False, default="GENERAL_EVENT") # MEETING, TASK_DEADLINE, APPLICATION_DEADLINE, HACKATHON, INTERNSHIP, CERTIFICATION, GENERAL_EVENT
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    start_datetime = Column(DateTime(timezone=True), nullable=True)
    end_datetime = Column(DateTime(timezone=True), nullable=True)
    deadline = Column(DateTime(timezone=True), nullable=True)
    all_day = Column(Boolean, default=False, nullable=False)
    timezone = Column(String(50), default="Asia/Kolkata", nullable=False)
    location = Column(String(255), nullable=True)
    external_url = Column(String(500), nullable=True)
    priority = Column(String(20), default=None, nullable=True) # LOW, MEDIUM, HIGH, URGENT or null
    status = Column(String(20), default="ACTIVE", nullable=False) # ACTIVE, COMPLETED, CANCELLED
    google_calendar_id = Column(String(255), nullable=True)
    google_event_id = Column(String(255), nullable=True)
    google_event_link = Column(String(500), nullable=True)
    sync_status = Column(String(50), default="PENDING", nullable=False) # PENDING, SYNCED, MOCK_SYNCED, ERROR
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    synced_at = Column(DateTime(timezone=True), nullable=True)

    reminders = relationship("CalendarReminderModel", back_populates="event", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('user_id', 'source_type', 'source_id', 'event_type', name='uq_user_source_event'),
        Index('idx_user_status_deadline', 'user_id', 'status', 'deadline'),
        Index('idx_user_status_start', 'user_id', 'status', 'start_datetime'),
    )

class CalendarReminderModel(Base):
    __tablename__ = "calendar_reminders"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    calendar_event_id = Column(String(36), ForeignKey("calendar_events.id", ondelete="CASCADE"), nullable=False)
    reminder_method = Column(String(50), default="popup", nullable=False)
    minutes_before = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    event = relationship("CalendarEventModel", back_populates="reminders")

class NotificationJobModel(Base):
    __tablename__ = "notification_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    calendar_event_id = Column(UUID(as_uuid=True), nullable=True)
    user_id = Column(String(100), nullable=False, default="dharanivasan")
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(Text, nullable=True)
    priority = Column(Text, nullable=False)
    notification_time = Column(DateTime(timezone=True), nullable=False)
    channels = Column(JSON, nullable=True)
    sound = Column(Text, nullable=True)
    action_buttons = Column(JSON, nullable=True)
    action_url = Column(Text, nullable=True)
    status = Column(Text, default="Pending")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

class GoogleCalendarConnectionModel(Base):
    __tablename__ = "google_calendar_connections"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), unique=True, nullable=False)
    google_account_email = Column(String(255), nullable=True)
    access_token_encrypted = Column(Text, nullable=True)
    refresh_token_encrypted = Column(Text, nullable=True)
    token_expiry = Column(DateTime(timezone=True), nullable=True)
    calendar_id = Column(String(255), default="primary", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
