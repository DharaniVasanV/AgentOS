"""
app/main.py

Purpose
-------
The application entrypoint. Creates the FastAPI app, mounts the API
routes, and starts the background scheduler as an asyncio task on
startup (and cancels it cleanly on shutdown).

Responsibilities
----------------
- FastAPI app + lifespan management
- Nothing else — this file should stay thin; all logic lives in
  app/services and app/db

Run with
--------
uvicorn app.main:app --host 0.0.0.0 --port 8000

Dependencies
------------
fastapi, uvicorn, app.api.routes, app.services.scheduler
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.services import scheduler
from app.utils.logger import get_logger

logger = get_logger(__name__)

_scheduler_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler_task
    logger.info("Starting Meeting Agent")
    _scheduler_task = asyncio.create_task(scheduler.run_scheduler())
    yield
    logger.info("Shutting down Meeting Agent")
    scheduler.stop_scheduler()
    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Meeting Agent", version="1.0.0", lifespan=lifespan)
app.include_router(router)
