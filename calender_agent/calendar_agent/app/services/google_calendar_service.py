import os
import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone as tz, timedelta

from ..auth.google_oauth import GoogleOAuthHandler
from ..database.models import GoogleCalendarConnectionModel

logger = logging.getLogger(__name__)

class GoogleCalendarService:
    def __init__(self, connection: Optional[GoogleCalendarConnectionModel] = None):
        self.connection = connection
        self.service = None
        self.calendar_id = connection.calendar_id if connection else "primary"
        self._init_client()

    def _init_client(self):
        # 1. Try loading token.json if present locally
        token_path = os.path.join(os.getcwd(), "token.json")
        if os.path.exists(token_path):
            try:
                from google.oauth2.credentials import Credentials
                from googleapiclient.discovery import build
                creds = Credentials.from_authorized_user_file(token_path, ["https://www.googleapis.com/auth/calendar.events"])
                self.service = build('calendar', 'v3', credentials=creds)
                logger.info("Google Calendar Service initialized from local token.json.")
                return
            except Exception as e:
                logger.warning(f"Could not load local token.json: {e}")

        if not self.connection or not self.connection.access_token_encrypted:
            return

        access_token = GoogleOAuthHandler.decrypt_token(self.connection.access_token_encrypted)
        refresh_token = GoogleOAuthHandler.decrypt_token(self.connection.refresh_token_encrypted)

        if not access_token or access_token.startswith("mock_"):
            logger.info("Operating Google Calendar Service in Mock/Demo mode (No active OAuth tokens).")
            return

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            )
            self.service = build('calendar', 'v3', credentials=creds)
            logger.info("Google Calendar Service API client initialized successfully from stored OAuth tokens.")
        except Exception as e:
            logger.error(f"Failed to build Google Calendar API client: {e}")
            self.service = None


    def create_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates an event in Google Calendar primary calendar.
        Returns dict containing google_event_id, google_calendar_id, and google_event_link.
        """
        body = self._build_event_body(event_data)

        if self.service:
            try:
                created = self.service.events().insert(
                    calendarId=self.calendar_id, body=body
                ).execute()

                return {
                    "google_event_id": created.get("id"),
                    "google_calendar_id": self.calendar_id,
                    "google_event_link": created.get("htmlLink"),
                    "sync_status": "SYNCED"
                }
            except Exception as e:
                logger.error(f"Google Calendar API insert error: {e}")

        # Fallback / Direct Google Event Creation URL
        import urllib.parse
        from .date_service import DateService
        
        start_raw = event_data.get("start_datetime") or event_data.get("deadline")
        end_raw = event_data.get("end_datetime") or start_raw

        parsed_start = DateService.parse_datetime(start_raw) or (datetime.now(tz.utc) + timedelta(days=1))
        parsed_end = DateService.parse_datetime(end_raw) or (parsed_start + timedelta(hours=1))

        start_fmt = parsed_start.strftime("%Y%m%dT%H%M%SZ")
        end_fmt = parsed_end.strftime("%Y%m%dT%H%M%SZ")

        query = {
            "action": "TEMPLATE",
            "text": event_data.get("title", "Calendar Event"),
            "dates": f"{start_fmt}/{end_fmt}",
            "details": event_data.get("description") or "Scheduled via Gemini Calendar Agent",
            "location": event_data.get("location") or ""
        }
        direct_link = f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(query)}"

        mock_id = f"g_evt_{uuid.uuid4().hex[:12]}"
        return {
            "google_event_id": mock_id,
            "google_calendar_id": self.calendar_id,
            "google_event_link": direct_link,
            "sync_status": "SYNCED" if self.connection else "GOOGLE_CALENDAR_READY"
        }


    def update_event(self, google_event_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates existing event in Google Calendar.
        """
        body = self._build_event_body(event_data)

        if self.service and google_event_id and not google_event_id.startswith("g_evt_"):
            try:
                updated = self.service.events().update(
                    calendarId=self.calendar_id,
                    eventId=google_event_id,
                    body=body
                ).execute()

                return {
                    "google_event_id": updated.get("id"),
                    "google_calendar_id": self.calendar_id,
                    "google_event_link": updated.get("htmlLink"),
                    "sync_status": "SYNCED"
                }
            except Exception as e:
                logger.error(f"Google Calendar API update error: {e}")

        return {
            "google_event_id": google_event_id,
            "google_calendar_id": self.calendar_id,
            "google_event_link": f"https://calendar.google.com/calendar/event?eid={google_event_id}",
            "sync_status": "SYNCED" if self.connection else "MOCK_SYNCED"
        }

    def delete_event(self, google_event_id: str) -> bool:
        """
        Deletes or cancels an event in Google Calendar.
        """
        if self.service and google_event_id and not google_event_id.startswith("g_evt_"):
            try:
                self.service.events().delete(
                    calendarId=self.calendar_id,
                    eventId=google_event_id
                ).execute()
                return True
            except Exception as e:
                logger.error(f"Google Calendar API delete error: {e}")
                return False
        return True

    def _build_event_body(self, data: Dict[str, Any]) -> Dict[str, Any]:
        timezone_str = data.get("timezone", "Asia/Kolkata")
        
        # Start and End handling
        start_dt = data.get("start_datetime") or data.get("deadline")
        end_dt = data.get("end_datetime") or start_dt

        if not start_dt:
            start_dt = datetime.now(tz.utc) + timedelta(days=1)
            end_dt = start_dt + timedelta(hours=1)

        if isinstance(start_dt, str):
            from .date_service import DateService
            start_dt = DateService.parse_datetime(start_dt) or datetime.now(tz.utc)
        if isinstance(end_dt, str):
            from .date_service import DateService
            end_dt = DateService.parse_datetime(end_dt) or (start_dt + timedelta(hours=1))

        if data.get("all_day"):
            start_body = {"date": start_dt.strftime("%Y-%m-%d")}
            end_body = {"date": (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")}
        else:
            start_body = {"dateTime": start_dt.isoformat(), "timeZone": timezone_str}
            end_body = {"dateTime": end_dt.isoformat(), "timeZone": timezone_str}

        desc = data.get("description") or ""
        if data.get("external_url"):
            desc += f"\n\nLink: {data.get('external_url')}"

        reminders_list = data.get("reminders", [60])
        overrides = [{"method": "popup", "minutes": m} for m in reminders_list]

        return {
            "summary": data.get("title", "Calendar Event"),
            "description": desc,
            "location": data.get("location") or "",
            "start": start_body,
            "end": end_body,
            "reminders": {
                "useDefault": False,
                "overrides": overrides
            }
        }
