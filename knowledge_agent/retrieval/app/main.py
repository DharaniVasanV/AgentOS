"""
app/main.py

FastAPI entrypoint for Knowledge Retrieval Service UI & REST API.
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
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Knowledge Retrieval Service (Knowledge Agent - AgentOS)")
    yield
    logger.info("Shutting down Knowledge Retrieval Service")


app = FastAPI(title="Knowledge Retrieval Service - AgentOS", version="1.0.0", lifespan=lifespan)
app.include_router(router)


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    html_path = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Knowledge Retrieval Service Dashboard</h1><p>Dashboard HTML not found.</p>"
