"""
app/db/crud.py

CRUD operations for Career Agent analyses.
"""

import uuid
from datetime import datetime
from typing import Sequence, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import CareerAnalysis


async def create_career_analysis(
    session: AsyncSession,
    raw_content: str,
    structured_data: dict,
) -> CareerAnalysis:
    profile = structured_data.get("profile", {}) or {}
    ats = structured_data.get("ats", {}) or {}

    record = CareerAnalysis(
        raw_content=raw_content,
        input_type=structured_data.get("input_type", "Profile"),
        user_name=profile.get("name", "Candidate"),
        career_summary=structured_data.get("career_summary", ""),
        ats_score=int(ats.get("score", 0)) if isinstance(ats.get("score"), (int, float)) else 0,
        employability_score=int(structured_data.get("employability_score", 0)) if isinstance(structured_data.get("employability_score"), (int, float)) else 0,
        structured_data=structured_data,
        confidence=float(structured_data.get("confidence", 1.0)),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def get_all_career_analyses(session: AsyncSession) -> Sequence[CareerAnalysis]:
    stmt = select(CareerAnalysis).order_by(CareerAnalysis.created_at.desc())
    res = await session.execute(stmt)
    return res.scalars().all()


async def get_career_analysis(session: AsyncSession, analysis_id: uuid.UUID) -> Optional[CareerAnalysis]:
    return await session.get(CareerAnalysis, analysis_id)


async def delete_career_analysis(session: AsyncSession, analysis_id: uuid.UUID) -> bool:
    analysis = await session.get(CareerAnalysis, analysis_id)
    if analysis:
        await session.delete(analysis)
        await session.commit()
        return True
    return False
