"""
app/api/routes.py

FastAPI routes for Career Agent API.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db import crud
from app.db.database import get_db
from app.services import career_service

router = APIRouter()


class AnalyzeRequest(BaseModel):
    content: str


@router.get("/health")
async def health():
    return {"status": "ok", "service": "Career Agent", "version": "1.0"}


@router.post("/analyze")
async def analyze_career_route(
    req: AnalyzeRequest,
    session: AsyncSession = Depends(get_db)
):
    if not req.content or not req.content.strip():
        raise HTTPException(status_code=400, detail="Career profile content cannot be empty.")

    try:
        structured_data = await career_service.analyze_career(req.content)
        record = await crud.create_career_analysis(session, raw_content=req.content, structured_data=structured_data)

        # Auto-ingest profile into Knowledge Ingestion Service (8003)
        try:
            import urllib.request, json
            payload = json.dumps({
                "content": req.content,
                "source_agent": "Career Agent",
                "user_id": "user_default"
            }).encode('utf-8')
            ingest_req = urllib.request.Request("http://127.0.0.1:8003/ingest", data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(ingest_req, timeout=3)
        except Exception:
            pass

        return {
            "id": record.id,
            "created_at": record.created_at,
            "analysis": structured_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyses")
async def list_analyses(session: AsyncSession = Depends(get_db)):
    records = await crud.get_all_career_analyses(session)
    return records


@router.get("/analyses/{analysis_id}")
async def get_analysis(analysis_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    record = await crud.get_career_analysis(session, analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail="Career analysis not found")
    return record


@router.delete("/analyses/{analysis_id}")
async def delete_analysis(analysis_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    success = await crud.delete_career_analysis(session, analysis_id)
    if not success:
        raise HTTPException(status_code=404, detail="Career analysis not found")
    return {"status": "deleted", "id": analysis_id}
