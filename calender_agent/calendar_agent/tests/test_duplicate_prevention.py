import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from calendar_agent.app.database.database import Base
from calendar_agent.app.services.sync_service import SyncService
from calendar_agent.app.database.repository import CalendarRepository

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_duplicate_prevention(db_session):
    sync_service = SyncService(db_session)
    repo = CalendarRepository(db_session)

    # First sync run
    summary1 = sync_service.run_sync("user_test")
    assert summary1.created_count > 0
    created_initial = summary1.created_count

    # Second sync run immediately after (No data changed)
    summary2 = sync_service.run_sync("user_test")
    assert summary2.created_count == 0
    assert summary2.unchanged_count == created_initial

    # Check total events in database
    events = repo.list_events("user_test")
    assert len(events) == created_initial
