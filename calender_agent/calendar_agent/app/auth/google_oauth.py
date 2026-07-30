import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone as tz, timedelta
from cryptography.fernet import Fernet
import base64
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Derive a consistent 32-byte Fernet key from SECRET_KEY
SECRET_KEY = os.getenv("SECRET_KEY", "calendar_agent_default_secret_key_32_bytes_long!")
key_bytes = SECRET_KEY.ljust(32)[:32].encode('utf-8')
FERNET_KEY = base64.urlsafe_b64encode(key_bytes)
cipher_suite = Fernet(FERNET_KEY)

# Allow HTTP for local OAuth testing (e.g. http://localhost:8005)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8005/auth/google/callback").strip()
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events"
]

class GoogleOAuthHandler:
    @staticmethod
    def encrypt_token(token: Optional[str]) -> Optional[str]:
        if not token:
            return None
        return cipher_suite.encrypt(token.encode('utf-8')).decode('utf-8')

    @staticmethod
    def decrypt_token(token_encrypted: Optional[str]) -> Optional[str]:
        if not token_encrypted:
            return None
        try:
            return cipher_suite.decrypt(token_encrypted.encode('utf-8')).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to decrypt Google token: {e}")
            return None

    @staticmethod
    def get_authorization_url() -> str:
        """
        Generates Google OAuth 2.0 authorization URL.
        """
        if not GOOGLE_CLIENT_ID or GOOGLE_CLIENT_ID.startswith("your_") or not GOOGLE_CLIENT_SECRET or GOOGLE_CLIENT_SECRET.startswith("your_"):
            # Return demo/mock auth URL if not configured
            return f"/auth/google/callback?code=mock_authorization_code_for_demo"

        from urllib.parse import urlencode
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true"
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    @staticmethod
    def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
        """
        Exchanges authorization code for access and refresh tokens.
        """
        if code.startswith("mock_") or not GOOGLE_CLIENT_ID or GOOGLE_CLIENT_ID.startswith("your_") or not GOOGLE_CLIENT_SECRET or GOOGLE_CLIENT_SECRET.startswith("your_"):
            return {
                "access_token": f"mock_access_token_{int(datetime.now().timestamp())}",
                "refresh_token": f"mock_refresh_token_{int(datetime.now().timestamp())}",
                "expiry": datetime.now(tz.utc) + timedelta(hours=1),
                "email": "user.demo@google.com"
            }

        import httpx
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code"
        }

        response = httpx.post(token_url, data=payload, timeout=15.0)
        if response.status_code != 200:
            logger.error(f"Google token exchange failed: {response.text}")
            raise Exception(f"Google token exchange failed ({response.status_code}): {response.text}")

        token_data = response.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        expiry = datetime.now(tz.utc) + timedelta(seconds=expires_in)

        email = "google_user@gmail.com"
        if access_token:
            try:
                userinfo_res = httpx.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10.0
                )
                if userinfo_res.status_code == 200:
                    email = userinfo_res.json().get("email", email)
            except Exception as ex:
                logger.warning(f"Could not fetch user profile email: {ex}")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expiry": expiry,
            "email": email
        }
