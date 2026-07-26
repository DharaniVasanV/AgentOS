import json
import os
import re
from typing import Dict
from app.agents.meeting_validator import extract_meeting_link

try:
    import google.generativeai as genai
except ImportError:
    genai = None


def extract_meeting(email: dict) -> Dict[str, object]:
    subject = email.get("subject")
    body = email.get("body", "")
    sender = email.get("sender")
    email_id = email.get("id")
    full_text = f"Subject: {subject or ''}\nSender: {sender or ''}\nBody: {body or ''}"

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key and genai:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = (
                "Extract structured meeting details from this email invitation. "
                "If a detail is not present in the email, set its value to null. "
                "Return ONLY a JSON object with keys: "
                "'title' (string or null), 'description' (string or null), 'organizer' (string or null), "
                "'platform' (string or null), 'meeting_link' (string or null), 'date' (YYYY-MM-DD or null), "
                "'start_time' (HH:MM or null), 'end_time' (HH:MM or null), "
                "'time_zone' (string or null), 'status' ('scheduled', 'updated', or 'cancelled').\n\n"
                f"Email Content:\n{full_text}"
            )
            response = model.generate_content(prompt)
            content = response.text.strip()
            if content.startswith("```json"):
                content = content[7:-3].strip()
            data = json.loads(content)
            data["email_id"] = email_id
            return data
        except Exception:
            pass

    # Heuristic Regex Extraction (Strict, No Hardcoded Mock Data)
    link, platform = extract_meeting_link(full_text)

    # Date regex
    date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", full_text)
    meeting_date = date_match.group(1) if date_match else None

    # Time regex
    time_matches = re.findall(r"\b(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)\b", full_text)
    start_time = time_matches[0] if time_matches else None
    end_time = time_matches[1] if len(time_matches) > 1 else None

    # Time zone regex
    tz_match = re.search(r"\b(UTC|GMT|EST|PST|CST|IST|EDT|PDT)\b", full_text)
    time_zone = tz_match.group(1) if tz_match else None

    # Status regex
    status = "cancelled" if subject and any(w in subject.lower() for w in ["cancel", "cancelled", "canceled"]) else "scheduled"

    return {
        "email_id": email_id,
        "title": subject or "Untitled Meeting",
        "description": body[:300] if body else None,
        "organizer": sender,
        "platform": platform,
        "meeting_link": link,
        "date": meeting_date,
        "start_time": start_time,
        "end_time": end_time,
        "time_zone": time_zone,
        "status": status,
    }
