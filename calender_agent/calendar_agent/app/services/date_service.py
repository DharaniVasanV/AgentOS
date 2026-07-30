import os
import re
from datetime import datetime, date, time, timezone as tz, timedelta
from typing import Optional, Tuple
import zoneinfo

DEFAULT_TIMEZONE_STR = os.getenv("DEFAULT_TIMEZONE", "Asia/Kolkata")

class DateService:
    @staticmethod
    def get_user_timezone(tz_name: Optional[str] = None):
        tz_str = tz_name or DEFAULT_TIMEZONE_STR
        try:
            return zoneinfo.ZoneInfo(tz_str)
        except Exception:
            return tz.utc

    @staticmethod
    def parse_datetime(dt_str: Optional[str], tz_name: Optional[str] = None) -> Optional[datetime]:
        """
        Parses an ISO-8601 or standard datetime string into a timezone-aware UTC datetime.
        Returns None if dt_str is empty, null, or unparseable.
        """
        if not dt_str or not isinstance(dt_str, str):
            return None
        
        dt_str = dt_str.strip()
        if not dt_str or dt_str.lower() in ("null", "none", "n/a"):
            return None

        # Clean string
        dt_str = dt_str.replace("Z", "+00:00")

        # 1. Try standard ISO-8601 parsing
        try:
            parsed = datetime.fromisoformat(dt_str)
            if parsed.tzinfo is None:
                user_tz = DateService.get_user_timezone(tz_name)
                parsed = parsed.replace(tzinfo=user_tz)
            return parsed.astimezone(tz.utc)
        except ValueError:
            pass

        # 2. Try explicit common datetime formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%B %d, %Y %I:%M %p",
            "%B %d, %Y",
            "%b %d, %Y %I:%M %p",
            "%b %d, %Y",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(dt_str, fmt)
                if parsed.tzinfo is None:
                    user_tz = DateService.get_user_timezone(tz_name)
                    parsed = parsed.replace(tzinfo=user_tz)
                return parsed.astimezone(tz.utc)
            except ValueError:
                continue

        return None

    @staticmethod
    def combine_date_time(date_str: Optional[str], time_str: Optional[str], tz_name: Optional[str] = None) -> Optional[datetime]:
        """
        Combines separate date and time strings into a datetime object.
        """
        if not date_str:
            return None
        
        user_tz = DateService.get_user_timezone(tz_name)
        
        # Try to parse date
        parsed_date = None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y"):
            try:
                parsed_date = datetime.strptime(date_str.strip(), fmt).date()
                break
            except ValueError:
                continue
        
        if not parsed_date:
            dt = DateService.parse_datetime(date_str, tz_name)
            if dt:
                parsed_date = dt.date()

        if not parsed_date:
            return None

        parsed_time = time(17, 0) # Default 5 PM for deadlines if time isn't explicitly provided
        if time_str:
            t_str = time_str.strip()
            for t_fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I %p"):
                try:
                    parsed_time = datetime.strptime(t_str, t_fmt).time()
                    break
                except ValueError:
                    continue

        combined = datetime.combine(parsed_date, parsed_time)
        combined = combined.replace(tzinfo=user_tz)
        return combined.astimezone(tz.utc)

    @staticmethod
    def is_valid_future_or_current(dt: Optional[datetime]) -> bool:
        """
        Validates that datetime object exists.
        """
        return dt is not None
