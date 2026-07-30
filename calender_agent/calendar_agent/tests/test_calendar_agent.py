import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from calendar_agent.app.database.database import Base
from calendar_agent.app.agent.calendar_agent import CalendarAgent
from calendar_agent.app.schemas.calendar import CalendarEventCreate

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_calendar_agent_lifecycle(db_session):
    agent = CalendarAgent(db_session, user_id="user_1")

    # Sync
    sync_res = agent.sync()
    assert sync_res.created_count > 0

    # Status
    status = agent.get_status()
    assert status.total_events > 0

    # Create manual event
    evt_in = CalendarEventCreate(
        title="Manual Test Meeting",
        event_type="MEETING",
        priority="HIGH"
    )
    created = agent.create_event(evt_in)
    assert created.title == "Manual Test Meeting"

    # Cancel event
    cancelled = agent.cancel_event(created.id)
    assert cancelled.status == "CANCELLED"
