"""
app/api/routes.py

FastAPI routes for Research Agent API.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db import crud
from app.db.database import get_db
from app.services import research_service

router = APIRouter()


class AnalyzeRequest(BaseModel):
    content: str


@router.get("/health")
async def health():
    return {"status": "ok", "service": "Research Agent", "version": "1.0"}


@router.post("/analyze")
async def analyze_content_route(
    req: AnalyzeRequest,
    session: AsyncSession = Depends(get_db)
):
    if not req.content or not req.content.strip():
        raise HTTPException(status_code=400, detail="Content to analyze cannot be empty.")

    try:
        structured_data = await research_service.analyze_content(req.content)
        record = await crud.create_analysis(session, raw_content=req.content, structured_data=structured_data)
        return {
            "id": record.id,
            "created_at": record.created_at,
            "analysis": structured_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyses")
async def list_analyses(session: AsyncSession = Depends(get_db)):
    records = await crud.get_all_analyses(session)
    return records


@router.get("/analyses/{analysis_id}")
async def get_analysis(analysis_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    record = await crud.get_analysis(session, analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return record


@router.delete("/analyses/{analysis_id}")
async def delete_analysis(analysis_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    success = await crud.delete_analysis(session, analysis_id)
    if not success:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"status": "deleted", "id": analysis_id}
