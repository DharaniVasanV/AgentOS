"""
app/services/learning_service.py

Learning Agent Version 1.0 - 12-Step Autonomous AI Learning Mentor Engine.
"""

import json
import os
import uuid
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.db import models
from app.utils.logger import get_logger

logger = get_logger(__name__)

JSON_STORE_FILE = "e:/meeting-agent/learning_agent/data/learning_store.json"


def ensure_store_dir():
    os.makedirs(os.path.dirname(JSON_STORE_FILE), exist_ok=True)
    if not os.path.exists(JSON_STORE_FILE):
        with open(JSON_STORE_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


def load_json_store() -> List[Dict[str, Any]]:
    ensure_store_dir()
    try:
        with open(JSON_STORE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_json_store(records: List[Dict[str, Any]]):
    ensure_store_dir()
    with open(JSON_STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)


async def generate_learning_plan(
    raw_payload: Dict[str, Any],
    session: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """
    Executes the 12-Step Learning Agent Mentor Workflow.
    """
    # Extract Input Parameters
    career_goal = raw_payload.get("career_goal") or raw_payload.get("learning_goal")
    skills = raw_payload.get("skills")
    resume = raw_payload.get("resume")
    job_description = raw_payload.get("job_description")
    technologies = raw_payload.get("technologies") or raw_payload.get("technologies_to_learn")
    knowledge_level = raw_payload.get("knowledge_level") or raw_payload.get("current_knowledge_level", "Beginner/Intermediate")
    study_time = raw_payload.get("study_time") or raw_payload.get("available_study_time", "10-15 hours/week")
    learning_style = raw_payload.get("learning_style") or raw_payload.get("preferred_learning_style", "Hands-on Project Based")
    existing_certs = raw_payload.get("existing_certifications") or []

    # STEP 1 Validation: Require Goal or Skills/Technologies
    if not career_goal and not technologies and not skills:
        logger.warning("Step 1 Validation Failed: Insufficient learning information.")
        return {
            "status": "failed",
            "reason": "Insufficient learning information."
        }

    user_id = raw_payload.get("user_id", "dharanivasan")

    # Construct Groq Prompt using GROQ_API_KEY6
    system_prompt = """You are the Learning Agent Version 1.0 of AgentOS, an autonomous AI Learning Mentor.
Your mission is to analyze the user's learning parameters and construct a comprehensive, factual 12-step learning plan and roadmap.

CRITICAL RULES:
1. Never invent user skills or experience.
2. Never exaggerate abilities.
3. Only recommend technologies strictly relevant to the user's career goal.
4. Always provide a realistic roadmap and encourage project-based learning.
5. You MUST return ONLY a valid JSON object matching the exact specification below.

JSON OUTPUT STRUCTURE:
{
  "status": "success",
  "career_goal": "<User Career or Learning Goal>",
  "current_level": "<Assessed Knowledge Level>",
  "missing_skills": [
    "<Missing Skill 1>", "<Missing Skill 2>"
  ],
  "learning_roadmap": {
    "immediate": ["<Goal 1>", "<Goal 2>"],
    "weekly": ["<Goal 1>", "<Goal 2>"],
    "monthly": ["<Goal 1>", "<Goal 2>"],
    "long_term": ["<Goal 1>", "<Goal 2>"]
  },
  "recommended_topics": ["<Topic 1>", "<Topic 2>", "<Topic 3>"],
  "recommended_resources": [
    {
      "title": "<Resource Title>",
      "type": "<Official Docs / Book / Video / Practice Platform / Course>",
      "difficulty": "<Beginner / Intermediate / Advanced>",
      "reason": "<Why this resource is essential for the goal>"
    }
  ],
  "practice_recommendations": [
    "<Coding Problem / Mini Project / Major Project / Lab / Assignment 1>",
    "<Project / Practice 2>"
  ],
  "recommended_certifications": ["<Cert 1>", "<Cert 2>"],
  "daily_plan": [
    "<Day 1: Topic & Practice>",
    "<Day 2: Topic & Practice>",
    "<Day 3: Topic & Practice>",
    "<Day 4: Topic & Practice>",
    "<Day 5: Topic & Practice>",
    "<Day 6: Mini Project>",
    "<Day 7: Weekly Revision & Assessment>"
  ],
  "weekly_schedule": [
    "<Week 1: Foundations & Core Concepts>",
    "<Week 2: Frameworks & Advanced Tools>",
    "<Week 3: Real-world Hands-on Project>",
    "<Week 4: Portfolio Integration & Certification Prep>"
  ],
  "progress": {
    "completed": 0,
    "remaining": 10,
    "percentage": 0.0
  },
  "next_milestone": "<Next Immediate Milestone Goal>",
  "motivation": "<Encouraging, constructive, realistic mentor advice>"
}"""

    user_prompt = f"""Target Goal: {career_goal}
Current Skills: {skills}
Resume Details: {resume}
Job Description Context: {job_description}
Technologies to Learn: {technologies}
Current Knowledge Level: {knowledge_level}
Available Study Time: {study_time}
Preferred Learning Style: {learning_style}
Existing Certifications: {existing_certs}

Generate the complete 12-Step Learning Plan in strict JSON format."""

    api_key = settings.GROQ_API_KEY6
    if not api_key:
        logger.error("GROQ_API_KEY6 is not configured in settings or .env!")
        return {
            "status": "failed",
            "reason": "GROQ_API_KEY6 missing in configuration."
        }

    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": settings.GROQ_CHAT_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"}
                }
            )

        if response.status_code != 200:
            logger.error(f"Groq API error HTTP {response.status_code}: {response.text}")
            return {"status": "failed", "reason": f"Groq API returned HTTP {response.status_code}"}

        res_data = response.json()
        raw_content = res_data["choices"][0]["message"]["content"]
        plan_json = json.loads(raw_content)

        plan_id = str(uuid.uuid4())
        plan_json["plan_id"] = plan_id
        plan_json["user_id"] = user_id
        plan_json["created_at"] = datetime.now().isoformat()

        # Step 11: Initialize Progress
        if "progress" not in plan_json or not isinstance(plan_json["progress"], dict):
            total_topics = len(plan_json.get("recommended_topics", [])) or 10
            plan_json["progress"] = {
                "completed": 0,
                "remaining": total_topics,
                "percentage": 0.0
            }

        # Save to local JSON store
        records = load_json_store()
        records.insert(0, plan_json)
        save_json_store(records)

        # Save to PostgreSQL if session is active
        if session:
            try:
                db_plan = models.LearningPlan(
                    id=uuid.UUID(plan_id),
                    user_id=user_id,
                    career_goal=plan_json.get("career_goal", str(career_goal)),
                    current_level=plan_json.get("current_level", str(knowledge_level)),
                    missing_skills=plan_json.get("missing_skills", []),
                    learning_roadmap=plan_json.get("learning_roadmap", {}),
                    recommended_topics=plan_json.get("recommended_topics", []),
                    practice_recommendations=plan_json.get("practice_recommendations", []),
                    recommended_certifications=plan_json.get("recommended_certifications", []),
                    daily_plan=plan_json.get("daily_plan", []),
                    weekly_schedule=plan_json.get("weekly_schedule", []),
                    next_milestone=plan_json.get("next_milestone", ""),
                    motivation=plan_json.get("motivation", ""),
                    created_at=datetime.now()
                )
                session.add(db_plan)

                # Save resources
                for r in plan_json.get("recommended_resources", []):
                    db_res = models.LearningResource(
                        id=uuid.uuid4(),
                        plan_id=uuid.UUID(plan_id),
                        title=r.get("title", "Resource"),
                        type=r.get("type", "Tutorial"),
                        difficulty=r.get("difficulty", "Intermediate"),
                        reason=r.get("reason", ""),
                        created_at=datetime.now()
                    )
                    session.add(db_res)

                # Save history
                db_hist = models.LearningHistory(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    career_goal=plan_json.get("career_goal", str(career_goal)),
                    status="Active",
                    progress_percentage=0.0,
                    created_at=datetime.now()
                )
                session.add(db_hist)

                await session.commit()
            except Exception as db_err:
                logger.warning(f"PostgreSQL store skipped: {db_err}")

        logger.info(f"✅ Learning Plan generated for '{career_goal}' via GROQ_API_KEY6!")
        return plan_json

    except Exception as err:
        logger.error(f"Error generating learning plan: {err}")
        return {
            "status": "failed",
            "reason": str(err)
        }


def get_all_plans() -> List[Dict[str, Any]]:
    return load_json_store()


def update_plan_progress(plan_id: str, completed_increment: int = 1) -> Dict[str, Any]:
    records = load_json_store()
    for r in records:
        if r.get("plan_id") == plan_id or r.get("id") == plan_id:
            prog = r.get("progress", {"completed": 0, "remaining": 10, "percentage": 0.0})
            completed = prog.get("completed", 0) + completed_increment
            remaining = max(0, prog.get("remaining", 10) - completed_increment)
            total = completed + remaining
            pct = round((completed / total) * 100, 1) if total > 0 else 100.0

            r["progress"] = {
                "completed": completed,
                "remaining": remaining,
                "percentage": pct
            }
            save_json_store(records)
            return {"status": "success", "plan_id": plan_id, "progress": r["progress"]}

    return {"status": "failed", "reason": "Plan not found."}


def delete_plan_record(plan_id: str) -> bool:
    records = load_json_store()
    filtered = [r for r in records if r.get("plan_id") != plan_id and r.get("id") != plan_id]
    save_json_store(filtered)
    return True
