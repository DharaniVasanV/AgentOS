"""
app/services/recorder.py

Purpose
-------
Records meeting audio via Windows WASAPI loopback using pyaudiowpatch.
Captures ALL audio currently playing on the system's default output device
(speakers or headphones), which includes Google Meet participant voices.
This is 100% reliable regardless of WebRTC internals or browser settings —
if you can hear it, it gets recorded.
"""

import asyncio
import os
import subprocess
import threading
import uuid
import wave
from pathlib import Path
from typing import Any

try:
    import imageio_ffmpeg
    _FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    _FFMPEG_EXE = None

try:
    import pyaudiowpatch as pyaudio
    _PYAUDIO_OK = True
except ImportError:
    _PYAUDIO_OK = False

from app.config.settings import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Kept for browser.py import compatibility (injected as init script for context)
_INIT_WEBAUDIO_CAPTURE_JS = """
(function() {
    // Placeholder — actual capture is done via WASAPI loopback in Python
    window.__recLoopbackMode = true;
})();
"""


def _recording_path(meeting_id: uuid.UUID) -> str:
    Path(settings.RECORDINGS_DIR).mkdir(parents=True, exist_ok=True)
    return os.path.join(settings.RECORDINGS_DIR, f"{meeting_id}.wav")


def _get_loopback_device() -> dict | None:
    """Find the WASAPI loopback device matching the default output (speakers/headphones)."""
    if not _PYAUDIO_OK:
        return None
    try:
        p = pyaudio.PyAudio()
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_out = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        loopback = None
        for lb in p.get_loopback_device_info_generator():
            if default_out["name"] in lb["name"]:
                loopback = lb
                break
        if loopback is None:
            # Fallback: take first available loopback
            for lb in p.get_loopback_device_info_generator():
                loopback = lb
                break
        p.terminate()
        if loopback:
            logger.info("WASAPI loopback device: '%s' (index %s)", loopback["name"], loopback["index"])
        else:
            logger.warning("No WASAPI loopback device found.")
        return loopback
    except Exception as e:
        logger.warning("Could not enumerate WASAPI loopback devices: %s", e)
        return None


class WASAPILoopbackRecorder:
    """Records system audio output via Windows WASAPI loopback."""

    def __init__(self, meeting_id: uuid.UUID):
        self.meeting_id = meeting_id
        self.filepath = _recording_path(meeting_id)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._loopback = _get_loopback_device()

    def _record_loop(self):
        if not _PYAUDIO_OK or not self._loopback:
            logger.warning("WASAPI loopback not available — no audio will be recorded.")
            return

        p = pyaudio.PyAudio()
        channels = int(self._loopback["maxInputChannels"])
        rate = int(self._loopback["defaultSampleRate"])
        chunk = 512

        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                frames_per_buffer=chunk,
                input=True,
                input_device_index=int(self._loopback["index"]),
            )
            logger.info(
                "WASAPI loopback recording started: device='%s' rate=%d ch=%d",
                self._loopback["name"], rate, channels,
            )
        except Exception as e:
            logger.warning("Failed to open WASAPI loopback stream: %s", e)
            p.terminate()
            return

        frames = []
        try:
            while not self._stop_event.is_set():
                try:
                    data = stream.read(chunk, exception_on_overflow=False)
                    frames.append(data)
                except Exception:
                    break
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

        # Write WAV file
        try:
            with wave.open(self.filepath, "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)  # paInt16 = 2 bytes
                wf.setframerate(rate)
                wf.writeframes(b"".join(frames))
            size = os.path.getsize(self.filepath)
            duration_s = len(frames) * chunk / rate
            logger.info(
                "WASAPI loopback recording saved: %s (%d bytes, %.1fs)",
                self.filepath, size, duration_s,
            )
        except Exception as e:
            logger.warning("Failed to write WAV file: %s", e)

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()
        logger.info("WASAPI loopback recorder thread started for meeting %s", self.meeting_id)

    def stop(self) -> str:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("WASAPI loopback recorder stopped.")
        return self.filepath


async def start_recording(meeting_id: uuid.UUID, page: Any = None) -> tuple[str, Any]:
    recorder = WASAPILoopbackRecorder(meeting_id)
    recorder.start()
    return (recorder.filepath, recorder)


async def stop_recording(process: Any = None, page: Any = None) -> None:
    if process and isinstance(process, WASAPILoopbackRecorder):
        await asyncio.get_event_loop().run_in_executor(None, process.stop)
