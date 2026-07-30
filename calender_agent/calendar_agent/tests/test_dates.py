import pytest
from datetime import datetime, timezone as tz
from calendar_agent.app.services.date_service import DateService

def test_parse_iso_datetime():
    dt_str = "2026-08-15T17:00:00Z"
    parsed = DateService.parse_datetime(dt_str)
    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 8
    assert parsed.day == 15

def test_parse_null_date():
    assert DateService.parse_datetime(None) is None
    assert DateService.parse_datetime("null") is None
    assert DateService.parse_datetime("") is None

def test_combine_date_time():
    combined = DateService.combine_date_time("2026-08-20", "15:30")
    assert combined is not None
    assert combined.year == 2026
    assert combined.month == 8
    assert combined.day == 20
