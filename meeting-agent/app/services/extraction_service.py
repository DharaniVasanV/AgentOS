"""
app/services/extraction_service.py

Purpose
-------
Extracts structured action items and decisions from a transcript.
Originally spec'd as a second GPT pass — implemented here as a second
Groq call, kept in its own module (separate from summary_service) so
each prompt/response stays focused and easy to iterate on independently.

Responsibilities
----------------
- Load app/prompts/extraction_prompt.txt
- Call Groq's /chat/completions
- Parse + validate the JSON response
- Return plain dicts/lists — persistence happens in report_service.py

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

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "extraction_prompt.txt"
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
        "temperature": 0.1,
        "max_tokens": 1500,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]


async def extract_items(transcript: str) -> dict:
    """Returns {"action_items": [{"assigned_to","task","deadline"}, ...], "decisions": [str, ...]}."""
    if not transcript.strip():
        return {"action_items": [], "decisions": []}

    prompt = _PROMPT_TEMPLATE.format(transcript=transcript)
    raw = await _call_groq_chat(prompt)

    try:
        parsed = safe_json_loads(raw)
    except Exception:
        logger.exception("Failed to parse Groq extraction response as JSON: %s", raw[:500])
        return {"action_items": [], "decisions": []}

    action_items = [
        item for item in parsed.get("action_items", []) or []
        if isinstance(item, dict) and item.get("task")
    ]
    decisions = [d for d in parsed.get("decisions", []) or [] if isinstance(d, str) and d.strip()]

    return {"action_items": action_items, "decisions": decisions}
