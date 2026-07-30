import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from calendar_agent.app.database.database import Base
from calendar_agent.app.services.sync_service import SyncService

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_sync_execution(db_session):
    sync_service = SyncService(db_session)
    summary = sync_service.run_sync("user_1")
    
    assert summary.total_processed > 0
    assert summary.created_count > 0
    assert summary.failed_count == 0
