"""
app/db/models.py

SQLAlchemy ORM models for Notification Agent database tables.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON, ForeignKey

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=True)
    email = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(100), unique=True, nullable=False, index=True)
    channels = Column(JSON, default=["Dashboard", "Browser", "Email"])
    sound_type = Column(String(100), default="Bell")
    custom_sound_name = Column(String(200), nullable=True)
    volume = Column(Integer, default=80)
    reminder_frequency = Column(String(100), default="Auto")
    quiet_hours_enabled = Column(Boolean, default=False)
    quiet_hours_start = Column(String(20), default="22:00")
    quiet_hours_end = Column(String(20), default="07:00")
    dnd_enabled = Column(Boolean, default=False)
    emergency_override = Column(Boolean, default=True)
    default_snooze_duration = Column(Integer, default=15)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class NotificationSound(Base):
    __tablename__ = "notification_sounds"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(100), nullable=False)
    sound_name = Column(String(200), nullable=False)
    file_path = Column(String(500), nullable=False)
    sound_type = Column(String(50), default="Custom")  # Custom / System
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False)
    type = Column(String(100), nullable=False)
    priority = Column(String(50), nullable=False)
    title_template = Column(String(300), nullable=False)
    description_template = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class NotificationJob(Base):
    __tablename__ = "notification_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    calendar_event_id = Column(String(36), nullable=True)
    user_id = Column(String(100), nullable=False, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(Text, nullable=True)
    priority = Column(Text, nullable=False)
    notification_time = Column(DateTime(timezone=True), nullable=False, index=True)
    channels = Column(JSON, nullable=True)
    sound = Column(Text, nullable=True)
    action_buttons = Column(JSON, nullable=True)
    action_url = Column(Text, nullable=True)
    status = Column(Text, default="Pending", index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(100), nullable=False, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=False)
    type = Column(String(100), nullable=False)
    priority = Column(String(50), nullable=False)
    channels = Column(JSON, nullable=False)
    sound = Column(JSON, nullable=False)
    actions = Column(JSON, nullable=False)
    scheduled_time = Column(String(100), nullable=True)
    repeat_interval = Column(String(100), nullable=True)
    delivery_status = Column(String(50), default="Scheduled", index=True)
    is_duplicate = Column(Boolean, default=False)
    action_url = Column(String(500), nullable=True)
    event_date = Column(String(50), nullable=True)
    event_time = Column(String(50), nullable=True)
    reminder_time = Column(String(50), nullable=True)
    deadline = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class NotificationHistory(Base):
    __tablename__ = "notification_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    notification_id = Column(String(36), nullable=False)
    calendar_event_id = Column(String(36), nullable=True)
    user_id = Column(String(100), nullable=False)
    type = Column(String(100), nullable=False)
    priority = Column(String(50), nullable=False)
    channels_used = Column(JSON, nullable=False)
    sound_used = Column(String(100), nullable=True)
    scheduled_time = Column(String(100), nullable=True)
    delivery_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    read_time = Column(DateTime(timezone=True), nullable=True)
    dismiss_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), default="Delivered")


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    notification_id = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
