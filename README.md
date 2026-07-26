# 🤖 AI Meeting Assistant

> **An Autonomous AI System for Email-Based Meeting Detection, Automatic Meeting Attendance, Intelligent Transcription, and AI-Powered Meeting Report Generation**

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-blue)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT%20%7C%20Whisper-black)
![Playwright](https://img.shields.io/badge/Playwright-Automation-orange)
![License](https://img.shields.io/badge/License-Educational-lightgrey)

---

# 📖 Overview

The **AI Meeting Assistant** is an intelligent automation platform designed to simplify online meeting management by combining **email intelligence**, **browser automation**, **speech recognition**, and **Generative AI**.

The system automatically detects meeting invitation emails, extracts meeting details, stores them in a PostgreSQL database, joins meetings at the scheduled time, records conversations, transcribes discussions, generates AI-powered meeting summaries, extracts action items and decisions, and stores structured meeting reports for future reference.

The project eliminates repetitive manual tasks involved in attending online meetings while ensuring users never miss important discussions or assigned responsibilities.

---

# 🎯 Objectives

The project aims to:

- Automatically detect meeting invitation emails
- Extract meeting details from emails
- Store meeting information in PostgreSQL
- Automatically join scheduled meetings
- Record meeting conversations
- Convert speech into text
- Generate AI-powered meeting summaries
- Extract decisions and action items
- Track meeting attendance
- Maintain structured meeting history
- Improve productivity using AI automation

---

# 🏗️ System Architecture

```text
                     Gmail Inbox
                          │
                          │
                Email Extraction Agent
                          │
        ┌────────────────────────────────┐
        │                                │
        │  Extract Meeting Information   │
        │  • Meeting Title               │
        │  • Meeting URL                 │
        │  • Meeting Date                │
        │  • Start Time                  │
        │  • Participants                │
        │  • Organizer                   │
        └────────────────────────────────┘
                          │
                          ▼
                 PostgreSQL Database
                          │
                          ▼
                  AI Meeting Agent
                          │
        ┌────────────────────────────────┐
        │                                │
        │  Monitor Upcoming Meetings     │
        │  Launch Browser                │
        │  Join Meeting                  │
        │  Record Audio                  │
        │  Generate Transcript           │
        │  AI Summarization              │
        │  Store Reports                 │
        └────────────────────────────────┘
                          │
                          ▼
                 Meeting Reports Database
```

---

# 🚀 Project Modules

The project consists of two independent AI agents.

---

## 📧 Module 1 – Email Extraction Agent

The Email Agent continuously monitors the user's Gmail inbox for meeting invitation emails.

### Responsibilities

- Authenticate using Gmail OAuth
- Read incoming emails
- Identify meeting invitation emails
- Extract meeting metadata
- Detect meeting platform
- Store structured meeting information in PostgreSQL

### Information Extracted

- Meeting Title
- Meeting Description
- Organizer
- Participants
- Meeting Date
- Start Time
- End Time
- Meeting URL
- Meeting ID
- Passcode
- Platform
- Time Zone

### Database Tables Used

- users
- accounts
- inbox_messages
- meetings
- meeting_updates
- meeting_tags
- notifications
- audit_logs

---

## 🤖 Module 2 – AI Meeting Agent

The Meeting Agent continuously monitors the database for upcoming meetings.

When a meeting is about to begin, it automatically joins the meeting and generates intelligent reports.

### Responsibilities

- Monitor scheduled meetings
- Launch browser automatically
- Join Google Meet
- Join Zoom
- Join Microsoft Teams
- Record meeting audio
- Convert speech into text
- Generate AI summaries
- Extract decisions
- Extract action items
- Track attendance
- Store reports into PostgreSQL

---

# 🔄 Complete Workflow

```text
Gmail Inbox
      │
      ▼
Email Agent
      │
      ▼
Extract Meeting Details
      │
      ▼
Store Meeting Information
      │
      ▼
PostgreSQL
      │
      ▼
Meeting Agent
      │
      ▼
Detect Upcoming Meeting
      │
      ▼
Launch Browser
      │
      ▼
Join Meeting
      │
      ▼
Record Audio
      │
      ▼
Whisper Speech Recognition
      │
      ▼
Meeting Transcript
      │
      ▼
GPT Analysis
      │
      ├───────────────┐
      ▼               ▼
Meeting Summary   Action Items
      │               │
      ▼               ▼
 Decisions      Attendance
      │
      ▼
Store Everything
      │
      ▼
Meeting Database
```

---

# ⚙️ Technology Stack

| Layer | Technology |
|---------|------------|
| Programming Language | Python 3.12 |
| Backend Framework | FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Migration | Alembic |
| Browser Automation | Playwright |
| Speech Recognition | OpenAI Whisper |
| AI Model | OpenAI GPT |
| Scheduler | AsyncIO |
| Logging | Python Logging |
| Containerization | Docker |
| Configuration | python-dotenv |

---

# 🗄️ Database Design

## Existing Tables

| Table | Purpose |
|---------|----------|
| users | User Information |
| accounts | OAuth Credentials |
| inbox_messages | Email Storage |
| meetings | Meeting Metadata |
| meeting_updates | Meeting Changes |
| notifications | Notifications |
| meeting_tags | AI Tags |
| audit_logs | Activity Logs |

---

## AI Meeting Agent Tables

### meeting_transcripts

Stores the complete speech transcript generated by Whisper.

### meeting_reports

Stores AI-generated meeting summaries.

Contains

- Summary
- Key Discussion Points
- Sentiment
- Follow-up Notes

---

### meeting_action_items

Stores extracted tasks.

Contains

- Assigned Person
- Task
- Deadline
- Status

---

### meeting_decisions

Stores important decisions made during meetings.

---

### meeting_attendance

Stores

- Join Time
- Leave Time
- Duration
- Attendance Information

---

# 🧠 AI Pipeline

```text
Meeting Audio
      │
      ▼
OpenAI Whisper
      │
      ▼
Transcript
      │
      ▼
OpenAI GPT
      │
      ├───────────────┐
      │               │
      ▼               ▼
Summary         Decisions
      │               │
      ▼               ▼
Action Items    Sentiment
      │
      ▼
Database Storage
```

---

# 🌟 Features

## Email Agent

- Gmail OAuth Authentication
- Automatic Email Reading
- Meeting Invitation Detection
- AI Email Classification
- Meeting Metadata Extraction
- Database Integration

---

## Meeting Agent

- Automatic Meeting Monitoring
- Browser Automation
- Google Meet Support
- Zoom Support
- Microsoft Teams Support
- Automatic Audio Recording
- AI Speech Recognition
- AI Summarization
- Action Item Extraction
- Decision Tracking
- Attendance Logging

---

# 📦 Installation

Clone the repository

```bash
git clone https://github.com/yourusername/AI-Meeting-Assistant.git
```

Move into the project directory

```bash
cd AI-Meeting-Assistant
```

Create a virtual environment

```bash
python -m venv venv
```

Activate the environment

### Windows

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
source venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Install Playwright browsers

```bash
playwright install
```

Run database migrations

```bash
alembic upgrade head
```

Start the application

```bash
uvicorn app.main:app --reload
```

---

# 🔐 Environment Variables

```env
DATABASE_URL=

OPENAI_API_KEY=

GMAIL_CLIENT_ID=

GMAIL_CLIENT_SECRET=

GMAIL_REFRESH_TOKEN=

CHECK_INTERVAL=30

JOIN_BEFORE_MINUTES=2

WHISPER_MODEL=whisper-1

GPT_MODEL=gpt-4.1
```

---

# ❗ Error Handling

The system includes comprehensive error handling for:

- Invalid meeting links
- OAuth failures
- Gmail API failures
- Browser crashes
- Network interruptions
- Database failures
- Audio recording failures
- Whisper API failures
- GPT API timeouts
- Unexpected meeting termination

---

# 🎯 Applications

- Corporate Meetings
- Online Classes
- Research Discussions
- Team Stand-ups
- Client Meetings
- Academic Seminars
- Technical Interviews
- Project Reviews

---

# 🔮 Future Enhancements

- Live AI Assistant During Meetings
- Speaker Identification
- Real-Time Transcription
- Calendar Synchronization
- Slack Integration
- Microsoft Outlook Integration
- Mobile Notifications
- Multi-language Translation
- Voice Commands
- Retrieval-Augmented Generation (RAG) over Meeting History
- AI Chat with Previous Meetings

---

# 📈 Advantages

- Eliminates manual meeting joining
- Saves meeting history
- Generates structured reports
- Identifies tasks automatically
- Tracks decisions
- Reduces productivity loss
- Improves meeting accessibility
- Modular architecture
- Easily extensible

---

# 📝 Conclusion

The **AI Meeting Assistant** combines email automation, browser automation, speech recognition, and Generative AI into a single intelligent platform. By automating the complete meeting lifecycle—from invitation detection to intelligent report generation—the system enables users to focus on productivity while ensuring that every meeting is attended, documented, and transformed into actionable knowledge.

---

# 👨‍💻 Authors

**Project:** AI Meeting Assistant

- **Email Extraction Agent:** Team Member 1
- **AI Meeting Agent:** Team Member 2

**Institution:** *Sri Eshwar College Of Engineeering*

**Department:** Computer Science and Business Systems

**Academic Year:** 2024-2028

---

# 📜 License

This project is developed for **educational, research, and hackathon purposes**.
