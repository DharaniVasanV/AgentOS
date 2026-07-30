from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone as tz

from ..database.database import get_db
from ..database.repository import CalendarRepository
from ..auth.google_oauth import GoogleOAuthHandler

router = APIRouter(prefix="/auth", tags=["Authentication"])

import logging

logger = logging.getLogger(__name__)

@router.get("/google")
def google_auth_login():
    """
    Redirects user to Google OAuth 2.0 authorization page.
    """
    try:
        url = GoogleOAuthHandler.get_authorization_url()
        return RedirectResponse(url=url)
    except Exception as e:
        logger.error(f"Failed to initiate Google OAuth: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to initiate Google OAuth: {str(e)}")

@router.get("/google/callback")
def google_auth_callback(code: str = Query(...), db: Session = Depends(get_db)):
    """
    Handles Google OAuth 2.0 authorization callback and securely stores encrypted tokens.
    """
    try:
        token_data = GoogleOAuthHandler.exchange_code_for_tokens(code)
        
        repo = CalendarRepository(db)
        encrypted_access = GoogleOAuthHandler.encrypt_token(token_data.get("access_token"))
        encrypted_refresh = GoogleOAuthHandler.encrypt_token(token_data.get("refresh_token"))
        
        expiry = token_data.get("expiry")
        if not expiry:
            expiry = datetime.now(tz.utc)

        repo.save_google_connection(
            user_id="user_1",
            email=token_data.get("email", "user@google.com"),
            access_token=encrypted_access,
            refresh_token=encrypted_refresh,
            expiry=expiry
        )

        return RedirectResponse(url="/?google_connected=true")
    except Exception as e:
        logger.error(f"OAuth authorization failed: {e}")
        error_msg = str(e)
        return HTMLResponse(
            content=f"""
            <html>
                <body style="font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 40px; text-align: center;">
                    <h1 style="color: #f43f5e;">Google OAuth Connection Error</h1>
                    <div style="background: #1e293b; padding: 20px; border-radius: 8px; max-width: 600px; margin: 0 auto; text-align: left;">
                        <p style="color: #94a3b8;"><strong>Error Details:</strong></p>
                        <pre style="color: #fb7185; white-space: pre-wrap;">{error_msg}</pre>
                    </div>
                    <br>
                    <a href="/auth/google" style="background: #6366f1; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: bold;">Retry Sign In</a>
                    <a href="/" style="background: #334155; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; margin-left: 10px;">Return to Dashboard</a>
                </body>
            </html>
            """,
            status_code=400
        )
