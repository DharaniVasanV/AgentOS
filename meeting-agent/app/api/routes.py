"""
app/api/routes.py

Purpose
-------
Read-only HTTP surface over the data this service generates, plus one
manual-trigger endpoint for testing a specific meeting without waiting
for the scheduler. This service's real "work" happens in the
background scheduler, not through these endpoints — they exist for
observability/debugging and for any frontend that wants to display
transcripts/reports.

Responsibilities
----------------
- GET /health
- GET /meetings/{meeting_id}/transcript
- GET /meetings/{meeting_id}/report
- GET /meetings/{meeting_id}/action-items
- GET /meetings/{meeting_id}/decisions
- POST /meetings/{meeting_id}/trigger  (manual join, bypasses the scheduler's timing check)

Dependencies
------------
FastAPI, app.db.database.get_db, app.db.crud, app.services.meeting_joiner
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.db.database import get_db
from app.services import meeting_joiner

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/meetings/{meeting_id}/transcript")
async def get_transcript(meeting_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    row = await crud.get_transcript(session, meeting_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return {"meeting_id": meeting_id, "language": row.language, "transcript": row.transcript}


@router.get("/meetings/{meeting_id}/report")
async def get_report(meeting_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    row = await crud.get_report(session, meeting_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "meeting_id": meeting_id,
        "summary": row.summary,
        "key_points": row.key_points,
        "follow_up": row.follow_up,
        "sentiment": row.sentiment,
    }


@router.get("/meetings/{meeting_id}/action-items")
async def get_action_items(meeting_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    rows = await crud.get_action_items(session, meeting_id)
    return [
        {"id": r.id, "assigned_to": r.assigned_to, "task": r.task, "deadline": r.deadline, "status": r.status}
        for r in rows
    ]


@router.get("/meetings/{meeting_id}/decisions")
async def get_decisions(meeting_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    rows = await crud.get_decisions(session, meeting_id)
    return [{"id": r.id, "decision": r.decision} for r in rows]


@router.post("/meetings/{meeting_id}/trigger")
async def trigger_meeting(meeting_id: uuid.UUID, background_tasks: BackgroundTasks):
    """Manually kick off the join/record/transcribe pipeline for one
    meeting right now — useful for testing without waiting for the
    scheduler's timing window."""
    background_tasks.add_task(meeting_joiner.handle_meeting, meeting_id)
    return {"status": "triggered", "meeting_id": meeting_id}
