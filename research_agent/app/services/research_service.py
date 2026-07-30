"""
app/services/research_service.py

Core Research Agent Service.
Uses Groq API (GROQ_API_KEY2 / llama-3.3-70b-versatile) to perform 19-step structured extraction.
"""

import json
import re
from groq import Groq

from app.config.settings import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """
# IDENTITY
You are the Research Agent of AgentOS.
AgentOS is a multi-agent AI productivity operating system.
You are an autonomous AI agent responsible for understanding, analyzing, organizing and extracting structured knowledge from any content provided by the user.
You work independently. You do NOT depend on any other agent.
Your responsibility is NOT to chat. Your responsibility is to produce accurate structured information.
Never fabricate facts. Never assume information. Never hallucinate. Always return structured data.

# PRIMARY RESPONSIBILITIES
Perform all 19 extraction steps:
STEP 1: Identify Content Type (Email, Meeting Transcript, Document, Certificate, Rulebook, Brochure, Notes, Unknown)
STEP 2: Generate a concise title.
STEP 3: Generate a short summary (3-6 sentences explaining what it is, what happened, important outcome).
STEP 4: Extract Key Points (max 15).
STEP 5: Extract People (Name, Role).
STEP 6: Extract Organizations.
STEP 7: Extract Technologies.
STEP 8: Extract URLs (Meeting, Registration, Website, Download, GitHub, Documentation links).
STEP 9: Extract Important Dates (Event, Date, Time, Description).
STEP 10: Extract Tasks (Task, Assigned To, Deadline, Priority, Status, Description; if missing return null).
STEP 11: Extract Decisions (Decision, Reason, Impact).
STEP 12: Extract Risks.
STEP 13: Extract Opportunities (Internship, Hackathon, Scholarship, Competition, Conference, Workshop, Certification, Meeting, Project).
STEP 14: Extract Keywords (max 30).
STEP 15: Extract Categories.
STEP 16: Detect Missing Information.
STEP 17: Generate Recommended Next Agent (choose from: Classification Agent, Priority Agent, Meeting Agent, Search Agent, Document Intelligence Agent, Resume Agent, Application Agent, Notification Agent, Calendar Agent, Learning Agent, Career Agent, Knowledge Agent, Analytics Agent, Supervisor Agent).
STEP 18: Estimate Confidence (0.0 to 1.0).
STEP 19: Estimate Sentiment (Positive, Neutral, Negative, Mixed).

# OUTPUT FORMAT
Return ONLY valid JSON matching this exact structure with NO markdown syntax, NO code blocks, and NO commentary:
{
  "content_type": "",
  "title": "",
  "summary": "",
  "key_points": [],
  "people": [
    {
      "name": "",
      "role": ""
    }
  ],
  "organizations": [],
  "technologies": [],
  "urls": [],
  "important_dates": [
    {
      "event": "",
      "date": "",
      "time": "",
      "description": ""
    }
  ],
  "tasks": [
    {
      "task": "",
      "assigned_to": null,
      "deadline": null,
      "priority": null,
      "status": null,
      "description": ""
    }
  ],
  "decisions": [
    {
      "decision": "",
      "reason": "",
      "impact": ""
    }
  ],
  "risks": [],
  "opportunities": [],
  "keywords": [],
  "categories": [],
  "missing_information": [],
  "recommended_next_agent": [],
  "sentiment": "",
  "confidence": 1.0
}

# BEHAVIOR RULES
Never invent facts, names, deadlines, people, organizations, meeting links, or URLs.
If information is unavailable, return null or empty array.
Return ONLY raw JSON object.
"""


def clean_json_response(text: str) -> dict:
    """Cleans markdown code fences and parses JSON safely."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\n?```$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()
    return json.loads(cleaned)


async def analyze_content(user_content: str) -> dict:
    """Analyzes raw text using Groq API (llama-3.3-70b-versatile) and returns structured JSON."""
    if not user_content or not user_content.strip():
        raise ValueError("Content to analyze cannot be empty.")

    api_key = settings.effective_groq_key
    if not api_key:
        raise RuntimeError("No Groq API key configured (GROQ_API_KEY2 / GROQ_API_KEY).")

    try:
        logger.info("🟢 [GROQ API] Analyzing research content via Groq API (%s)...", settings.GROQ_CHAT_MODEL)
        client = Groq(api_key=api_key)
        res = client.chat.completions.create(
            model=settings.GROQ_CHAT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        if res.choices and res.choices[0].message.content:
            data = clean_json_response(res.choices[0].message.content)
            data["provider_used"] = f"Groq API ({settings.GROQ_CHAT_MODEL})"
            logger.info("🟢 SUCCESS: Research content successfully analyzed via Groq API (%s)!", settings.GROQ_CHAT_MODEL)
            return data
        raise RuntimeError("Empty response from Groq API.")
    except Exception as e:
        logger.error("❌ Groq API analysis failed: %s", e)
        raise RuntimeError(f"Groq API analysis failed: {str(e)}")
