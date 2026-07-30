"""
app/services/meeting_joiner.py

Purpose
-------
The orchestrator for a single meeting, start to finish. This is the
"main workflow" module — everything else (browser, recorder, whisper_service,
attendance) is a step this file calls in order.

Responsibilities
----------------
- Detect platform, flip status scheduled -> joining -> in_progress
- Join via browser.py & record audio via recorder.py (WASAPI loopback)
- Wait until the meeting's scheduled end (or early exit), then leave
- Transcribe audio via whisper_service.py and store raw transcript in DB
- Record attendance metadata
- Flip status -> completed (or failed)

Flow
----
meeting_monitor.py -> handle_meeting(meeting)
    -> browser.join_meeting()
    -> recorder.start_recording()
    -> [wait for meeting end]
    -> recorder.stop_recording()
    -> browser.leave_meeting()
    -> whisper_service.transcribe_and_store()
    -> attendance_service.record_attendance()
    -> crud.set_meeting_status("completed")

Dependencies
------------
app.services.{browser,recorder,whisper_service,attendance_service}
app.db.{crud,database}
"""

import asyncio
from datetime import datetime, date, timedelta, timezone

from app.config.settings import get_settings
from app.db import crud
from app.db.database import get_session
from app.db.models import Meeting
from app.services import browser, whisper_service, recorder
from app.utils.helpers import detect_platform
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _seconds_until_meeting_end(meeting: Meeting) -> int:
    """How long to keep the bot in the meeting, capped by
    MEETING_MAX_DURATION_MINUTES in case end_time is missing/wrong and
    we'd otherwise stay in the call forever."""
    cap_seconds = settings.MEETING_MAX_DURATION_MINUTES * 60
    if not meeting.end_time:
        return cap_seconds

    now = datetime.now()
    end_dt = datetime.combine(meeting.meeting_date or date.today(), meeting.end_time)
    remaining = (end_dt - now).total_seconds()
    if remaining <= 0:
        remaining = 60  # end_time already passed by the time we joined; grab at least a minute
    return int(min(remaining, cap_seconds))


async def handle_meeting(meeting_id) -> None:
    """Entry point called by meeting_monitor.py for each due meeting.
    Re-fetches the meeting fresh (rather than trusting the caller's copy)
    since time has passed since the scan."""
    async with get_session() as session:
        meeting = await crud.get_meeting(session, meeting_id)
        if meeting is None or meeting.status != "scheduled":
            return  # picked up by another cycle already, or cancelled

        platform = detect_platform(meeting.meeting_url, meeting.platform)
        await crud.set_meeting_status(session, meeting.id, "joining")

    try:
        success, browser_handle, page = await browser.join_meeting(
            meeting.meeting_url, platform, settings.BOT_DISPLAY_NAME
        )
    except Exception:
        logger.exception("Unhandled error joining meeting %s", meeting.id)
        success, browser_handle, page = False, None, None

    if not success:
        async with get_session() as session:
            await crud.set_meeting_status(session, meeting.id, "failed")
        return

    join_time = datetime.now()
    async with get_session() as session:
        await crud.set_meeting_status(session, meeting.id, "in_progress")

    wait_seconds = _seconds_until_meeting_end(meeting)
    logger.info("In-browser digital audio capture engine initialized successfully.")
    logger.info("Meeting %s: active and recording audio for up to %s seconds...", meeting.id, wait_seconds)

    # Start audio recorder subprocess (FFmpeg WASAPI)
    audio_path, proc = await recorder.start_recording(meeting.id, page=page)

    # Brief post-join stabilization delay
    await asyncio.sleep(5)

    # Poll every 5 seconds to see if we're still in the meeting
    elapsed = 5
    poll_interval = 5
    while elapsed < wait_seconds:
        # Guarantee microphone and camera stay strictly muted
        await browser.ensure_muted(page)

        # Check if host ended meeting or everyone left
        if not await browser.is_meeting_active(page, platform):
            logger.info("Meeting %s ended early or bot was removed.", meeting.id)
            break

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    # Stop audio recorder
    await recorder.stop_recording(proc, page=page)

    await browser.leave_meeting(browser_handle)
    leave_time = datetime.now()

    try:
        async with get_session() as session:
            transcript_text = await whisper_service.transcribe_and_store(
                session, meeting.id, audio_path=audio_path
            )
            await crud.save_meeting_output(
                session,
                meeting_id=meeting.id,
                audio_path=audio_path,
                transcript=transcript_text,
                join_time=join_time,
                leave_time=leave_time,
                bot_joined=True,
            )
            await crud.set_meeting_status(session, meeting.id, "completed")
            logger.info("Meeting %s completed. Output saved in meetings table (transcript: %d chars)", meeting.id, len(transcript_text))
    except Exception:
        logger.exception("Post-processing failed for meeting %s", meeting.id)
        async with get_session() as session:
            await crud.set_meeting_status(session, meeting.id, "failed")