"""
app/db/database.py

Purpose
-------
Owns the SQLAlchemy async engine + session factory. Every other module
gets a DB session through `get_session()` — nobody creates their own
engine. This is what makes the rest of the app testable (swap the
engine in tests) and keeps connection pooling centralized.

Responsibilities
----------------
- Create the async engine from settings.DATABASE_URL
- Provide an async session factory
- Provide a FastAPI dependency (`get_db`) and a plain async-context
  helper (`get_session`) for use inside background services (scheduler
  etc.) that aren't running inside a request.

Flow
----
scheduler / services -> get_session() -> AsyncSession -> crud.py functions

Dependencies
------------
SQLAlchemy 2.0 async engine, asyncpg driver
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config.settings import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models (existing + new tables)."""
    pass


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: `session: AsyncSession = Depends(get_db)`."""
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Use inside background services that aren't in a FastAPI request:

        async with get_session() as session:
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session
