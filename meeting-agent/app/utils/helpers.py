"""
app/utils/helpers.py

Purpose
-------
Small stateless helpers used by more than one service. Nothing here
touches the DB or any external API — pure functions only.

Responsibilities
----------------
- detect_platform: infer google_meet/zoom/teams from a URL, falling
  back to the DB's `platform` column if the URL is ambiguous.
- safe_json_loads: parse LLM output defensively (LLMs occasionally wrap
  JSON in markdown fences or add trailing commentary).
- with_retries: minimal async retry decorator so we don't need an
  extra dependency just for retry/backoff.

Dependencies
------------
Python stdlib + asyncio only.
"""

import asyncio
import functools
import json
import re
from typing import Awaitable, Callable, TypeVar

from app.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def detect_platform(meeting_url: str, fallback: str | None = None) -> str:
    url = (meeting_url or "").lower()
    if "meet.google.com" in url:
        return "google_meet"
    if "zoom.us" in url:
        return "zoom"
    if "teams.microsoft.com" in url or "teams.live.com" in url:
        return "teams"
    return (fallback or "unknown").lower()


def safe_json_loads(raw_text: str) -> dict:
    """LLMs sometimes wrap JSON in ```json fences or add stray text.
    Strip that before parsing; raise a clear error if it's still not JSON."""
    text = raw_text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    # Grab the outermost {...} block in case there's leading/trailing prose
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def with_retries(max_retries: int = 3, backoff_seconds: int = 5):
    """Async retry decorator with linear backoff. Logs each failed attempt."""

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs) -> T:
            last_exc: Exception | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    return await fn(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001 - intentionally broad, we log + rethrow
                    last_exc = exc
                    logger.warning(
                        "Attempt %s/%s failed for %s: %s", attempt, max_retries, fn.__name__, exc
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(backoff_seconds * attempt)
            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator
