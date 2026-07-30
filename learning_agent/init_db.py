"""
init_db.py

Database table initialization script for Learning Agent.
"""

import asyncio
from app.db.session import engine, Base
from app.db import models
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def init_db():
    logger.info("Creating Learning Agent database tables in PostgreSQL...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tables created successfully!")

if __name__ == "__main__":
    asyncio.run(init_db())
