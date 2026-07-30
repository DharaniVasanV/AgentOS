"""
app/config/settings.py

Configuration settings for the Learning Agent Version 1.0 loading from E:\meeting-agent\.env.
"""

import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = r"e:\meeting-agent\.env"
load_dotenv(ENV_PATH, override=True)


class Settings(BaseSettings):
    SERVICE_NAME: str = "Learning Agent"
    VERSION: str = "1.0"
    PORT: int = 8006
    HOST: str = "127.0.0.1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:vasan5707@localhost:5432/meeting_agent_new"

    # Groq API Key 6
    GROQ_API_KEY6: str = ""
    GROQ_API_KEY: str = ""
    GROQ_CHAT_MODEL: str = "llama-3.3-70b-versatile"

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def effective_groq_key(self) -> str:
        return self.GROQ_API_KEY6 or self.GROQ_API_KEY or os.getenv("GROQ_API_KEY6", "") or os.getenv("GROQ_API_KEY", "")


settings = Settings()
