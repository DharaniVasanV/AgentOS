import json
import os
from typing import Dict

try:
    import google.generativeai as genai
except ImportError:
    genai = None


def classify_email(email: dict) -> Dict[str, object]:
    subject = email.get("subject", "")
    body = email.get("body", "")
    text = f"Subject: {subject}\nBody: {body}"

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key and genai:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = (
                "Analyze if the following email is a meeting invitation, event discussion, calendar request, or circulated form/survey/registration. "
                "Respond ONLY with a valid JSON object containing keys: 'is_meeting' (boolean) and 'category' (string: meeting, form, newsletter, promotional, personal, spam).\n\n"
                f"Email:\n{text}"
            )
            response = model.generate_content(prompt)
            content = response.text.strip()
            if content.startswith("```json"):
                content = content[7:-3].strip()
            parsed = json.loads(content)
            return {
                "is_meeting": bool(parsed.get("is_meeting")),
                "category": str(parsed.get("category", "meeting" if parsed.get("is_meeting") else "other")),
            }
        except Exception:
            pass

    # Heuristic Fallback
    text_lower = text.lower()
    meeting_keywords = [
        "meeting", "join", "schedule", "review", "call", "webinar", 
        "invitation", "huddle", "sync", "standup", "conference", "demo",
        "form", "forms", "survey", "rsvp", "registration", "feedback", "fill out"
    ]
    has_platform_url = any(domain in text_lower for domain in [
        "meet.google.com", "zoom.us", "teams.microsoft.com", "webex.com", "skype.com",
        "forms.gle", "forms.office.com", "forms.microsoft.com", "typeform.com", "jotform.com", "surveymonkey.com"
    ])
    is_meeting = has_platform_url or any(kw in text_lower for kw in meeting_keywords)
    
    return {
        "is_meeting": is_meeting,
        "category": "form" if any(k in text_lower for k in ["form", "survey", "rsvp"]) else ("meeting" if is_meeting else "other")
    }
