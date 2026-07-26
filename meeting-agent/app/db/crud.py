"""
app/db/crud.py

Purpose
-------
Repository pattern: every raw SQLAlchemy query in the whole project
lives in this one file. Services never build queries themselves —
they call a function here. This means if the teammate's schema shifts
(column renamed, table renamed) you fix it in exactly one place.

Responsibilities
----------------
- Read meetings that are due to be joined
- Update meeting status (the one write this service is allowed to make
  on the shared `meetings` table)
- Write audit logs / notifications
- Write transcripts, reports, action items, decisions, attendance

Dependencies
------------
SQLAlchemy async session, app.db.models
"""

import json
import uuid
from datetime import datetime, date, timedelta
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Meeting,
    AuditLog,
    Notification,
    MeetingUpdate,
    MeetingTranscript,
    MeetingReport,
    MeetingActionItem,
    MeetingDecision,
    MeetingAttendance,
)


# ----------------------------------------------------------------------
# Reads
# ----------------------------------------------------------------------

async def get_meetings_due(session: AsyncSession, join_before_minutes: int) -> Sequence[Meeting]:
    """Meetings scheduled for today, still 'scheduled', whose start_time
    is within `join_before_minutes` of right now (or already started but
    not yet marked in_progress — covers a missed poll cycle)."""
    now = datetime.now()
    today = date.today()
    window_end = (now + timedelta(minutes=join_before_minutes)).time()

    stmt = select(Meeting).where(
        Meeting.status == "scheduled",
        Meeting.meeting_date == today,
        Meeting.start_time <= window_end,
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_meeting(session: AsyncSession, meeting_id: uuid.UUID) -> Meeting | None:
    return await session.get(Meeting, meeting_id)


# ----------------------------------------------------------------------
# Meeting status transitions (the only writes allowed on `meetings`)
# ----------------------------------------------------------------------

async def set_meeting_status(session: AsyncSession, meeting_id: uuid.UUID, new_status: str) -> None:
    meeting = await session.get(Meeting, meeting_id)
    if meeting is None:
        return
    old_status = meeting.status
    meeting.status = new_status
    meeting.updated_at = datetime.utcnow()
    session.add(MeetingUpdate(meeting_id=meeting_id, old_status=old_status, new_status=new_status))
    await session.commit()


# ----------------------------------------------------------------------
# Audit / notifications
# ----------------------------------------------------------------------

async def add_audit_log(session: AsyncSession, meeting_id: uuid.UUID, action: str, details: str = "") -> None:
    session.add(AuditLog(meeting_id=meeting_id, action=action, details=details))
    await session.commit()


async def add_notification(session: AsyncSession, meeting_id: uuid.UUID, message: str, type_: str = "info") -> None:
    session.add(Notification(meeting_id=meeting_id, message=message, type=type_))
    await session.commit()


# ----------------------------------------------------------------------
# Writes: new tables
# ----------------------------------------------------------------------

async def save_transcript(session: AsyncSession, meeting_id: uuid.UUID, transcript: str, language: str | None) -> MeetingTranscript:
    row = MeetingTranscript(meeting_id=meeting_id, transcript=transcript, language=language)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def save_report(
    session: AsyncSession,
    meeting_id: uuid.UUID,
    summary: str,
    key_points: list[str],
    follow_up: list[str],
    sentiment: str,
) -> MeetingReport:
    row = MeetingReport(
        meeting_id=meeting_id,
        summary=summary,
        key_points=json.dumps(key_points),
        follow_up=json.dumps(follow_up),
        sentiment=sentiment,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def save_action_items(session: AsyncSession, meeting_id: uuid.UUID, items: list[dict]) -> list[MeetingActionItem]:
    rows = [
        MeetingActionItem(
            meeting_id=meeting_id,
            assigned_to=item.get("assigned_to"),
            task=item["task"],
            deadline=item.get("deadline"),
            status="open",
        )
        for item in items
    ]
    session.add_all(rows)
    await session.commit()
    return rows


async def save_decisions(session: AsyncSession, meeting_id: uuid.UUID, decisions: list[str]) -> list[MeetingDecision]:
    rows = [MeetingDecision(meeting_id=meeting_id, decision=d) for d in decisions]
    session.add_all(rows)
    await session.commit()
    return rows


async def save_attendance(
    session: AsyncSession,
    meeting_id: uuid.UUID,
    participant: str,
    join_time: datetime,
    leave_time: datetime | None,
    bot_joined: bool = True,
) -> MeetingAttendance:
    duration = int((leave_time - join_time).total_seconds()) if leave_time else None
    row = MeetingAttendance(
        meeting_id=meeting_id,
        participant=participant,
        join_time=join_time,
        leave_time=leave_time,
        duration_seconds=duration,
        bot_joined=bot_joined,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


# ----------------------------------------------------------------------
# Reads for the API layer
# ----------------------------------------------------------------------

async def get_transcript(session: AsyncSession, meeting_id: uuid.UUID) -> MeetingTranscript | None:
    stmt = select(MeetingTranscript).where(MeetingTranscript.meeting_id == meeting_id)
    return (await session.execute(stmt)).scalars().first()


async def get_report(session: AsyncSession, meeting_id: uuid.UUID) -> MeetingReport | None:
    stmt = select(MeetingReport).where(MeetingReport.meeting_id == meeting_id)
    return (await session.execute(stmt)).scalars().first()


async def get_action_items(session: AsyncSession, meeting_id: uuid.UUID) -> Sequence[MeetingActionItem]:
    stmt = select(MeetingActionItem).where(MeetingActionItem.meeting_id == meeting_id)
    return (await session.execute(stmt)).scalars().all()


async def get_decisions(session: AsyncSession, meeting_id: uuid.UUID) -> Sequence[MeetingDecision]:
    stmt = select(MeetingDecision).where(MeetingDecision.meeting_id == meeting_id)
    return (await session.execute(stmt)).scalars().all()
