"""
app/services/report_service.py

Purpose
-------
The orchestration/persistence layer that sits above summary_service and
extraction_service. Those two modules only talk to Groq and return
plain data; this module is the one that actually writes to
`meeting_reports`, `meeting_action_items`, and `meeting_decisions`. This
separation means summary_service/extraction_service stay pure and easy
to unit test (mock the HTTP call, assert on the dict), while all DB
side effects live in one predictable place.

Responsibilities
----------------
- Run summary_service.generate_summary and extraction_service.extract_items
  (concurrently, since they're independent LLM calls over the same transcript)
- Persist both results via crud.py
- Return everything the caller (meeting_joiner.py) needs for logging/notifications

Dependencies
------------
app.services.summary_service, app.services.extraction_service, app.db.crud
"""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.services import summary_service, extraction_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def build_and_save_report(session: AsyncSession, meeting_id: uuid.UUID, transcript: str) -> dict:
    logger.info("Generating summary + extraction for meeting %s", meeting_id)

    summary_result, extraction_result = await asyncio.gather(
        summary_service.generate_summary(transcript),
        extraction_service.extract_items(transcript),
    )

    report = await crud.save_report(
        session,
        meeting_id=meeting_id,
        summary=summary_result["summary"],
        key_points=summary_result["key_points"],
        follow_up=summary_result["follow_up"],
        sentiment=summary_result["sentiment"],
    )

    action_items = await crud.save_action_items(session, meeting_id, extraction_result["action_items"])
    decisions = await crud.save_decisions(session, meeting_id, extraction_result["decisions"])

    logger.info(
        "Meeting %s: saved report, %d action items, %d decisions",
        meeting_id, len(action_items), len(decisions),
    )

    return {
        "report": report,
        "action_items": action_items,
        "decisions": decisions,
    }
