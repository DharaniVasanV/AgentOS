from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

class ReminderCreate(BaseModel):
    reminder_method: str = Field(default="popup", description="popup or email")
    minutes_before: int = Field(..., description="Minutes before event time")

class ReminderResponse(BaseModel):
    id: str
    calendar_event_id: str
    reminder_method: str
    minutes_before: int
    created_at: datetime

    class Config:
        from_attributes = True

class CalendarEventCreate(BaseModel):
    user_id: str = Field(default="user_1")
    source_type: str = Field(default="manual")
    source_id: Optional[str] = Field(default=None)
    event_type: str = Field(default="GENERAL_EVENT")
    title: str
    description: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    deadline: Optional[datetime] = None
    all_day: bool = False
    timezone: str = Field(default="Asia/Kolkata")
    location: Optional[str] = None
    external_url: Optional[str] = None
    priority: Optional[str] = Field(default=None)
    reminders: List[int] = Field(default_factory=list)

class CalendarEventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    deadline: Optional[datetime] = None
    all_day: Optional[bool] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    external_url: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None

class CalendarEventResponse(BaseModel):
    id: str
    user_id: str
    source_type: str
    source_id: Optional[str] = None
    event_type: str
    title: str
    description: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    deadline: Optional[datetime] = None
    all_day: bool
    timezone: str
    location: Optional[str] = None
    external_url: Optional[str] = None
    priority: Optional[str] = None

    status: str
    google_calendar_id: Optional[str] = None
    google_event_id: Optional[str] = None
    google_event_link: Optional[str] = None
    sync_status: str
    created_at: datetime
    updated_at: datetime
    synced_at: Optional[datetime] = None
    reminders: List[ReminderResponse] = []

    class Config:
        from_attributes = True

class SyncSummary(BaseModel):
    total_processed: int = 0
    created_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    cancelled_count: int = 0
    skipped_invalid_date: int = 0
    failed_count: int = 0
    google_synced_count: int = 0
    details: List[dict] = []

class CalendarStatus(BaseModel):
    google_connected: bool
    google_account_email: Optional[str] = None
    total_events: int
    active_events: int
    today_events_count: int
    upcoming_deadlines_count: int
    last_synced_at: Optional[datetime] = None
    default_timezone: str
