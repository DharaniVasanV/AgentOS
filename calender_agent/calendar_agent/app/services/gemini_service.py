import os
import re
import json
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

ENV_PATH = r"e:\meeting-agent\.env"
load_dotenv(ENV_PATH, override=True)

from ..schemas.gemini import CalendarIntent

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

class GeminiService:
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.client = None
        self.genai = None
        self.model = None

        if self.api_key and self.api_key.strip() and not self.api_key.startswith("your_"):
            try:
                # Try google-genai or google-generativeai SDK
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.genai = genai
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                logger.info("Gemini API initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini SDK: {e}")
                self.genai = None
                self.model = None

    def analyze_manual_input(self, text: str, reference_datetime: Optional[str] = None) -> Any:
        """
        Analyzes natural language manual input string according to strict AGENTOS Manual Input rules.
        """
        from ..schemas.manual_event import ManualEventAnalysisResponse

        if self.genai and self.model:
            try:
                result = self._analyze_manual_with_gemini(text, reference_datetime)
                if result:
                    return result
            except Exception as e:
                logger.error(f"Gemini manual input analysis failed: {e}. Using rule-based analyzer.")

        return self._analyze_manual_rule_based(text, reference_datetime)

    def _analyze_manual_with_gemini(self, text: str, reference_datetime: Optional[str] = None) -> Any:
        from ..schemas.manual_event import ManualEventAnalysisResponse
        from datetime import datetime, timezone as tz
        
        if not reference_datetime:
            reference_datetime = datetime.now(tz.utc).isoformat()

        prompt = f"""
You are the AGENTOS Calendar Agent AI for Manual Input Analysis.
Analyze the provided user input and convert it into a structured calendar event JSON matching the exact schema.

CURRENT REFERENCE TIMESTAMP:
{reference_datetime} (Current Date: 2026-07-29 Wednesday)

CRITICAL RULES:
1. Never invent missing dates, times, meeting links, or participants.
2. STRICT PRIORITY RULE:
   - Do NOT determine or infer priority independently!
   - If priority is explicitly provided in the input (e.g. "Priority: High", "Priority: Urgent"), preserve it exactly as provided (e.g. "High", "Urgent").
   - If priority is NOT explicitly provided by the user, set "priority": null.
3. SUPPORTED EVENT TYPES (Must match one of):
   Meeting, Task, Deadline, Hackathon, Internship, Certification, Interview, Exam, Assignment, Project, Personal, Bill, Reminder, Other
4. DATE & TIME RULES:
   - Natural language dates (Today=2026-07-29, Tomorrow=2026-07-30, Friday=2026-07-31, Next Monday=2026-08-03, August 15=2026-08-15, September 5=2026-09-05).
   - Convert start_date / end_date / deadline to "YYYY-MM-DD" or null.
   - Convert start_time / end_time to "HH:MM" 24-hour format or null.
   - If a required date/time is ambiguous, set "needs_clarification": true, "status": "needs_clarification", and populate "missing_fields": ["start_date", "start_time"].
5. REMINDER RULES:
   - Preserve explicit reminder instructions (e.g. "Remind me 30 minutes before" -> [{{"value": 30, "unit": "minutes", "before": "start"}}]).
   - "Remind me one day before" -> [{{"value": 1, "unit": "days", "before": "start"}}].
   - If no explicit reminder instruction, return [].
6. OUTPUT STRICT FORMAT:
   Return ONLY raw valid JSON without markdown code fences matching:

{{
  "status": "ready",
  "event": {{
    "title": "...",
    "event_type": "...",
    "description": null,
    "start_date": null,
    "start_time": null,
    "end_date": null,
    "end_time": null,
    "deadline": null,
    "location": null,
    "meeting_url": null,
    "priority": null,
    "participants": [],
    "reminders": [],
    "recurrence": null,
    "source": null
  }},
  "needs_clarification": false,
  "missing_fields": []
}}

USER INPUT TEXT:
"{text}"
"""
        response = self.model.generate_content(prompt)
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```[a-zA-Z]*\n?", "", raw_text)
            raw_text = re.sub(r"\n?```$", "", raw_text)
            raw_text = raw_text.strip()

        data = json.loads(raw_text)
        return ManualEventAnalysisResponse(**data)

    def _analyze_manual_rule_based(self, text: str, reference_datetime: Optional[str] = None) -> Any:
        from ..schemas.manual_event import ManualEventAnalysisResponse, ManualEventDetail
        from datetime import datetime, timedelta, timezone as tz

        clean_text = text.strip()

        # 1. Extract Meeting URL if present
        meeting_url = None
        url_match = re.search(r'https?://[^\s]+', clean_text)
        if url_match:
            meeting_url = url_match.group(0)

        # 2. Extract Priority ONLY if explicitly provided
        priority = None
        prio_match = re.search(r'(?:priority|prio)\s*:\s*([a-zA-Z]+)', clean_text, re.IGNORECASE)
        if prio_match:
            priority = prio_match.group(1).capitalize()
        else:
            m = re.search(r'\b(high|urgent|medium|low)\s+priority\b', clean_text, re.IGNORECASE)
            if m:
                priority = m.group(1).capitalize()

        # 3. Detect Event Type
        event_type = "Other"
        text_lower = clean_text.lower()
        if "hackathon" in text_lower:
            event_type = "Hackathon"
        elif "interview" in text_lower:
            event_type = "Interview"
        elif "assignment" in text_lower:
            event_type = "Assignment"
        elif "exam" in text_lower:
            event_type = "Exam"
        elif "internship" in text_lower:
            event_type = "Internship"
        elif "certification" in text_lower:
            event_type = "Certification"
        elif "meeting" in text_lower or "google meet" in text_lower or "sync" in text_lower:
            event_type = "Meeting"
        elif "deadline" in text_lower:
            event_type = "Deadline"
        elif "presentation" in text_lower or "submit" in text_lower or "task" in text_lower:
            event_type = "Task"
        elif "bill" in text_lower:
            event_type = "Bill"
        elif "reminder" in text_lower:
            event_type = "Reminder"
        elif "project" in text_lower:
            event_type = "Project"

        # 4. Dates and Times
        ref_dt = datetime(2026, 7, 29) # Default base 2026-07-29
        start_date = None
        end_date = None
        deadline = None
        start_time = None
        end_time = None

        if "tomorrow" in text_lower:
            target_dt = ref_dt + timedelta(days=1)
            start_date = target_dt.strftime("%Y-%m-%d")
        elif "today" in text_lower or "tonight" in text_lower:
            start_date = ref_dt.strftime("%Y-%m-%d")
        elif "friday" in text_lower:
            start_date = "2026-07-31"
        else:
            m_date = re.search(r'\b(january|february|march|april|may|june|july|august|september|october|november|december|aug|sept|sep)\s+(\d{1,2})\b', text_lower)
            if m_date:
                m_name = m_date.group(1)[:3]
                day_num = int(m_date.group(2))
                months = {"jan":1, "feb":2, "mar":3, "apr":4, "may":5, "jun":6, "jul":7, "aug":8, "sep":9, "oct":10, "nov":11, "dec":12}
                month_num = months.get(m_name, 8)
                start_date = f"2026-{month_num:02d}:{day_num:02d}".replace(':', '-')

        if "deadline" in text_lower or "by " in text_lower:
            if start_date:
                deadline = start_date

        time_range = re.search(r'from\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)', text_lower)
        if time_range:
            h1 = int(time_range.group(1))
            m1 = int(time_range.group(2) or 0)
            p1 = time_range.group(3)
            if p1 == "pm" and h1 < 12: h1 += 12
            if p1 == "am" and h1 == 12: h1 = 0
            start_time = f"{h1:02d}:{m1:02d}"

            h2 = int(time_range.group(4))
            m2 = int(time_range.group(5) or 0)
            p2 = time_range.group(6)
            if p2 == "pm" and h2 < 12: h2 += 12
            if p2 == "am" and h2 == 12: h2 = 0
            end_time = f"{h2:02d}:{m2:02d}"
        else:
            single_time = re.search(r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)', text_lower)
            if single_time:
                h = int(single_time.group(1))
                m = int(single_time.group(2) or 0)
                p = single_time.group(3)
                if p == "pm" and h < 12: h += 12
                if p == "am" and h == 12: h = 0
                start_time = f"{h:02d}:{m:02d}"

        # 5. Extract Reminders
        reminders = []
        if "remind me one day before" in text_lower or "remind me 1 day before" in text_lower:
            reminders.append({"value": 1, "unit": "days", "before": "start"})
        else:
            rem_match = re.search(r'remind me\s+(\d+)?\s*(minute|minutes|hour|hours|day|days)?\s*before', text_lower)
            if rem_match:
                val_str = rem_match.group(1)
                val = int(val_str) if val_str else 1
                unit = rem_match.group(2) or "days"
                if "minute" in unit: unit = "minutes"
                elif "hour" in unit: unit = "hours"
                elif "day" in unit: unit = "days"
                reminders.append({"value": val, "unit": unit, "before": "start"})

        # 6. Title
        title_raw = clean_text.split('\n')[0]
        title_raw = re.sub(r'https?://[^\s]+', '', title_raw)
        title_raw = re.sub(r'(?:priority|prio)\s*:\s*[a-zA-Z]+', '', title_raw, flags=re.IGNORECASE)
        title_raw = title_raw.strip(". ")
        title = title_raw if title_raw else "Calendar Event"

        needs_clarification = False
        missing_fields = []
        if not start_date and not deadline:
            needs_clarification = True
            missing_fields.append("start_date")

        status = "needs_clarification" if needs_clarification else "ready"

        return ManualEventAnalysisResponse(
            status=status,
            event=ManualEventDetail(
                title=title,
                event_type=event_type,
                description=clean_text if clean_text != title else None,
                start_date=start_date,
                start_time=start_time,
                end_date=end_date or start_date,
                end_time=end_time,
                deadline=deadline,
                location=None,
                meeting_url=meeting_url,
                priority=priority, # NULL if not provided!
                participants=[],
                reminders=reminders,
                recurrence=None,
                source=None
            ),
            needs_clarification=needs_clarification,
            missing_fields=missing_fields
        )


    def schedule_custom_event(self, user_input: Dict[str, Any]) -> CalendarIntent:
        """
        Parses raw user input (date, event name, prompt text) into a structured CalendarIntent using Gemini AI.
        """
        if self.genai and self.model:
            try:
                intent = self._schedule_custom_with_gemini(user_input)
                if intent:
                    return intent
            except Exception as e:
                logger.error(f"Gemini custom scheduling failed: {e}. Falling back to rule-based parser.")

        return self._schedule_custom_rule_based(user_input)

    def _schedule_custom_with_gemini(self, user_input: Dict[str, Any]) -> Optional[CalendarIntent]:
        prompt = f"""
You are Google Gemini Calendar AI Agent.
The user wants to schedule an event. Normalize their request into a clean CalendarIntent JSON object.

RULES:
1. Extract or infer event title, start_datetime (ISO-8601 e.g. 2026-08-05T14:30:00), end_datetime (ISO-8601 e.g. 2026-08-05T15:30:00), event_type, priority, description, and location.
2. If start_datetime is provided, ensure it is formatted as ISO-8601.
3. Return ONLY raw JSON without markdown formatting.

User Request Input:
{json.dumps(user_input, indent=2)}
"""
        response = self.model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            text = text.strip()

        data = json.loads(text)
        return CalendarIntent(**data)

    def _schedule_custom_rule_based(self, input_data: Dict[str, Any]) -> CalendarIntent:
        title = input_data.get("title") or input_data.get("prompt") or "Scheduled Event"
        start_str = input_data.get("start_datetime") or input_data.get("date")
        desc = input_data.get("description") or input_data.get("prompt")
        event_type = (input_data.get("event_type") or "MEETING").upper()
        priority = (input_data.get("priority") or "MEDIUM").upper()
        location = input_data.get("location")

        if priority not in ("LOW", "MEDIUM", "HIGH", "URGENT"):
            priority = "MEDIUM"

        end_str = input_data.get("end_datetime")
        deadline_str = input_data.get("deadline")

        # Format start_datetime properly
        if start_str and "T" in start_str and len(start_str) == 16:
            start_str = f"{start_str}:00"

        if start_str and not end_str:
            from datetime import datetime, timedelta
            from .date_service import DateService
            parsed = DateService.parse_datetime(start_str)
            if parsed:
                end_str = (parsed + timedelta(hours=1)).isoformat()

        reminders = [1440, 60] if priority in ("HIGH", "URGENT") else [30, 10]

        return CalendarIntent(
            title=title,
            description=desc,
            event_type=event_type,
            start_datetime=start_str,
            end_datetime=end_str,
            deadline=deadline_str,
            all_day=input_data.get("all_day", False),
            priority=priority,
            location=location,
            meeting_url=input_data.get("meeting_url"),
            source_type="user_input",
            source_id=f"usr_{int(os.getenv('TIMESTAMP', '100'))}",
            suggested_reminders=reminders,
            confidence=0.98
        )

    def normalize_record(self, raw_record: Dict[str, Any], source_type: str) -> CalendarIntent:
        """
        Parses raw incoming record (meeting_tasks or applications) into structured CalendarIntent.
        Uses Gemini API if available, with robust deterministic fallback parsing.
        """
        if self.genai and self.model:
            try:
                intent = self._normalize_with_gemini(raw_record, source_type)
                if intent:
                    return intent
            except Exception as e:
                logger.error(f"Gemini normalization failed: {e}. Falling back to rule-based parser.")

        return self._normalize_rule_based(raw_record, source_type)


    def _normalize_with_gemini(self, raw_record: Dict[str, Any], source_type: str) -> Optional[CalendarIntent]:
        prompt = f"""
You are an expert Calendar Agent AI for an OS system.
Your job is to normalize unstructured scheduling data into structured JSON matching the CalendarIntent schema.

IMPORTANT RULES:
1. DO NOT invent dates or times. If no reliable date exists in the input, set start_datetime=null, end_datetime=null, deadline=null.
2. Output ONLY raw JSON matching this format without markdown wrapping:
{{
    "title": "Clean Event Title",
    "description": "Description text or null",
    "event_type": "MEETING" | "TASK_DEADLINE" | "APPLICATION_DEADLINE" | "HACKATHON" | "INTERNSHIP" | "CERTIFICATION" | "GENERAL_EVENT",
    "start_datetime": "ISO-8601 string or null",
    "end_datetime": "ISO-8601 string or null",
    "deadline": "ISO-8601 string or null",
    "all_day": false,
    "priority": "LOW" | "MEDIUM" | "HIGH" | "URGENT",
    "location": "Location string or null",
    "meeting_url": "URL or null",
    "source_type": "{source_type}",
    "source_id": "record ID",
    "suggested_reminders": [1440, 60],
    "confidence": 0.95
}}

Current Input Record ({source_type}):
{json.dumps(raw_record, indent=2)}
"""
        response = self.model.generate_content(prompt)
        text = response.text.strip()
        
        # Remove potential markdown code fences ```json ... ```
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            text = text.strip()

        data = json.loads(text)
        return CalendarIntent(**data)

    def _normalize_rule_based(self, record: Dict[str, Any], source_type: str) -> CalendarIntent:
        """
        Deterministic rule-based fallback parser guaranteeing schema compliance.
        """
        if source_type == "meeting_tasks":
            source_id = str(record.get("id") or record.get("task_id") or "task_unknown")
            title = record.get("title") or record.get("task") or "Meeting Task"
            desc = record.get("description")
            priority = (record.get("priority") or "MEDIUM").upper()
            if priority not in ("LOW", "MEDIUM", "HIGH", "URGENT"):
                priority = "MEDIUM"

            due_date = record.get("due_date") or record.get("deadline")
            due_time = record.get("due_time")
            deadline_str = None
            if due_date:
                if "T" in str(due_date):
                    deadline_str = str(due_date)
                elif due_time:
                    deadline_str = f"{due_date}T{due_time}:00"
                else:
                    deadline_str = f"{due_date}T17:00:00"

            reminders = [1440, 60] if priority in ("HIGH", "URGENT") else [60]

            return CalendarIntent(
                title=title,
                description=desc,
                event_type="TASK_DEADLINE",
                start_datetime=None,
                end_datetime=None,
                deadline=deadline_str,
                all_day=False,
                priority=priority,
                location=None,
                meeting_url=None,
                source_type="meeting_tasks",
                source_id=source_id,
                suggested_reminders=reminders,
                confidence=0.90
            )

        elif source_type == "applications":
            source_id = str(record.get("application_id") or record.get("id") or "app_unknown")
            title = record.get("title") or "Application Event"
            category = (record.get("category") or "GENERAL_EVENT").upper()
            
            event_type = "APPLICATION_DEADLINE"
            if category in ("HACKATHON", "INTERNSHIP", "CERTIFICATION"):
                event_type = category

            desc = record.get("description") or f"Organization: {record.get('organization', 'N/A')}"
            priority = (record.get("priority") or "HIGH").upper()
            if priority not in ("LOW", "MEDIUM", "HIGH", "URGENT"):
                priority = "HIGH"

            reg_deadline = record.get("registration_deadline")
            start_date = record.get("event_start_date") or record.get("event_date")
            end_date = record.get("event_end_date")

            reminders = [4320, 1440, 60]

            return CalendarIntent(
                title=title,
                description=desc,
                event_type=event_type,
                start_datetime=start_date,
                end_datetime=end_date,
                deadline=reg_deadline,
                all_day=False,
                priority=priority,
                location=record.get("location"),
                meeting_url=record.get("registration_url"),
                source_type="applications",
                source_id=source_id,
                suggested_reminders=reminders,
                confidence=0.95
            )

        else:
            return CalendarIntent(
                title=record.get("title", "General Event"),
                description=record.get("description"),
                event_type="GENERAL_EVENT",
                start_datetime=record.get("start_datetime"),
                end_datetime=record.get("end_datetime"),
                deadline=record.get("deadline"),
                all_day=record.get("all_day", False),
                priority=record.get("priority", "MEDIUM"),
                location=record.get("location"),
                meeting_url=record.get("meeting_url"),
                source_type=source_type,
                source_id=str(record.get("id", "manual")),
                suggested_reminders=[60],
                confidence=0.85
            )
