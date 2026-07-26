# AI Meeting Intelligence Agent

This workspace contains a minimal prototype of the AI Meeting Intelligence Agent.

## Features
- Monitors inbox-like email samples
- Classifies meeting invitations
- Validates meeting links
- Extracts meeting metadata
- Stores and deduplicates meetings
- Exposes a small FastAPI endpoint for syncing meetings

## Run locally

```bash
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Then open http://127.0.0.1:8001/docs for the interactive API docs.

## Gmail integration

To connect to a real Gmail inbox, set these environment variables before starting the app:

```bash
set GMAIL_ACCESS_TOKEN=...
set GMAIL_REFRESH_TOKEN=...
set GMAIL_CLIENT_ID=...
set GMAIL_CLIENT_SECRET=...
```

If these are not provided, the app falls back to a sample inbox so the server can still run.

To start the OAuth flow, run:

```bash
python -m app.gmail_oauth
```

This will open a browser window for Google authentication and print the tokens after approval.
