"""
app/config/settings.py

Single source of truth for runtime configuration loading from E:\meeting-agent\.env.
"""

import os
from functools import lru_cache
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = r"e:\meeting-agent\.env"
load_dotenv(ENV_PATH, override=True)


class Settings(BaseSettings):
    # --- Database -----------------------------------------------------
    DATABASE_URL: str = "postgresql+asyncpg://postgres:vasan5707@localhost:5432/meeting_agent_new"

    # --- Groq API Key --------------------------------------------------
    GROQ_API_KEY: str = ""
    GROQ_API_BASE: str = "https://api.groq.com/openai/v1"
    GROQ_CHAT_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_WHISPER_MODEL: str = "whisper-large-v3"

    # --- Scheduler / join behavior --------------------------------------
    CHECK_INTERVAL: int = 30
    JOIN_BEFORE_MINUTES: int = 2
    MEETING_MAX_DURATION_MINUTES: int = 180

    # --- Bot identity ----------------------------------------------------
    BOT_DISPLAY_NAME: str = "Meeting Notes Bot"

    # --- Storage ----------------------------------------------------------
    RECORDINGS_DIR: str = "/tmp/meeting-agent/recordings"

    # --- Logging ------------------------------------------------------
    LOG_LEVEL: str = "INFO"

    # --- Retry behavior -------------------------------------------------
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_SECONDS: int = 5

    model_config = SettingsConfigDict(env_file=ENV_PATH, env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — import and call this, don't instantiate Settings() directly."""
    return Settings()
