"""
app/db/models.py

Purpose
-------
ORM models. Split into two clearly-labeled groups:

1. EXISTING TABLES — owned by the email/meeting-extraction pipeline
   your teammate already built. We only ever SELECT from these (never
   INSERT/UPDATE/DELETE except the one allowed field: meetings.status,
   which is our explicit job to update). Column lists here are a
   best-effort mapping based on the fields you described — if your
   teammate's actual schema has different column names/types, adjust
   these classes to match. Do NOT run migrations against these tables;
   they're mapped `extend_existing=True` purely for read access.

2. NEW TABLES — owned by this Meeting Agent service. These get created
   via the Alembic migration in migrations/versions/.

Dependencies
------------
SQLAlchemy 2.0 ORM
"""

import uuid
from datetime import datetime, date, time

from sqlalchemy import String, Text, DateTime, Date, Time, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


# ======================================================================
# EXISTING TABLES (read-only from this service's perspective)
# ======================================================================

class Meeting(Base):
    """Maps to the existing `meetings` table populated by the email pipeline.

    We READ from this table to find meetings to join, and we are the
    ONLY service allowed to WRITE to `status` / `updated_at` on it —
    everything else (url, date, times, platform, id, passcode, title)
    is owned upstream.
    """
    __tablename__ = "meetings"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    meeting_url: Mapped[str] = mapped_column(Text, nullable=True)
    meeting_date: Mapped[date] = mapped_column(Date, nullable=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=True)
    end_time: Mapped[time] = mapped_column(Time, nullable=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=True)  # 'google_meet' | 'zoom' | 'teams'
    meeting_id: Mapped[str] = mapped_column(String(255), nullable=True)
    passcode: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=True)  # scheduled|joining|in_progress|completed|failed
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    """Maps to the existing `audit_logs` table. We only INSERT rows here."""
    __tablename__ = "audit_logs"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(255), nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Notification(Base):
    """Maps to the existing `notifications` table. We only INSERT rows here."""
    __tablename__ = "notifications"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MeetingUpdate(Base):
    """Maps to the existing `meeting_updates` table — an append-only status-change log."""
    __tablename__ = "meeting_updates"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    old_status: Mapped[str] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ======================================================================
# NEW TABLES (owned by this Meeting Agent service — see migrations/)
# ======================================================================

class MeetingTranscript(Base):
    __tablename__ = "meeting_transcripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=False)
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MeetingReport(Base):
    __tablename__ = "meeting_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    key_points: Mapped[str] = mapped_column(Text, nullable=True)   # JSON-encoded list[str]
    follow_up: Mapped[str] = mapped_column(Text, nullable=True)    # JSON-encoded list[str]
    sentiment: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MeetingActionItem(Base):
    __tablename__ = "meeting_action_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=False)
    assigned_to: Mapped[str] = mapped_column(String(255), nullable=True)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    deadline: Mapped[str] = mapped_column(String(100), nullable=True)  # free text; extraction isn't always a clean date
    status: Mapped[str] = mapped_column(String(50), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MeetingDecision(Base):
    __tablename__ = "meeting_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MeetingAttendance(Base):
    __tablename__ = "meeting_attendance"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=False)
    participant: Mapped[str] = mapped_column(String(255), nullable=True)
    join_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    leave_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    bot_joined: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
