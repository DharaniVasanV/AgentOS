import os
from datetime import datetime, timezone
import uuid
from sqlalchemy import create_engine, Column, String, Text, DateTime, Date, Time, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.dialects.postgresql import UUID


def _load_env_file() -> dict:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(project_root, ".env")
    if not os.path.exists(env_path):
        return {}
    values = {}
    with open(env_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            values[key.strip()] = val.strip()
    return values


ENV_VALUES = _load_env_file()
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
default_sqlite_url = f"sqlite:///{os.path.join(project_root, 'meetings.db')}"

RAW_DB_URL = os.getenv("DATABASE_URL") or ENV_VALUES.get("DATABASE_URL") or default_sqlite_url

# Fix legacy 'postgres://' scheme for SQLAlchemy 2.0
if RAW_DB_URL.startswith("postgres://"):
    RAW_DB_URL = RAW_DB_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if RAW_DB_URL.startswith("sqlite") else {}

try:
    engine = create_engine(RAW_DB_URL, connect_args=connect_args)
    # Test connection
    with engine.connect() as conn:
        pass
except Exception as exc:
    print(f"CRITICAL ERROR: Could not connect to primary database '{RAW_DB_URL}': {exc}.")
    raise exc

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_utc_now():
    return datetime.now(timezone.utc)


class Meeting(Base):
    __tablename__ = "meetings"

    # Core meeting-agent columns (so meeting-agent can fetch & process these)
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    title = Column(String(255), nullable=False)
    meeting_url = Column(Text, nullable=True)
    meeting_date = Column(Date, nullable=True)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    platform = Column(String(50), nullable=True)
    meeting_id = Column(String(255), nullable=True)  # Meeting code (e.g. from Zoom)
    passcode = Column(String(255), nullable=True)
    status = Column(String(50), default="scheduled")
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    # Extra columns that email-agent extracts
    email_id = Column(String(255), unique=True, index=True, nullable=True)
    organizer = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    time_zone = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=get_utc_now)


class MeetingReport(Base):
    __tablename__ = "meeting_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    meeting_id = Column(UUID(as_uuid=True), nullable=False)
    summary = Column(Text, nullable=False)
    created_at = Column(DateTime, default=get_utc_now)


class MeetingTranscript(Base):
    __tablename__ = "meeting_transcripts"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    meeting_id = Column(UUID(as_uuid=True), nullable=False)
    transcript = Column(Text, nullable=False)
    language = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=get_utc_now)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
