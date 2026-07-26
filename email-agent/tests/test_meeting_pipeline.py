import os

# Isolate unit tests to an in-memory SQLite database so they never touch meetings.db
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.agents.database_manager import MeetingStore
from app.agents.duplicate_detector import find_duplicate, merge_meeting
from app.agents.email_classifier import classify_email
from app.agents.information_extractor import extract_meeting
from app.agents.meeting_validator import validate_meeting, extract_meeting_link
from app.agents.notification_agent import NotificationAgent


def test_pipeline_extracts_and_deduplicates_meetings():
    sample_email = {
        "id": "email-101",
        "subject": "Quarterly Planning Review 2026-07-25",
        "sender": "alex@example.com",
        "body": "Join meeting at https://meet.google.com/abc-defg-hij at 09:00 UTC",
        "timestamp": "2026-07-25T09:00:00",
    }

    classification = classify_email(sample_email)
    assert classification["is_meeting"] is True

    validation = validate_meeting(sample_email)
    assert validation["valid"] is True

    extracted = extract_meeting(sample_email)
    assert extracted["title"] == "Quarterly Planning Review 2026-07-25"
    assert extracted["meeting_link"] == "https://meet.google.com/abc-defg-hij"

    store = MeetingStore()
    first_record = store.add_meeting(extracted)

    duplicate = find_duplicate(store, extracted)
    assert duplicate is not None

    merged = merge_meeting(first_record, {**extracted, "start_time": "11:00"})
    assert merged["status"] == "updated"


def test_multi_platform_validation():
    zoom_text = "Join Zoom Meeting https://us02web.zoom.us/j/123456789"
    link, platform = extract_meeting_link(zoom_text)
    assert platform == "Zoom"
    assert "zoom.us" in link

    teams_text = "Join Microsoft Teams Meeting https://teams.microsoft.com/l/meetup-join/123"
    link, platform = extract_meeting_link(teams_text)
    assert platform == "Microsoft Teams"

    webex_text = "Join Cisco Webex https://company.webex.com/meet/user"
    link, platform = extract_meeting_link(webex_text)
    assert platform == "Cisco Webex"

    gforms_text = "Please fill out this survey https://forms.gle/xyz123"
    link, platform = extract_meeting_link(gforms_text)
    assert platform == "Google Forms"
    assert "forms.gle" in link

    msforms_text = "Submit feedback at https://forms.office.com/r/abc456"
    link, platform = extract_meeting_link(msforms_text)
    assert platform == "Microsoft Forms"


def test_notifications():
    store = MeetingStore()
    store.add_meeting({
        "title": "Cancelled Sync",
        "status": "cancelled",
        "organizer": "alice@example.com"
    })
    agent = NotificationAgent(store)
    notifs = agent.get_upcoming_notifications()
    assert len(notifs) >= 1
    assert any("Cancelled" in n["title"] for n in notifs)
