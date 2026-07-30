"""
app/config/settings.py

Settings for Knowledge Ingestion Service loading API keys from E:\meeting-agent\.env.
"""

import os
from functools import lru_cache
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = r"e:\meeting-agent\.env"
load_dotenv(ENV_PATH, override=True)


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:vasan5707@localhost:5432/meeting_agent_new"
    GROQ_API_KEY4: str = ""
    GROQ_API_KEY: str = ""
    GROQ_CHAT_MODEL: str = "llama-3.3-70b-versatile"
    CHROMA_PERSIST_DIR: str = "e:/meeting-agent/knowledge_agent/ingestion/chroma_db"
    CHUNK_SIZE_WORDS: int = 700
    CHUNK_OVERLAP_WORDS: int = 120
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=ENV_PATH, env_file_encoding="utf-8", extra="ignore")

    @property
    def effective_groq_key(self) -> str:
        return self.GROQ_API_KEY4 or self.GROQ_API_KEY or os.getenv("GROQ_API_KEY4", "") or os.getenv("GROQ_API_KEY", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
