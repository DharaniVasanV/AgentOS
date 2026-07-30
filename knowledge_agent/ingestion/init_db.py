"""
knowledge_agent/ingestion/init_db.py

Initializes all PostgreSQL database tables for Knowledge Ingestion Service.
"""

import asyncio
from app.db.database import engine, Base
from app.db.models import KnowledgeDocument, KnowledgeChunk, KnowledgeVector, KnowledgeMetadata, AgentLog
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def init_db():
    logger.info("Initializing Knowledge Agent Ingestion database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tables (knowledge_documents, knowledge_chunks, knowledge_vectors, knowledge_metadata, agent_logs) initialized successfully!")


if __name__ == "__main__":
    asyncio.run(init_db())
