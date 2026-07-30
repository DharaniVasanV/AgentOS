"""
app/api/routes.py

FastAPI routes for Meeting Agent UI and management API.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db import crud
from app.db.database import get_db
from app.services import meeting_joiner

router = APIRouter()


class MeetingCreateRequest(BaseModel):
    title: str
    meeting_url: str
    organizer: Optional[str] = None
    platform: Optional[str] = "google_meet"
    meeting_date: Optional[str] = None  # YYYY-MM-DD
    start_time: Optional[str] = None    # HH:MM
    end_time: Optional[str] = None      # HH:MM
    passcode: Optional[str] = None
    status: Optional[str] = "scheduled"


class MeetingUpdateRequest(BaseModel):
    title: Optional[str] = None
    organizer: Optional[str] = None
    meeting_url: Optional[str] = None
    platform: Optional[str] = None
    meeting_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    passcode: Optional[str] = None
    status: Optional[str] = None


@router.get("/health")
async def health():
    return {"status": "ok", "service": "Meeting Agent"}


@router.post("/bot/connect")
async def connect_bot_route():
    """Triggered by the Connect Bot button. Launches Chrome for user sign-in and saves session."""
    from app.services.browser import connect_bot_session
    try:
        session_file = await connect_bot_session()
        return {"status": "connected", "message": f"Bot connected successfully! Session saved to {session_file}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect bot: {str(e)}")


@router.get("/meetings")
async def list_meetings(session: AsyncSession = Depends(get_db)):
    meetings = await crud.get_all_meetings(session)
    return meetings


@router.post("/meetings")
async def create_meeting(req: MeetingCreateRequest, session: AsyncSession = Depends(get_db)):
    from datetime import datetime
    data = req.dict(exclude_unset=True)
    if data.get("meeting_date") and isinstance(data["meeting_date"], str):
        try:
            data["meeting_date"] = datetime.strptime(data["meeting_date"], "%Y-%m-%d").date()
        except ValueError:
            data["meeting_date"] = None
    if data.get("start_time") and isinstance(data["start_time"], str):
        try:
            data["start_time"] = datetime.strptime(data["start_time"], "%H:%M").time()
        except ValueError:
            data["start_time"] = None
    if data.get("end_time") and isinstance(data["end_time"], str):
        try:
            data["end_time"] = datetime.strptime(data["end_time"], "%H:%M").time()
        except ValueError:
            data["end_time"] = None

    m = await crud.create_meeting(session, data)
    return m


@router.get("/meetings/{meeting_id}")
async def get_meeting(meeting_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    m = await crud.get_meeting(session, meeting_id)
    if not m:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return m


@router.put("/meetings/{meeting_id}")
async def update_meeting(meeting_id: uuid.UUID, req: MeetingUpdateRequest, session: AsyncSession = Depends(get_db)):
    from datetime import datetime
    data = req.dict(exclude_unset=True)
    if data.get("meeting_date") and isinstance(data["meeting_date"], str):
        try:
            data["meeting_date"] = datetime.strptime(data["meeting_date"], "%Y-%m-%d").date()
        except ValueError:
            data["meeting_date"] = None
    if data.get("start_time") and isinstance(data["start_time"], str):
        try:
            data["start_time"] = datetime.strptime(data["start_time"], "%H:%M").time()
        except ValueError:
            data["start_time"] = None
    if data.get("end_time") and isinstance(data["end_time"], str):
        try:
            data["end_time"] = datetime.strptime(data["end_time"], "%H:%M").time()
        except ValueError:
            data["end_time"] = None

    m = await crud.update_meeting(session, meeting_id, data)
    if not m:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return m


@router.delete("/meetings/{meeting_id}")
async def delete_meeting(meeting_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    success = await crud.delete_meeting(session, meeting_id)
    if not success:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return {"status": "deleted", "meeting_id": meeting_id}


@router.post("/meetings/{meeting_id}/trigger")
async def trigger_meeting(meeting_id: uuid.UUID, background_tasks: BackgroundTasks):
    """Manually trigger bot to join, record audio, generate dialogue transcript and store in DB."""
    background_tasks.add_task(meeting_joiner.handle_meeting, meeting_id)
    return {"status": "triggered", "meeting_id": meeting_id}


class ReformatRequest(BaseModel):
    transcript: Optional[str] = None


@router.post("/meetings/{meeting_id}/reformat")
async def reformat_meeting_transcript(
    meeting_id: uuid.UUID,
    req: Optional[ReformatRequest] = None,
    session: AsyncSession = Depends(get_db)
):
    """Re-formats an existing transcript to replace generic 'Speaker 1/2' with actual person names using Groq LLM."""
    from app.services.whisper_service import reformat_transcript_text
    m = await crud.get_meeting(session, meeting_id)
    if not m:
        raise HTTPException(status_code=404, detail="Meeting not found")

    raw_text = (req.transcript if req and req.transcript else m.transcript) or ""
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="Transcript is empty")

    new_transcript = reformat_transcript_text(
        raw_or_existing_transcript=raw_text,
        organizer=m.organizer or "",
        meeting_title=m.title or "",
    )
    updated = await crud.save_transcript(session, meeting_id, new_transcript)
    return updated
