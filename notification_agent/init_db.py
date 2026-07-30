"""
init_db.py

Initializes the PostgreSQL database schema for Notification Agent Version 3.0.
"""

import asyncio
from app.db.database import engine, Base
from app.db.models import (
    User, NotificationPreference, NotificationSound,
    NotificationTemplate, Notification, NotificationHistory, NotificationLog
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def init_db():
    logger.info("Initializing Notification Agent database tables in PostgreSQL...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tables for Notification Agent initialized successfully!")


if __name__ == "__main__":
    asyncio.run(init_db())
