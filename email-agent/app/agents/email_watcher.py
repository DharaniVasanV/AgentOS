import base64
import os
from typing import Dict, List

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except ImportError:
    Credentials = None
    build = None


def _load_env_dict() -> Dict[str, str]:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_path = os.path.join(project_root, ".env")
    if not os.path.exists(env_path):
        return {}
    values = {}
    with open(env_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            values[key.strip()] = val.strip()
    return values


def watch_inbox() -> List[Dict[str, object]]:
    env_dict = _load_env_dict()

    token = os.getenv("GMAIL_ACCESS_TOKEN") or env_dict.get("GMAIL_ACCESS_TOKEN")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN") or env_dict.get("GMAIL_REFRESH_TOKEN")
    client_id = os.getenv("GMAIL_CLIENT_ID") or env_dict.get("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET") or env_dict.get("GMAIL_CLIENT_SECRET")

    if token and refresh_token and client_id and client_secret and Credentials and build:
        try:
            creds = Credentials(
                token=token,
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                token_uri="https://oauth2.googleapis.com/token",
                scopes=["https://www.googleapis.com/auth/gmail.readonly"],
            )
            service = build("gmail", "v1", credentials=creds)
            # Query past inbox messages matching meeting and form terms (up to 50 past emails)
            query = "meeting OR join OR schedule OR meet OR zoom OR teams OR webex OR form OR survey OR rsvp"
            results = service.users().messages().list(userId="me", q=query, maxResults=50).execute()
            messages = results.get("messages", [])
            emails = []
            for msg in messages:
                full = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
                payload = full.get("payload", {})
                headers = {h["name"].lower(): h.get("value", "") for h in payload.get("headers", [])}
                
                body = ""
                parts = payload.get("parts", [])
                if parts:
                    for part in parts:
                        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                            body = base64.urlsafe_b64decode(part["body"]["data"].encode("ascii")).decode("utf-8", errors="ignore")
                            break
                elif payload.get("body", {}).get("data"):
                    body = base64.urlsafe_b64decode(payload["body"]["data"].encode("ascii")).decode("utf-8", errors="ignore")

                emails.append({
                    "id": full.get("id"),
                    "subject": headers.get("subject", ""),
                    "sender": headers.get("from", ""),
                    "body": body,
                    "timestamp": headers.get("date", ""),
                })
            return emails
        except Exception as exc:
            import traceback
            print(f"Error watching inbox via Gmail API: {exc}")
            traceback.print_exc()
            return []

    return []
