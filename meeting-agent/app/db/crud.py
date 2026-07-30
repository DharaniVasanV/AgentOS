"""
app/db/crud.py

CRUD operations for standalone Meeting Agent operating on the `meetings` table.
"""

import uuid
from datetime import datetime, date, timezone, timedelta
from typing import Sequence
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Meeting


async def get_all_meetings(session: AsyncSession) -> Sequence[Meeting]:
    stmt = select(Meeting).order_by(Meeting.created_at.desc())
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_meeting(session: AsyncSession, meeting_id: uuid.UUID) -> Meeting | None:
    return await session.get(Meeting, meeting_id)


async def get_meetings_due(session: AsyncSession, join_before_minutes: int) -> Sequence[Meeting]:
    now = datetime.now()
    today = date.today()
    window_end = (now + timedelta(minutes=join_before_minutes)).time()

    stmt = select(Meeting).where(
        Meeting.status == "scheduled",
        (Meeting.meeting_date == None) | (Meeting.meeting_date <= today),
        Meeting.start_time <= window_end,
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def create_meeting(session: AsyncSession, meeting_data: dict) -> Meeting:
    m = Meeting(
        id=uuid.uuid4(),
        title=meeting_data.get("title", "Untitled Meeting"),
        organizer=meeting_data.get("organizer"),
        meeting_url=meeting_data.get("meeting_url") or meeting_data.get("meeting_link"),
        platform=meeting_data.get("platform"),
        meeting_date=meeting_data.get("meeting_date"),
        start_time=meeting_data.get("start_time"),
        end_time=meeting_data.get("end_time"),
        passcode=meeting_data.get("passcode"),
        status=meeting_data.get("status", "scheduled"),
    )
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return m


async def update_meeting(session: AsyncSession, meeting_id: uuid.UUID, data: dict) -> Meeting | None:
    m = await session.get(Meeting, meeting_id)
    if not m:
        return None
    for field in ["title", "organizer", "meeting_url", "platform", "meeting_date", "start_time", "end_time", "passcode", "status", "transcript", "audio_path", "join_time", "leave_time", "duration_seconds", "bot_joined"]:
        if field in data:
            setattr(m, field, data[field])
    m.updated_at = datetime.now()
    await session.commit()
    await session.refresh(m)
    return m


async def delete_meeting(session: AsyncSession, meeting_id: uuid.UUID) -> bool:
    m = await session.get(Meeting, meeting_id)
    if not m:
        return False
    await session.delete(m)
    await session.commit()
    return True


async def set_meeting_status(session: AsyncSession, meeting_id: uuid.UUID, new_status: str) -> None:
    m = await session.get(Meeting, meeting_id)
    if m:
        m.status = new_status
        m.updated_at = datetime.now()
        await session.commit()


async def save_transcript(session: AsyncSession, meeting_id: uuid.UUID, transcript: str, language: str = "en") -> Meeting | None:
    m = await session.get(Meeting, meeting_id)
    if m:
        m.transcript = transcript
        m.transcript_language = language
        m.updated_at = datetime.now()
        await session.commit()
        await session.refresh(m)
    return m


async def save_meeting_output(
    session: AsyncSession,
    meeting_id: uuid.UUID,
    audio_path: str = "",
    transcript: str = "",
    join_time: datetime | None = None,
    leave_time: datetime | None = None,
    bot_joined: bool = True,
) -> Meeting | None:
    m = await session.get(Meeting, meeting_id)
    if m:
        m.audio_path = audio_path
        m.transcript = transcript
        if join_time is not None:
            m.join_time = join_time
        if leave_time is not None:
            m.leave_time = leave_time
        if join_time and leave_time:
            m.duration_seconds = int((leave_time - join_time).total_seconds())
        m.bot_joined = bot_joined
        m.updated_at = datetime.now()
        await session.commit()
        await session.refresh(m)
    return m
