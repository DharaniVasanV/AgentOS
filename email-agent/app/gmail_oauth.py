import json
import os
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


def _load_env_file():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(project_root, ".env")
    if not os.path.exists(env_path):
        return {}
    values = {}
    with open(env_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


ENV_VALUES = _load_env_file()
CLIENT_ID = os.getenv("GMAIL_CLIENT_ID") or ENV_VALUES.get("GMAIL_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET") or ENV_VALUES.get("GMAIL_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("GMAIL_REDIRECT_URI") or ENV_VALUES.get("GMAIL_REDIRECT_URI", "http://127.0.0.1:8001/")
SCOPES = "https://www.googleapis.com/auth/gmail.readonly"

def get_auth_url() -> str:
    CLIENT_ID = os.getenv("GMAIL_CLIENT_ID") or ENV_VALUES.get("GMAIL_CLIENT_ID", "")
    REDIRECT_URI = os.getenv("GMAIL_REDIRECT_URI") or ENV_VALUES.get("GMAIL_REDIRECT_URI", "http://127.0.0.1:8001/oauth/callback")
    
    if not CLIENT_ID:
        raise ValueError("GMAIL_CLIENT_ID is not configured in .env")

    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    })

def exchange_code(code: str) -> dict:
    CLIENT_ID = os.getenv("GMAIL_CLIENT_ID") or ENV_VALUES.get("GMAIL_CLIENT_ID", "")
    CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET") or ENV_VALUES.get("GMAIL_CLIENT_SECRET", "")
    REDIRECT_URI = os.getenv("GMAIL_REDIRECT_URI") or ENV_VALUES.get("GMAIL_REDIRECT_URI", "http://127.0.0.1:8001/oauth/callback")

    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    
    request = Request(
        token_url,
        data=urlencode(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    
    try:
        with urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
            
        # Update .env
        env_lines = []
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                env_lines = f.readlines()
                
        # Remove old tokens
        env_lines = [l for l in env_lines if not l.startswith("GMAIL_ACCESS_TOKEN=") and not l.startswith("GMAIL_REFRESH_TOKEN=")]
        
        with open(env_path, "w", encoding="utf-8") as f:
            for l in env_lines:
                f.write(l)
            if not env_lines or not env_lines[-1].endswith('\n'):
                f.write('\n')
            f.write(f"GMAIL_ACCESS_TOKEN={data.get('access_token', '')}\n")
            if data.get('refresh_token'):
                f.write(f"GMAIL_REFRESH_TOKEN={data.get('refresh_token', '')}\n")
                
        # Also update os.environ
        os.environ["GMAIL_ACCESS_TOKEN"] = data.get("access_token", "")
        if data.get("refresh_token"):
            os.environ["GMAIL_REFRESH_TOKEN"] = data.get("refresh_token", "")
            
        return data
        
    except (HTTPError, URLError) as exc:
        raise ValueError(f"Token exchange failed: {str(exc)}")
