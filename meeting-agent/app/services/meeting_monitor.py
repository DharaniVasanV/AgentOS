"""
app/services/meeting_monitor.py

Purpose
-------
The polling step. Every scheduler tick, this checks the `meetings`
table for anything due to be joined and kicks off meeting_joiner for
each one — concurrently, since two meetings could legitimately overlap.

Responsibilities
----------------
- Query crud.get_meetings_due()
- Fan out to meeting_joiner.handle_meeting() as independent asyncio
  tasks (one meeting failing must never block/crash the others)

Flow
----
scheduler.py -> check_and_dispatch() -> crud.get_meetings_due()
    -> asyncio.create_task(meeting_joiner.handle_meeting(meeting.id)) per meeting

Dependencies
------------
app.db.crud, app.db.database, app.services.meeting_joiner
"""

import asyncio

from app.config.settings import get_settings
from app.db import crud
from app.db.database import get_session
from app.services import meeting_joiner
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Meetings we've already dispatched this run, so a slow meeting_joiner
# task doesn't get re-triggered by the next poll before its status flips
# out of 'scheduled'. Cleared naturally once status changes in the DB.
_dispatched: set = set()


async def check_and_dispatch() -> None:
    async with get_session() as session:
        due_meetings = await crud.get_meetings_due(session, settings.JOIN_BEFORE_MINUTES)

    for meeting in due_meetings:
        if meeting.id in _dispatched:
            continue
        _dispatched.add(meeting.id)
        logger.info("Dispatching meeting %s ('%s') for joining", meeting.id, meeting.title)
        asyncio.create_task(_run_and_cleanup(meeting.id))


async def _run_and_cleanup(meeting_id) -> None:
    try:
        await meeting_joiner.handle_meeting(meeting_id)
    finally:
        _dispatched.discard(meeting_id)
