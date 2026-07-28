"""
app/config/settings.py

Purpose
-------
Single source of truth for all runtime configuration. Everything that
changes between environments (dev/staging/prod) lives here and is
loaded from environment variables / a .env file — nothing is hardcoded
in the services.

Responsibilities
----------------
- Define a typed Settings object (pydantic-settings) so config errors
  (missing key, wrong type) fail fast at startup instead of deep inside
  a service at 2am.
- Provide a cached singleton accessor `get_settings()` so we don't
  re-parse the .env file on every import.

Dependencies
------------
pydantic-settings, python-dotenv (loaded implicitly by pydantic-settings)
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Database -----------------------------------------------------
    # Must point at the SAME Postgres database your teammate's
    # email/meeting-extraction pipeline already writes to.
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/meeting_agent"

    # --- Groq (replaces OpenAI GPT + OpenAI Whisper) -------------------
    GROQ_API_KEY: str = ""
    GROQ_API_BASE: str = "https://api.groq.com/openai/v1"
    # Chat/completions model used for summarization + extraction.
    # Groq deprecates/rotates model names periodically — check
    # https://console.groq.com/docs/models before deploying and override
    # via env var if this default has been retired.
    GROQ_CHAT_MODEL: str = "openai/gpt-oss-120b"
    # Groq-hosted Whisper model used for transcription.
    GROQ_WHISPER_MODEL: str = "whisper-large-v3"

    # --- Scheduler / join behavior --------------------------------------
    CHECK_INTERVAL: int = 30           # seconds between DB polls
    JOIN_BEFORE_MINUTES: int = 2       # join this many minutes early
    MEETING_MAX_DURATION_MINUTES: int = 180  # safety cap on recording length

    # --- Bot identity ----------------------------------------------------
    # Shown in-meeting so participants can see a recording bot has joined.
    # Do NOT silently record — check your jurisdiction's consent-to-record
    # rules and keep this name/announcement honest.
    BOT_DISPLAY_NAME: str = "Meeting Notes Bot"

    # --- Google account for bot login ------------------------------------
    # We no longer store bot credentials. We use scripts/generate_google_session.py
    # to manually authenticate a headed browser and inject the resulting
    # base64 session file into GOOGLE_SESSION_B64 via the environment.

    # --- Storage ----------------------------------------------------------
    RECORDINGS_DIR: str = "/tmp/meeting-agent/recordings"

    # --- Logging ------------------------------------------------------
    LOG_LEVEL: str = "INFO"

    # --- Retry behavior -------------------------------------------------
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_SECONDS: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — import and call this, don't instantiate Settings() directly."""
    return Settings()
