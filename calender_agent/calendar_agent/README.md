# Calendar Agent Service | AgentOS

Standalone Calendar Agent for integration into multi-agent AgentOS architecture.

## Overview

The Calendar Agent receives/reads pre-processed records from other agents:
1. `meeting_tasks` (from Meeting Notes / Transcripts Agent)
2. `applications` (from Hackathon / Internship / Certification Processing Agent)

It standardizes inputs using Google Gemini API structured extraction (`CalendarIntent`), validates dates, prevents duplicate Google Calendar events, and presents a sleek dashboard for schedule management.

---

## Features

- **Google Gemini API Normalization**: Extracts structured `CalendarIntent` schemas from unstructured task inputs.
- **Date & Deadline Validation**: Programmatically validates timestamps and prevents creation of invalid events.
- **Duplicate Prevention Engine**: Unique index constraints and field diff comparison guarantee zero event duplication.
- **Google Calendar API OAuth 2.0**: Backend OAuth authentication with Fernet token encryption.
- **Configurable Reminder Rules**: Automatic default reminder intervals per event type & priority level.
- **Sleek Vanilla Dashboard**: Interactive month calendar, today's events, upcoming deadlines, status telemetry, and modal viewer.

---

## File Structure

```
calendar_agent/
│
├── app/
│   ├── main.py
│   │
│   ├── agent/
│   │   └── calendar_agent.py
│   │
│   ├── services/
│   │   ├── calendar_service.py
│   │   ├── google_calendar_service.py
│   │   ├── gemini_service.py
│   │   ├── sync_service.py
│   │   ├── reminder_service.py
│   │   └── date_service.py
│   │
│   ├── database/
│   │   ├── database.py
│   │   ├── models.py
│   │   └── repository.py
│   │
│   ├── schemas/
│   │   ├── calendar.py
│   │   └── gemini.py
│   │
│   ├── api/
│   │   ├── calendar_routes.py
│   │   └── auth_routes.py
│   │
│   ├── auth/
│   │   └── google_oauth.py
│   │
│   ├── templates/
│   │   ├── dashboard.html
│   │   └── event_details.html
│   │
│   └── static/
│       ├── css/
│       │   └── style.css
│       └── js/
│           └── calendar.js
│
├── mock_data/
│   ├── meeting_tasks.json
│   └── applications.json
│
├── tests/
│   ├── test_calendar_agent.py
│   ├── test_sync.py
│   ├── test_dates.py
│   └── test_duplicate_prevention.py
│
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Running the Calendar Agent

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in credentials as needed:
```bash
cp .env.example .env
```

### 3. Run Pytest Suite
```bash
pytest calendar_agent/tests
```

### 4. Start Server
```bash
uvicorn calendar_agent.app.main:app --reload --port 8005
```
Access dashboard at [http://localhost:8005](http://localhost:8005).
