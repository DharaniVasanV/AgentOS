"""
career_agent/init_db.py

Initializes the `career_analyses` database table in PostgreSQL.
"""

import asyncio
from app.db.database import engine, Base
from app.db.models import CareerAnalysis  # Ensure models are imported
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def init_db():
    logger.info("Initializing Career Agent database schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database table 'career_analyses' initialized successfully!")


if __name__ == "__main__":
    asyncio.run(init_db())
