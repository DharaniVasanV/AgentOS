"""
app/services/whisper_service.py

Purpose
-------
Transcribes recorded audio using Groq Whisper API (whisper-large-v3-turbo)
and persists the transcript into `meeting_transcripts` via crud.py.
"""

import os
import uuid
from groq import Groq
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.db import crud
from app.db.models import Meeting
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _get_groq_client() -> Groq | None:
    api_key = settings.GROQ_API_KEY
    if not api_key:
        logger.error("GROQ_API_KEY is missing from environment!")
        return None
    return Groq(api_key=api_key)


def _format_as_dialogue(client: Groq, raw_transcript: str, organizer: str = "", meeting_title: str = "") -> str:
    """Uses LLM to format raw Whisper transcript into speaker dialogue script with actual person names."""
    if not raw_transcript or len(raw_transcript.strip()) < 10:
        return raw_transcript

    meta_info = ""
    if organizer:
        meta_info += f"Meeting Organizer / Host Name: {organizer}\n"
    if meeting_title:
        meta_info += f"Meeting Title: {meeting_title}\n"

    try:
        prompt = (
            "You are an expert meeting transcript editor and name resolution assistant.\n"
            "Convert the following raw audio transcription into a clean, accurate dialogue script with actual person names.\n\n"
            f"{meta_info}"
            "CRITICAL INSTRUCTIONS FOR SPEAKER IDENTIFICATION:\n"
            "1. DO NOT use generic placeholders like 'Speaker 1', 'Speaker 2', 'Speaker A', or 'Speaker B'. You MUST assign actual person names or specific descriptive roles (e.g. 'Dharani Vasan', 'Mahesh', 'Interviewer', 'Recruiter', 'HR').\n"
            "2. Carefully analyze the context, greetings, introductions, salutations, and addressed names in the conversation:\n"
            "   - If a person says 'Hello Mr. Dhanivasan', the person being addressed is Dhanivasan/Dharani Vasan, and the person speaking is the HR / Interviewer / Organizer (or Mahesh).\n"
            "   - Match spoken turns to the correct individuals based on context.\n"
            "3. Format each spoken line strictly as 'Person Name: Dialogue text'\n"
            "   Example Output:\n"
            "   Recruiter: Hello Mr. Dhanivasan, we would like to inform you that you have been selected for Google...\n"
            "   Mahesh: The technical round will start on 13th July...\n"
            "4. Do NOT add any preamble, markdown formatting, or commentary. Output ONLY the clean speaker dialogue lines.\n\n"
            f"Raw Transcript:\n{raw_transcript}"
        )
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=3000,
        )
        if response.choices and response.choices[0].message.content:
            dialogue = response.choices[0].message.content.strip()
            logger.info("Transcript successfully formatted into named dialogue format.")
            return dialogue
    except Exception as e:
        logger.warning("Failed to format transcript into dialogue: %s", e)

    return raw_transcript


def reformat_transcript_text(raw_or_existing_transcript: str, organizer: str = "", meeting_title: str = "") -> str:
    """Utility to re-format any existing transcript using Groq LLM name resolution."""
    client = _get_groq_client()
    if not client:
        return raw_or_existing_transcript
    return _format_as_dialogue(client, raw_or_existing_transcript, organizer=organizer, meeting_title=meeting_title)


async def transcribe_and_store(
    session: AsyncSession,
    meeting_id: uuid.UUID,
    audio_path: str = "",
) -> str:
    transcript_text = ""
    language = "en"

    # Fetch meeting metadata for context
    meeting = await crud.get_meeting(session, meeting_id)
    organizer = meeting.organizer if meeting and meeting.organizer else ""
    meeting_title = meeting.title if meeting and meeting.title else ""

    if audio_path and os.path.exists(audio_path):
        client = _get_groq_client()
        if client:
            try:
                logger.info("Transcribing recorded meeting audio via Groq Whisper API (%s)...", audio_path)
                filename = os.path.basename(audio_path)
                with open(audio_path, "rb") as audio_file:
                    res = client.audio.transcriptions.create(
                        file=(filename, audio_file.read()),
                        model="whisper-large-v3-turbo",
                        response_format="text",
                        language="en",
                    )
                    raw_text = str(res).strip()
                    logger.info("Groq Whisper transcription successful (%d raw chars).", len(raw_text))

                    # Convert raw transcription into Dialogue Speech format with actual names
                    transcript_text = _format_as_dialogue(client, raw_text, organizer=organizer, meeting_title=meeting_title)
            except Exception as e:
                logger.warning("Groq Whisper transcription failed: %s", e)
    else:
        logger.warning("No audio file found at path: %s", audio_path)

    if not transcript_text:
        logger.warning("Empty or silent audio transcript returned for meeting %s", meeting_id)

    await crud.save_transcript(session, meeting_id, transcript_text, language)
    return transcript_text