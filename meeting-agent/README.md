# Meeting Agent

An AI backend that watches a `meetings` table (populated upstream by an
existing email/meeting-extraction pipeline), auto-joins the meeting at
the scheduled time, records audio, transcribes it, and generates a
summary, action items, decisions, and attendance — all via **Groq**
(Whisper + LLM), no OpenAI dependency.

This service **only reads** from `meetings`, `users`, `accounts`,
`inbox_messages`, `notifications`, `meeting_tags`, `audit_logs`,
`meeting_updates` — except for one write it owns: updating
`meetings.status` as it progresses the meeting through its lifecycle.
It owns and writes to 5 new tables (see Architecture below).

## 1. High-level architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PostgreSQL (existing)                       │
│  meetings · users · accounts · inbox_messages · notifications ·     │
│  meeting_tags · audit_logs · meeting_updates   (read-only for us,    │
│  except meetings.status which we update)                            │
└───────────────────────────────┬───────────────────────────────────┘
                                 │ poll every CHECK_INTERVAL
                                 ▼
                        ┌─────────────────┐
                        │  scheduler.py   │  (asyncio loop)
                        └────────┬────────┘
                                 ▼
                        ┌─────────────────────┐
                        │ meeting_monitor.py  │  finds due meetings
                        └────────┬────────────┘
                                 ▼  (one asyncio task per meeting)
                        ┌─────────────────────┐
                        │ meeting_joiner.py   │  orchestrator
                        └───┬───────┬─────────┘
             ┌──────────────┘       └───────────────┐
             ▼                                       ▼
     ┌───────────────┐                      ┌────────────────┐
     │  browser.py   │  Playwright join     │  recorder.py   │  ffmpeg + Pulse
     └───────────────┘                      └────────┬───────┘
                                                       ▼ audio.wav
                                            ┌────────────────────┐
                                            │ whisper_service.py │  Groq Whisper
                                            └─────────┬──────────┘
                                                       ▼ transcript
                                            ┌────────────────────┐
                                            │ report_service.py  │
                                            │  ├─ summary_service │  Groq LLM
                                            │  └─ extraction_svc │  Groq LLM
                                            └─────────┬──────────┘
                                                       ▼
                                       ┌────────────────────────────────┐
                                       │ New tables (owned by this svc) │
                                       │ meeting_transcripts            │
                                       │ meeting_reports                │
                                       │ meeting_action_items           │
                                       │ meeting_decisions              │
                                       │ meeting_attendance             │
                                       └────────────────────────────────┘
```

## 2. Folder structure

```
meeting-agent/
    app/
        api/routes.py
        config/settings.py
        db/{database.py, models.py, crud.py}
        services/{scheduler, meeting_monitor, meeting_joiner,
                   browser, recorder, whisper_service,
                   summary_service, extraction_service,
                   report_service, attendance_service}.py
        prompts/{summary_prompt.txt, extraction_prompt.txt}
        utils/{logger.py, helpers.py}
        main.py
    migrations/            (Alembic — creates only the 5 new tables)
    requirements.txt
    Dockerfile
    entrypoint.sh
    docker-compose.yml
    .env.example
    README.md
```

## 3. Data flow (per meeting)

`scheduled` → **scheduler** polls → **meeting_monitor** finds it due →
**meeting_joiner** flips status to `joining` → **browser.py** joins via
Playwright → status → `in_progress` → **recorder.py** captures audio →
meeting ends → **whisper_service** transcribes via Groq →
**report_service** runs summary + extraction (both via Groq) → results
saved → **attendance_service** logs bot join/leave → status →
`completed`. Any failure at any step → status → `failed` + audit log +
notification row.

## 4. Sequence diagram

```
Scheduler        Monitor         Joiner          Browser      Recorder     Groq API        DB
   │  tick          │               │               │             │            │           │
   ├───────────────>│ get_meetings_due()                            │            │           │
   │                ├───────────────────────────────────────────────────────────────────────>│
   │                │<───────────────────────────────────────────────────────────────────────┤
   │                │ dispatch(meeting)              │               │             │          │
   │                ├──────────────>│ set_status(joining)            │             │          │
   │                │               ├────────────────────────────────────────────────────────>│
   │                │               │ join_meeting()  │               │             │          │
   │                │               ├───────────────>│               │             │          │
   │                │               │<───success──────┤               │             │          │
   │                │               │ set_status(in_progress)         │             │          │
   │                │               │ start_recording()                │            │          │
   │                │               ├─────────────────────────────────>│            │          │
   │                │               │  ... meeting happens, then ...   │            │          │
   │                │               │ stop_recording()                 │            │          │
   │                │               ├─────────────────────────────────>│            │          │
   │                │               │<──audio.wav──────────────────────┤            │          │
   │                │               │ transcribe(audio.wav)                          │          │
   │                │               ├────────────────────────────────────────────────>│          │
   │                │               │<──transcript────────────────────────────────────┤          │
   │                │               │ summarize + extract(transcript)                │          │
   │                │               ├────────────────────────────────────────────────>│          │
   │                │               │<──summary/action_items/decisions───────────────┤          │
   │                │               │ save all + set_status(completed)                │          │
   │                │               ├────────────────────────────────────────────────────────────>│
