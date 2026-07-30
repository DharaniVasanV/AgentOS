from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field

class ReminderItem(BaseModel):
    value: int
    unit: str = "minutes" # minutes, hours, days, weeks
    before: str = "start" # start, deadline

class ManualEventDetail(BaseModel):
    title: str = ""
    event_type: str = ""
    description: Optional[str] = None
    start_date: Optional[str] = None # YYYY-MM-DD
    start_time: Optional[str] = None # HH:MM (24-hour)
    end_date: Optional[str] = None   # YYYY-MM-DD
    end_time: Optional[str] = None   # HH:MM (24-hour)
    deadline: Optional[str] = None   # YYYY-MM-DD or YYYY-MM-DDTHH:MM
    location: Optional[str] = None
    meeting_url: Optional[str] = None
    priority: Optional[str] = None   # Null unless user explicitly specified priority!
    participants: List[str] = Field(default_factory=list)
    reminders: List[Union[ReminderItem, Dict[str, Any]]] = Field(default_factory=list)
    recurrence: Optional[str] = None
    source: Optional[str] = None

class ManualEventAnalysisResponse(BaseModel):
    status: str = "ready" # "ready" or "needs_clarification"
    event: ManualEventDetail
    needs_clarification: bool = False
    missing_fields: List[str] = Field(default_factory=list)

class ManualInputRequest(BaseModel):
    text: str = Field(..., description="Natural language input text describing an event, task, or deadline.")
