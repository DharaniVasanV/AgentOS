"""
app/config/settings.py

Configuration settings for Notification Agent Version 3.0 loading from E:\meeting-agent\.env.
"""

import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = r"e:\meeting-agent\.env"
load_dotenv(ENV_PATH, override=True)


class Settings(BaseSettings):
    SERVICE_NAME: str = "Notification Agent"
    VERSION: str = "3.0"
    PORT: int = 8007
    HOST: str = "127.0.0.1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:vasan5707@localhost:5432/meeting_agent_new"

    # Email SMTP Settings
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "dharanivasanveeramani07@gmail.com"
    SMTP_PASSWORD: str = "ccbt rpxk dzji ovlc"

    # Sound Upload Storage
    UPLOAD_DIR: str = "e:/meeting-agent/notification_agent/static/uploads/sounds"

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
