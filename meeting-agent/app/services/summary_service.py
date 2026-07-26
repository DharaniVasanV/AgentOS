"""
app/services/summary_service.py

Purpose
-------
Turns a transcript into a structured summary (summary text, key points,
follow-ups, sentiment). Originally spec'd as "OpenAI GPT" — implemented
here against Groq's OpenAI-compatible chat completions endpoint instead.

Responsibilities
----------------
- Load the reusable prompt template from app/prompts/summary_prompt.txt
- Call Groq's /chat/completions
- Parse the JSON response defensively
- Return a plain dict — persistence to `meeting_reports` happens in
  report_service.py, not here, so this module is pure "call the LLM".

Dependencies
------------
httpx, app.config.settings, app.utils.helpers.safe_json_loads
"""

from pathlib import Path

import httpx

from app.config.settings import get_settings
from app.utils.helpers import safe_json_loads, with_retries
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "summary_prompt.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text()


@with_retries(max_retries=settings.MAX_RETRIES, backoff_seconds=settings.RETRY_BACKOFF_SECONDS)
async def _call_groq_chat(prompt: str) -> str:
    url = f"{settings.GROQ_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.GROQ_CHAT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 1500,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]


async def generate_summary(transcript: str) -> dict:
    """Returns {"summary": str, "key_points": list[str], "follow_up": list[str], "sentiment": str}."""
    if not transcript.strip():
        logger.warning("Empty transcript passed to generate_summary; returning placeholder")
        return {
            "summary": "No transcript content was available to summarize.",
            "key_points": [],
            "follow_up": [],
            "sentiment": "neutral",
        }

    prompt = _PROMPT_TEMPLATE.format(transcript=transcript)
    raw = await _call_groq_chat(prompt)

    try:
        parsed = safe_json_loads(raw)
    except Exception:
        logger.exception("Failed to parse Groq summary response as JSON: %s", raw[:500])
        parsed = {
            "summary": raw.strip()[:2000],
            "key_points": [],
            "follow_up": [],
            "sentiment": "neutral",
        }

    return {
        "summary": parsed.get("summary", ""),
        "key_points": parsed.get("key_points", []) or [],
        "follow_up": parsed.get("follow_up", []) or [],
        "sentiment": parsed.get("sentiment", "neutral") or "neutral",
    }
