import os
import subprocess
import sys
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pydantic.fields import PrivateAttr
import google.generativeai as genai

load_dotenv()

from app.agents.database_manager import MeetingStore
from app.agents.duplicate_detector import find_duplicate, merge_meeting
from app.agents.email_classifier import classify_email
from app.agents.email_watcher import watch_inbox
from app.agents.information_extractor import extract_meeting
from app.agents.meeting_validator import validate_meeting
from app.agents.notification_agent import NotificationAgent
from app.gmail_oauth import get_auth_url, exchange_code
from app.database import SessionLocal, MeetingReport, MeetingTranscript

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


@app.get("/gmail/oauth")
def get_gmail_oauth_url() -> dict:
    try:
        url = get_auth_url()
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/oauth/callback")
def oauth_callback(code: str):
    try:
        exchange_code(code)
        return HTMLResponse(
            """
            <div style="font-family: sans-serif; text-align: center; margin-top: 50px;">
                <h1 style="color: #4f46e5;">Authentication Successful!</h1>
                <p>Your Gmail account has been successfully connected to the agent.</p>
                <p>You can close this window and refresh your dashboard.</p>
                <script>setTimeout(function(){ window.close(); }, 3000);</script>
            </div>
            """
        )
    except Exception as e:
        return HTMLResponse(f"<h1>OAuth Error</h1><p>{str(e)}</p>")



@app.get("/meetings/{meeting_id}/summary")
def get_meeting_summary(meeting_id: str):
    with SessionLocal() as session:
        report = session.query(MeetingReport).filter(MeetingReport.meeting_id == meeting_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Summary not found. Meeting agent might still be processing.")
        return {"summary": report.summary}


class AskRequest(BaseModel):
    question: str


@app.post("/meetings/{meeting_id}/ask")
def ask_meeting_question(meeting_id: str, payload: AskRequest):
    with SessionLocal() as session:
        report = session.query(MeetingReport).filter(MeetingReport.meeting_id == meeting_id).first()
        transcript = session.query(MeetingTranscript).filter(MeetingTranscript.meeting_id == meeting_id).first()
        
        if not report and not transcript:
            raise HTTPException(status_code=404, detail="No transcript or summary available to answer questions.")
        
        context = ""
        if report:
            context += f"Meeting Summary:\n{report.summary}\n\n"
        if transcript:
            context += f"Full Transcript:\n{transcript.transcript}\n\n"
            
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured in .env.")
            
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-3-flash-preview")
            prompt = (
                f"You are a Meeting Intelligence Assistant. Use the following context from a recent team meeting "
                f"to answer the user's question clearly and accurately.\n\n"
                f"{context}\n\n"
                f"User Question: {payload.question}\n"
            )
            response = model.generate_content(prompt)
            return {"answer": response.text.strip()}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM Error: {str(e)}")
