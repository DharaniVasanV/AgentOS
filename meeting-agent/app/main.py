"""
app/main.py

FastAPI entrypoint for standalone Meeting Agent UI & background scheduler.
"""

import asyncio
import os
import sys
from contextlib import asynccontextmanager

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.api.routes import router
from app.services import scheduler
from app.utils.logger import get_logger

logger = get_logger(__name__)

_scheduler_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler_task
    logger.info("Starting Autonomous Meeting Agent")
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


app = FastAPI(title="Meeting Agent", version="2.0.0", lifespan=lifespan)
app.include_router(router)


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    html_path = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Meeting Agent Dashboard</h1><p>Dashboard HTML not found.</p>"
