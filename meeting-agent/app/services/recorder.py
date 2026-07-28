"""
app/services/recorder.py

*** SECOND FILE MOST LIKELY TO NEED ENVIRONMENT-SPECIFIC ADJUSTMENT ***

Purpose
-------
Records the meeting's audio output to a file so whisper_service can
transcribe it. Playwright/Chromium has no built-in "record this tab's
audio" API, so the standard approach (used by most open-source meeting
bots) is:

  1. Route Chromium's audio output to a virtual PulseAudio sink instead
     of a real speaker (done once at container/OS level — see Dockerfile
     and README "Audio setup" section).
  2. Use ffmpeg to capture from that sink's `.monitor` source to a WAV
     file for the duration of the meeting.

This module only handles step 2 (spawning/stopping ffmpeg). Step 1 is
infrastructure setup, not application code — it's in the Dockerfile.

Responsibilities
----------------
- start_recording(meeting_id): spawn an ffmpeg subprocess capturing the
  virtual sink monitor to a WAV file, return the file path + process handle
- stop_recording(process): terminate ffmpeg cleanly (SIGTERM, not SIGKILL,
  so the WAV file header gets finalized properly)

Dependencies
------------
ffmpeg binary on PATH, a PulseAudio virtual sink named "meetingsink"
(see Dockerfile), Python stdlib subprocess/asyncio
"""

import asyncio
import os
import uuid
from pathlib import Path

from app.config.settings import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

_PULSE_MONITOR_SOURCE = "meetingsink.monitor"  # must match the sink created in the Dockerfile/entrypoint


def _recording_path(meeting_id: uuid.UUID) -> str:
    Path(settings.RECORDINGS_DIR).mkdir(parents=True, exist_ok=True)
    return os.path.join(settings.RECORDINGS_DIR, f"{meeting_id}.wav")


async def start_recording(meeting_id: uuid.UUID) -> tuple[str, asyncio.subprocess.Process]:
    """Starts an ffmpeg process capturing system audio for this meeting.
    Caller (meeting_joiner.py) is responsible for calling stop_recording
    once the meeting ends or the max-duration safety cap is hit."""
    output_path = _recording_path(meeting_id)
    log_path = output_path.replace(".wav", "_ffmpeg.log")
    logger.info("Starting audio recording for meeting %s -> %s", meeting_id, output_path)

    # Pre-flight: confirm PulseAudio sink is available
    check = await asyncio.create_subprocess_exec(
        "pactl", "list", "short", "sources",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await check.communicate()
    sources = stdout.decode()
    if _PULSE_MONITOR_SOURCE not in sources:
        logger.error("PulseAudio source '%s' NOT FOUND! Available: %s", _PULSE_MONITOR_SOURCE, sources)
    else:
        logger.info("PulseAudio source '%s' confirmed available.", _PULSE_MONITOR_SOURCE)

    log_file = open(log_path, "wb")
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-f", "pulse",
        "-i", _PULSE_MONITOR_SOURCE,
        "-ac", "1",
        "-ar", "16000",  # 16kHz mono is plenty for speech and keeps Whisper uploads small
        output_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=log_file,  # Write ffmpeg output to a log file for diagnosis
    )
    logger.info("ffmpeg PID=%s recording to %s (log: %s)", process.pid, output_path, log_path)
    return output_path, process


async def stop_recording(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return  # already exited
    logger.info("Stopping audio recording (pid=%s)", process.pid)
    process.terminate()  # SIGTERM: lets ffmpeg finalize the WAV header
    try:
        await asyncio.wait_for(process.wait(), timeout=10)
    except asyncio.TimeoutError:
        logger.warning("ffmpeg did not exit after SIGTERM, killing pid=%s", process.pid)
        process.kill()
        await process.wait()