```

## 5. Installation (local, no Docker)

```bash
git clone <your-repo>
cd meeting-agent
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium
```

### Audio setup (required for recording — local, non-Docker only)

The recorder captures system audio via a **virtual PulseAudio sink**,
since Playwright/Chromium has no built-in "record this tab" API. On a
Linux dev machine with PulseAudio already running:

```bash
pactl load-module module-null-sink sink_name=meetingsink sink_properties=device.description=meetingsink
pactl set-default-sink meetingsink
```

(In Docker, `entrypoint.sh` does this automatically.) On macOS, PulseAudio
isn't native — either run this service inside the provided Docker
container (recommended) or substitute a macOS virtual audio device
(e.g. BlackHole) and update `_PULSE_MONITOR_SOURCE` in `recorder.py`
accordingly.

### FFmpeg

```bash
# Debian/Ubuntu
sudo apt-get install ffmpeg
# macOS
brew install ffmpeg
```

## 6. Environment variables

Copy `.env.example` to `.env` and fill in:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Points at the **existing** Postgres DB your teammate's pipeline writes to |
| `GROQ_API_KEY` | Used for both transcription (Whisper) and summarization/extraction (LLM) |
| `GROQ_CHAT_MODEL` | Chat model for summary/extraction — check `console.groq.com/docs/models`, Groq rotates model names |
| `GROQ_WHISPER_MODEL` | `whisper-large-v3` (or `whisper-large-v3-turbo` for lower latency) |
| `CHECK_INTERVAL` | Seconds between DB polls |
| `JOIN_BEFORE_MINUTES` | How early to join before the scheduled start |
| `BOT_DISPLAY_NAME` | Name the bot shows inside the meeting — keep this honest/visible, don't disguise it as a human participant |

## 7. Running locally

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The scheduler starts automatically with the app (see `app/main.py`
lifespan). Check `GET /health`.

## 8. Running with Docker

```bash
docker compose up --build
```

This builds the image (Python + ffmpeg + PulseAudio + Playwright's
Chromium), starts PulseAudio + the virtual sink via `entrypoint.sh`,
then starts the API + scheduler.

## 9. Database migration

This project's Alembic migration creates **only** the 5 new tables —
it never touches `meetings` or any other existing table.

```bash
alembic upgrade head
```

To roll back:

```bash
alembic downgrade -1
```

## 10. API reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/meetings/{id}/transcript` | Full transcript |
| GET | `/meetings/{id}/report` | Summary, key points, follow-ups, sentiment |
| GET | `/meetings/{id}/action-items` | Extracted action items |
| GET | `/meetings/{id}/decisions` | Extracted decisions |
| POST | `/meetings/{id}/trigger` | Manually join now, bypassing the scheduler's timing check (testing) |

## 11. Error handling implemented

- Invalid/unreachable meeting link → `browser.join_meeting` returns
  `False` → status → `failed`, audit log + error notification.
- Browser crash mid-join → caught, same failure path.
- Whisper/Groq transcription failure → retried (`MAX_RETRIES`, linear
  backoff via `with_retries` in `utils/helpers.py`), then raises →
  meeting marked `failed` with audit log (no silent data loss — you'll
  see it in `/health`-adjacent logs and the `audit_logs` table).
- Groq chat completion timeout/error → same retry wrapper.
- Malformed LLM JSON output → `safe_json_loads` strips markdown fences
  and grabs the outermost `{...}`; if still unparseable, summary falls
  back to raw text and extraction falls back to empty lists rather than
  crashing the whole pipeline.
- Meeting cancelled after we've already dispatched → `meeting_joiner`
  re-fetches the meeting fresh and checks `status == "scheduled"`
  before doing anything, so a status change wins the race.

## 12. Known limitations — read before relying on this in production

1. **Zoom and Teams join selectors** (`app/services/browser.py`) are a
   working starting point, not a guarantee. Both platforms change
   button labels, add app-download interstitials, or alter waiting-room
   flows across releases more often than Google Meet does. Test against
   real links from your target platforms and expect to adjust selectors.
2. **Audio capture** (`app/services/recorder.py`) depends on routing
   Chromium's output to a virtual PulseAudio sink — this is the
   standard technique open-source meeting bots use, but it's
   infrastructure-level setup (see `entrypoint.sh`) that needs to
   actually run correctly in your deployment target, not just in code.
3. **Per-participant attendance** is not implemented — only the bot's
   own join/leave time is recorded (`attendance_service.py`). Reliably
   scraping every human participant's individual join/leave time from
   each platform's live UI is fragile and was out of scope here; the
   `meeting_attendance` table is structured to support it if you add
   platform-specific participant-list scraping later.
4. **Recording consent**: auto-joining and recording a call has legal
   notice/consent requirements that vary by jurisdiction (e.g.
   two-party consent states/countries). The bot joins with a visible,
   honest display name (`BOT_DISPLAY_NAME`) rather than disguising
   itself — but you are responsible for whatever additional consent
   mechanism (verbal announcement, host confirmation, etc.) your
   jurisdiction requires.
5. **Groq model names change**: `GROQ_CHAT_MODEL`/`GROQ_WHISPER_MODEL`
   are read from `.env` specifically so you can update them without a
   code change when Groq deprecates a model — check
   `https://console.groq.com/docs/models` periodically.
6. This was generated as a complete first pass across every file in the
   spec — it has not been run against a live database or a real meeting
   link. Treat it as a strong starting point that needs an integration
   test pass against your teammate's actual schema and real meeting
   URLs, not as already-verified production code.
