import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from app.agents.database_manager import MeetingStore
from app.agents.duplicate_detector import find_duplicate, merge_meeting
from app.agents.email_classifier import classify_email
from app.agents.email_watcher import watch_inbox
from app.agents.information_extractor import extract_meeting
from app.agents.meeting_validator import validate_meeting
from app.agents.notification_agent import NotificationAgent
from app.gmail_oauth import run_oauth_flow

app = FastAPI(title="AI Meeting Intelligence Agent")
store = MeetingStore()
notification_agent = NotificationAgent(store)


@app.get("/", response_class=HTMLResponse)
def read_dashboard() -> str:
    template_path = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/meetings")
def list_meetings() -> list[dict]:
    return store.list_meetings()


@app.post("/meetings/manual")
def add_manual_meeting(data: dict) -> dict:
    saved = store.add_meeting(data)
    return saved


@app.delete("/meetings")
def clear_meetings() -> dict:
    store.clear_all_meetings()
    return {"message": "All meetings cleared successfully"}


@app.get("/notifications")
def get_notifications() -> list[dict]:
    return notification_agent.get_upcoming_notifications()


@app.post("/sync")
def sync_meetings() -> list[dict]:
    emails = watch_inbox()
    processed_results = []

    for email in emails:
        classification = classify_email(email)
        if classification["is_meeting"]:
            validation = validate_meeting(email)
            if validation["valid"]:
                extracted = extract_meeting(email)
                if validation.get("meeting_link"):
                    extracted["meeting_link"] = validation["meeting_link"]
                    extracted["meeting_url"] = validation["meeting_link"]
                if validation.get("platform"):
                    extracted["platform"] = validation["platform"]

                duplicate = find_duplicate(store, extracted)
                if duplicate:
                    merged = merge_meeting(duplicate, extracted)
                    saved = store.add_meeting(merged)
                else:
                    saved = store.add_meeting(extracted)

                processed_results.append(saved)

    return processed_results


@app.post("/gmail/oauth")
def gmail_oauth() -> dict:
    return run_oauth_flow()
