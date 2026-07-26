"""
app/services/whisper_service.py

Purpose
-------
Turns a recorded audio file into text. Originally spec'd as "OpenAI
Whisper" — implemented here against GROQ's hosted Whisper endpoint
instead (`whisper-large-v3` via Groq's OpenAI-compatible
`/audio/transcriptions` route), so only GROQ_API_KEY is needed, not
a separate OpenAI key.

Responsibilities
----------------
- Upload the recorded audio file to Groq
- Return (transcript_text, detected_language)
- Persist the result into `meeting_transcripts` via crud.py

Flow
----
meeting_joiner.py -> transcribe_and_store(session, meeting_id, audio_path)
    -> Groq /audio/transcriptions
    -> crud.save_transcript(...)

Dependencies
------------
httpx (async HTTP client), app.config.settings, app.db.crud
"""

import httpx

from app.config.settings import get_settings
from app.db import crud
from app.db.models import MeetingTranscript
from app.utils.helpers import with_retries
from app.utils.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

logger = get_logger(__name__)
settings = get_settings()


@with_retries(max_retries=settings.MAX_RETRIES, backoff_seconds=settings.RETRY_BACKOFF_SECONDS)
async def _call_groq_transcription(audio_path: str) -> dict:
    url = f"{settings.GROQ_API_BASE}/audio/transcriptions"
    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}

    async with httpx.AsyncClient(timeout=180.0) as client:
        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.split("/")[-1], f, "audio/wav")}
            data = {
                "model": settings.GROQ_WHISPER_MODEL,
                "response_format": "verbose_json",  # gives us detected language back
            }
            response = await client.post(url, headers=headers, data=data, files=files)
        response.raise_for_status()
        return response.json()


async def transcribe_and_store(
    session: AsyncSession, meeting_id: uuid.UUID, audio_path: str
) -> MeetingTranscript:
    logger.info("Transcribing audio for meeting %s via Groq (%s)", meeting_id, settings.GROQ_WHISPER_MODEL)
    result = await _call_groq_transcription(audio_path)

    transcript_text = result.get("text", "").strip()
    language = result.get("language")

    if not transcript_text:
        logger.warning("Empty transcript returned for meeting %s", meeting_id)

    return await crud.save_transcript(session, meeting_id, transcript_text, language)
