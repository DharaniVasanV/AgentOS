"""
app/db/models.py

Single table ORM model for standalone Meeting Agent (`meetings` table).
Stores all meeting inputs (title, URL, platform, scheduled date/times)
and outputs (dialogue transcript, audio_path, join/leave times, duration, status).
"""

import uuid
from datetime import datetime, date, time
from sqlalchemy import String, Text, DateTime, Date, Time, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Inputs
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    organizer: Mapped[str] = mapped_column(String(255), nullable=True)
    meeting_url: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=True)  # 'google_meet' | 'zoom' | 'teams'
    meeting_date: Mapped[date] = mapped_column(Date, nullable=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=True)
    end_time: Mapped[time] = mapped_column(Time, nullable=True)
    passcode: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="scheduled")  # scheduled|joining|in_progress|completed|failed

    # Outputs
    transcript: Mapped[str] = mapped_column(Text, nullable=True)          # Dialogue Speech format (Speaker: text)
    transcript_language: Mapped[str] = mapped_column(String(20), default="en")
    audio_path: Mapped[str] = mapped_column(Text, nullable=True)          # Recorded audio file path
    join_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    leave_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    bot_joined: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
