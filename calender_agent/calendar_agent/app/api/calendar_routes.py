from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..agent.calendar_agent import CalendarAgent
from ..schemas.calendar import (
    CalendarEventCreate,
    CalendarEventUpdate,
    CalendarEventResponse,
    SyncSummary,
    CalendarStatus
)
from ..schemas.manual_event import ManualInputRequest, ManualEventAnalysisResponse


router = APIRouter(prefix="/api/calendar", tags=["Calendar Agent"])

def get_agent(db: Session = Depends(get_db)) -> CalendarAgent:
    return CalendarAgent(db=db, user_id="user_1")

@router.post("/sync", response_model=SyncSummary)
def run_calendar_sync(agent: CalendarAgent = Depends(get_agent)):
    """
    Triggers the Calendar Agent synchronization workflow over meeting_tasks and applications.
    """
    return agent.sync()

@router.post("/events", response_model=CalendarEventResponse)
def create_manual_event(event_in: CalendarEventCreate, agent: CalendarAgent = Depends(get_agent)):
    """
    Creates a new manual calendar event and syncs with Google Calendar.
    """
    return agent.create_event(event_in)

@router.get("/events", response_model=List[CalendarEventResponse])
def get_calendar_events(
    status: Optional[str] = Query(None, description="Filter by status: ACTIVE, COMPLETED, CANCELLED"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    agent: CalendarAgent = Depends(get_agent)
):
    """
    Lists calendar events for current user.
    """
    return agent.calendar_service.list_events(status=status, event_type=event_type)

@router.get("/today", response_model=List[CalendarEventResponse])
def get_today_events(agent: CalendarAgent = Depends(get_agent)):
    """
    Returns today's scheduled events and deadlines.
    """
    return agent.get_today_schedule()

@router.get("/upcoming", response_model=List[CalendarEventResponse])
def get_upcoming_events(agent: CalendarAgent = Depends(get_agent)):
    """
    Returns upcoming calendar events.
    """
    return agent.calendar_service.get_upcoming_events()

@router.get("/deadlines", response_model=List[CalendarEventResponse])
def get_upcoming_deadlines(agent: CalendarAgent = Depends(get_agent)):
    """
    Returns upcoming task and application deadlines.
    """
    return agent.get_upcoming_deadlines()

@router.get("/events/{event_id}", response_model=CalendarEventResponse)
def get_event_details(event_id: str, agent: CalendarAgent = Depends(get_agent)):
    """
    Returns detailed information for a single calendar event.
    """
    evt = agent.calendar_service.get_event(event_id)
    if not evt:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    return evt

@router.put("/events/{event_id}", response_model=CalendarEventResponse)
def update_event_details(
    event_id: str,
    update_in: CalendarEventUpdate,
    agent: CalendarAgent = Depends(get_agent)
):
    """
    Updates details for an existing event and syncs changes to Google Calendar.
    """
    updated = agent.update_event(event_id, update_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    return updated

@router.delete("/events/{event_id}", response_model=CalendarEventResponse)
def cancel_calendar_event(event_id: str, agent: CalendarAgent = Depends(get_agent)):
    """
    Cancels or soft-deletes a calendar event.
    """
    cancelled = agent.cancel_event(event_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    return cancelled

@router.post("/schedule-gemini", response_model=CalendarEventResponse)
def schedule_event_with_gemini(input_data: dict, agent: CalendarAgent = Depends(get_agent)):
    """
    Schedules an event using Google Gemini AI normalization from date, title, and prompt.
    """
    return agent.schedule_with_gemini(input_data)

@router.post("/analyze-manual-input", response_model=ManualEventAnalysisResponse)
def analyze_manual_input_endpoint(req: ManualInputRequest, agent: CalendarAgent = Depends(get_agent)):
    """
    Analyzes natural language manual input string according to strict AGENTOS Manual Input rules.
    """
    return agent.analyze_manual_input(req.text)

@router.delete("/clear-all")
def clear_all_calendar_events(agent: CalendarAgent = Depends(get_agent)):

    """
    Clears all events from the database (removing mock and scheduled events).
    """
    count = agent.clear_all_events()
    return {"status": "success", "deleted_count": count}

@router.get("/status", response_model=CalendarStatus)
def get_calendar_status(agent: CalendarAgent = Depends(get_agent)):
    """
    Returns Google Calendar connection and agent synchronization status telemetry.
    """
    return agent.get_status()

