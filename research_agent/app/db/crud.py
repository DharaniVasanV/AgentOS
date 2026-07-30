"""
app/db/crud.py

CRUD operations for Research Agent analyses.
"""

import uuid
from datetime import datetime
from typing import Sequence, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import ResearchAnalysis


async def create_analysis(
    session: AsyncSession,
    raw_content: str,
    structured_data: dict,
) -> ResearchAnalysis:
    record = ResearchAnalysis(
        raw_content=raw_content,
        content_type=structured_data.get("content_type", "Unknown"),
        title=structured_data.get("title", "Untitled Research"),
        summary=structured_data.get("summary", ""),
        structured_data=structured_data,
        sentiment=structured_data.get("sentiment", "Neutral"),
        confidence=float(structured_data.get("confidence", 1.0)),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def get_all_analyses(session: AsyncSession) -> Sequence[ResearchAnalysis]:
    stmt = select(ResearchAnalysis).order_by(ResearchAnalysis.created_at.desc())
    res = await session.execute(stmt)
    return res.scalars().all()


async def get_analysis(session: AsyncSession, analysis_id: uuid.UUID) -> Optional[ResearchAnalysis]:
    return await session.get(ResearchAnalysis, analysis_id)


async def delete_analysis(session: AsyncSession, analysis_id: uuid.UUID) -> bool:
    analysis = await session.get(ResearchAnalysis, analysis_id)
    if analysis:
        await session.delete(analysis)
        await session.commit()
        return True
    return False
