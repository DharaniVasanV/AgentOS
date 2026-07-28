"""
app/services/meeting_joiner.py

Purpose
-------
The orchestrator for a single meeting, start to finish. This is the
"main workflow" module — everything else (browser, recorder, whisper,
summary, extraction, attendance) is a step this file calls in order.

Responsibilities
----------------
- Detect platform, flip status scheduled -> joining -> in_progress
- Join via browser.py, start recording via recorder.py
- Wait until the meeting's scheduled end (or the safety-cap duration,
  whichever comes first), then leave + stop recording
- Run the transcription -> summary/extraction -> attendance pipeline
- Flip status -> completed (or failed, with audit log + notification,
  on any unrecoverable error)

Flow
----
meeting_monitor.py -> handle_meeting(meeting)
    -> browser.join_meeting()
    -> recorder.start_recording()
    -> [wait for meeting end]
    -> recorder.stop_recording() + browser.leave_meeting()
    -> whisper_service.transcribe_and_store()
    -> report_service.build_and_save_report()
    -> attendance_service.record_attendance()
    -> crud.set_meeting_status("completed")

Dependencies
------------
app.services.{browser,recorder,whisper_service,report_service,attendance_service}
app.db.{crud,database}
"""

import asyncio
from datetime import datetime, date, timedelta

from app.config.settings import get_settings
from app.db import crud
from app.db.database import get_session
from app.db.models import Meeting
from app.services import browser, recorder, whisper_service, report_service, attendance_service
from app.utils.helpers import detect_platform
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _seconds_until_meeting_end(meeting: Meeting) -> int:
    """How long to keep recording, capped by MEETING_MAX_DURATION_MINUTES
    in case end_time is missing/wrong and we'd otherwise record forever."""
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
        await crud.add_audit_log(session, meeting.id, "join_attempt", f"platform={platform}")

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
            await crud.add_audit_log(session, meeting.id, "join_failed", f"platform={platform}")
            await crud.add_notification(
                session, meeting.id,
                f"Meeting Agent could not join '{meeting.title or meeting.id}' ({platform}).",
                type_="error",
            )
        return

    join_time = datetime.utcnow()
    async with get_session() as session:
        await crud.set_meeting_status(session, meeting.id, "in_progress")
        await crud.add_audit_log(session, meeting.id, "joined", f"platform={platform}")

    # Force-reroute ALL Chromium audio sink-inputs to meetingsink so ffmpeg can capture them.
    # This is belt-and-suspenders: even if Chromium defaulted to a different sink at launch,
    # this moves every active audio stream into our virtual capture sink.
    try:
        reroute = await asyncio.create_subprocess_exec(
            "bash", "-c",
            "pactl list short sink-inputs | awk '{print $1}' | xargs -I{} pactl move-sink-input {} meetingsink",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await reroute.wait()
        logger.info("Rerouted all PulseAudio sink-inputs to meetingsink")
    except Exception:
        logger.warning("Could not reroute PulseAudio sink-inputs (non-fatal)")

    audio_path, ffmpeg_process = await recorder.start_recording(meeting.id)

    wait_seconds = _seconds_until_meeting_end(meeting)
    logger.info("Meeting %s: recording for up to %s seconds, polling for early end...", meeting.id, wait_seconds)

    # Poll every 5 seconds to see if we're still in the meeting
    elapsed = 0
    poll_interval = 5
    while elapsed < wait_seconds:
        # Check if we were kicked or if host ended meeting for everyone
        if not await browser.is_meeting_active(page, platform):
            logger.info("Meeting %s ended early or bot was removed. Stopping recording.", meeting.id)
            break
            
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    await recorder.stop_recording(ffmpeg_process)
    await browser.leave_meeting(browser_handle)
    leave_time = datetime.utcnow()

    try:
        async with get_session() as session:
            transcript_row = await whisper_service.transcribe_and_store(session, meeting.id, audio_path)
            await report_service.build_and_save_report(session, meeting.id, transcript_row.transcript)
            await attendance_service.record_attendance(session, meeting.id, join_time, leave_time)

            await crud.set_meeting_status(session, meeting.id, "completed")
            await crud.add_audit_log(session, meeting.id, "completed", "transcript+report+attendance saved")
            await crud.add_notification(
                session, meeting.id,
                f"Meeting notes ready for '{meeting.title or meeting.id}'.",
                type_="success",
            )
    except Exception:
        logger.exception("Post-processing failed for meeting %s", meeting.id)
        async with get_session() as session:
            await crud.set_meeting_status(session, meeting.id, "failed")
            await crud.add_audit_log(session, meeting.id, "post_processing_failed", "")
            await crud.add_notification(
                session, meeting.id,
                f"Meeting Agent joined '{meeting.title or meeting.id}' but failed to generate notes.",
                type_="error",
            )
