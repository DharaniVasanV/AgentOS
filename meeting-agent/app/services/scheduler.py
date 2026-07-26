"""
app/services/scheduler.py

Purpose
-------
The heartbeat of the whole service: an infinite async loop that calls
meeting_monitor.check_and_dispatch() every CHECK_INTERVAL seconds.
Started as a background asyncio task from main.py's FastAPI startup
event, so the API and the background monitor share one process/event
loop (simplest deployment; see README for the alternative of running
this as a separate worker process if you need to scale them independently).

Responsibilities
----------------
- Loop forever, catching and logging exceptions per-tick so one bad
  cycle never kills the whole scheduler

Dependencies
------------
app.services.meeting_monitor
"""

import asyncio

from app.config.settings import get_settings
from app.services import meeting_monitor
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

_running = False


async def run_scheduler() -> None:
    global _running
    _running = True
    logger.info("Scheduler started, polling every %s seconds", settings.CHECK_INTERVAL)
    while _running:
        try:
            await meeting_monitor.check_and_dispatch()
        except Exception:
            logger.exception("Scheduler tick failed")
        await asyncio.sleep(settings.CHECK_INTERVAL)


def stop_scheduler() -> None:
    global _running
    _running = False
