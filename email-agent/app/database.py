import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, sessionmaker


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
    print(f"Warning: Could not connect to primary database '{RAW_DB_URL}': {exc}. Falling back to SQLite.")
    RAW_DB_URL = default_sqlite_url
    engine = create_engine(RAW_DB_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_utc_now():
    return datetime.now(timezone.utc)


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(String, unique=True, index=True, nullable=True)
    organizer = Column(String, nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    platform = Column(String, nullable=True)
    meeting_url = Column(String, nullable=True)
    date = Column(String, nullable=True)  # YYYY-MM-DD
    start_time = Column(String, nullable=True)  # HH:MM
    end_time = Column(String, nullable=True)  # HH:MM
    time_zone = Column(String, nullable=True)
    status = Column(String, default="scheduled")  # scheduled, updated, cancelled
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
