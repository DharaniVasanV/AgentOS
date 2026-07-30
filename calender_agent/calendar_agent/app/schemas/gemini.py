from typing import Optional, List, Literal
from pydantic import BaseModel, Field

EventTypeEnum = Literal[
    "MEETING",
    "TASK_DEADLINE",
    "APPLICATION_DEADLINE",
    "HACKATHON",
    "INTERNSHIP",
    "CERTIFICATION",
    "GENERAL_EVENT"
]

PriorityEnum = Literal["LOW", "MEDIUM", "HIGH", "URGENT"]

class CalendarIntent(BaseModel):
    """
    Structured Calendar Intent output extracted and normalized by Gemini API.
    Validated by Pydantic before any database or calendar operations.
    """
    title: str = Field(..., description="Title of the calendar event or task deadline")
    description: Optional[str] = Field(default=None, description="Detailed description or context")
    event_type: EventTypeEnum = Field(..., description="Categorized event type")
    start_datetime: Optional[str] = Field(default=None, description="ISO-8601 formatted start datetime or null")
    end_datetime: Optional[str] = Field(default=None, description="ISO-8601 formatted end datetime or null")
    deadline: Optional[str] = Field(default=None, description="ISO-8601 formatted deadline datetime or null")
    all_day: bool = Field(default=False, description="Whether event spans full day without specific time")
    priority: PriorityEnum = Field(default="MEDIUM", description="Task/event priority level")
    location: Optional[str] = Field(default=None, description="Physical or virtual location")
    meeting_url: Optional[str] = Field(default=None, description="Link for meeting or application")
    source_type: str = Field(..., description="Origin source system: meeting_tasks, applications, manual")
    source_id: str = Field(..., description="ID from the origin source record")
    suggested_reminders: List[int] = Field(default_factory=list, description="Suggested reminder offsets in minutes before event")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score from 0.0 to 1.0")
