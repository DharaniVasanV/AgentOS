"""
app/services/attendance_service.py

Purpose
-------
Records the bot's own join/leave time and duration for a meeting into
`meeting_attendance`. Note: this tracks the BOT's presence, not
per-human-participant attendance — reliably scraping every participant's
individual join/leave time from Meet/Zoom/Teams UIs is fragile and
platform-specific (see README limitations). Bot-level attendance is
the reliable, always-available signal; per-participant attendance is
listed there as a documented "not implemented" gap.

Responsibilities
----------------
- record_join(): call the moment browser.join_meeting() succeeds
- record_leave(): call once the meeting ends / recording stops
- Persists via crud.save_attendance

Dependencies
------------
app.db.crud
"""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.db import crud
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def record_attendance(
    session: AsyncSession,
    meeting_id: uuid.UUID,
    join_time: datetime,
    leave_time: datetime,
) -> None:
    await crud.save_attendance(
        session,
        meeting_id=meeting_id,
        participant=settings.BOT_DISPLAY_NAME,
        join_time=join_time,
        leave_time=leave_time,
        bot_joined=True,
    )
    logger.info(
        "Recorded bot attendance for meeting %s: %s -> %s",
        meeting_id, join_time.isoformat(), leave_time.isoformat(),
    )
