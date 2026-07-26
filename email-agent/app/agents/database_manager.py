from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.database import Base, engine, SessionLocal, Meeting
from datetime import datetime

def _parse_date(date_str: str):
    if not date_str: return None
    try: return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception: return None

def _parse_time(time_str: str):
    if not time_str: return None
    try: return datetime.strptime(time_str, "%H:%M").time()
    except Exception: return None


class MeetingStore:
    def __init__(self, db: Optional[Session] = None) -> None:
        Base.metadata.create_all(bind=engine)
        self.db = db

    def _get_session(self) -> Session:
        return self.db if self.db is not None else SessionLocal()

    def add_meeting(self, meeting_data: Dict[str, object]) -> Dict[str, object]:
        session = self._get_session()
        try:
            email_id = meeting_data.get("email_id")
            existing = None
            if email_id:
                existing = session.query(Meeting).filter(Meeting.email_id == email_id).first()

            if existing:
                for key, val in meeting_data.items():
                    if key == "date":
                        existing.meeting_date = _parse_date(val)
                    elif key in ("start_time", "end_time") and val:
                        setattr(existing, key, _parse_time(val))
                    elif hasattr(existing, key) and val is not None and key not in ("id", "created_at"):
                        setattr(existing, key, val)
                session.commit()
                session.refresh(existing)
                res = self._meeting_to_dict(existing)
            else:
                new_meeting = Meeting(
                    email_id=meeting_data.get("email_id"),
                    organizer=meeting_data.get("organizer"),
                    title=meeting_data.get("title", "Untitled Meeting"),
                    description=meeting_data.get("description"),
                    platform=meeting_data.get("platform"),
                    meeting_url=meeting_data.get("meeting_link") or meeting_data.get("meeting_url"),
                    meeting_date=_parse_date(meeting_data.get("date")),
                    start_time=_parse_time(meeting_data.get("start_time")),
                    end_time=_parse_time(meeting_data.get("end_time")),
                    time_zone=meeting_data.get("time_zone"),
                    status=meeting_data.get("status", "scheduled"),
                )
                session.add(new_meeting)
                session.commit()
                session.refresh(new_meeting)
                res = self._meeting_to_dict(new_meeting)
            return res
        finally:
            if self.db is None:
                session.close()

    def list_meetings(self) -> List[Dict[str, object]]:
        session = self._get_session()
        try:
            meetings = session.query(Meeting).order_by(Meeting.created_at.desc()).all()
            return [self._meeting_to_dict(m) for m in meetings]
        finally:
            if self.db is None:
                session.close()

    def clear_all_meetings(self) -> None:
        session = self._get_session()
        from sqlalchemy import text
        try:
            # Cleanly cascade delete through child tables to satisfy Foreign Key constraints
            session.execute(text("DELETE FROM meeting_reports"))
            session.execute(text("DELETE FROM meeting_transcripts"))
            session.execute(text("DELETE FROM notifications"))
            session.execute(text("DELETE FROM audit_logs"))
            session.execute(text("DELETE FROM meeting_attendance"))
            
            session.query(Meeting).delete()
            session.commit()
        finally:
            if self.db is None:
                session.close()

    def find_by_url_or_email(self, url: Optional[str], email_id: Optional[str]) -> Optional[Dict[str, object]]:
        session = self._get_session()
        try:
            query = session.query(Meeting)
            if email_id:
                m = query.filter(Meeting.email_id == email_id).first()
                if m:
                    return self._meeting_to_dict(m)
            if url:
                m = query.filter(Meeting.meeting_url == url).first()
                if m:
                    return self._meeting_to_dict(m)
            return None
        finally:
            if self.db is None:
                session.close()

    @staticmethod
    def _meeting_to_dict(meeting: Meeting) -> Dict[str, object]:
        return {
            "id": str(meeting.id) if meeting.id else None,
            "email_id": meeting.email_id,
            "organizer": meeting.organizer,
            "title": meeting.title,
            "description": meeting.description,
            "platform": meeting.platform,
            "meeting_link": meeting.meeting_url,
            "meeting_url": meeting.meeting_url,
            "date": meeting.meeting_date.isoformat() if meeting.meeting_date else None,
            "start_time": meeting.start_time.strftime("%H:%M") if meeting.start_time else None,
            "end_time": meeting.end_time.strftime("%H:%M") if meeting.end_time else None,
            "time_zone": meeting.time_zone,
            "status": meeting.status,
            "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
            "updated_at": meeting.updated_at.isoformat() if meeting.updated_at else None,
        }
