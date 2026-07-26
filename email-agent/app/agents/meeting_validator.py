import re
from typing import Dict, Optional, Tuple

PLATFORM_PATTERNS = [
    ("Google Meet", r"https://meet\.google\.com/[a-z0-9-]+"),
    ("Microsoft Teams", r"https://teams\.(microsoft|live)\.com/[^\s\"'>]+"),
    ("Zoom", r"https://([a-z0-9\-]+\.)?zoom\.us/(j|my|w)/[^\s\"'>]+"),
    ("Cisco Webex", r"https://([a-z0-9\-]+\.)?webex\.com/[^\s\"'>]+"),
    ("Skype", r"https://join\.skype\.com/[^\s\"'>]+"),
    ("Google Forms", r"https://(forms\.gle|docs\.google\.com/forms)/[^\s\"'>]+"),
    ("Microsoft Forms", r"https://forms\.(office|microsoft)\.com/[^\s\"'>]+"),
    ("Typeform", r"https://[a-z0-9\-]+\.typeform\.com/[^\s\"'>]+"),
    ("Jotform", r"https://(form\.)?jotform\.com/[^\s\"'>]+"),
    ("SurveyMonkey", r"https://[a-z0-9\-]+\.surveymonkey\.com/[^\s\"'>]+"),
]


def extract_meeting_link(text: str) -> Tuple[Optional[str], Optional[str]]:
    for platform_name, pattern in PLATFORM_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0), platform_name
    return None, None


def validate_meeting(email: dict) -> Dict[str, object]:
    subject = email.get("subject", "")
    body = email.get("body", "")
    full_text = f"{subject}\n{body}"

    link, platform = extract_meeting_link(full_text)

    # Check for calendar invitations, forms, or registration links
    has_calendar_invite = "BEGIN:VCALENDAR" in full_text or ".ics" in full_text.lower()
    has_form_keyword = any(kw in full_text.lower() for kw in ["google form", "ms form", "feedback form", "registration form", "survey form", "fill out", "rsvp"])
    is_valid = bool(link) or has_calendar_invite or has_form_keyword

    return {
        "valid": is_valid,
        "platform": platform or ("Google Calendar" if has_calendar_invite else ("Registration Form" if has_form_keyword else None)),
        "meeting_link": link,
    }
