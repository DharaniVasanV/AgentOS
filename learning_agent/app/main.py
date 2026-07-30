"""
app/main.py

FastAPI Application entrypoint for Learning Agent Version 1.0.
"""

import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.api.routes import router as api_router
from app.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title=settings.SERVICE_NAME,
    version=settings.VERSION,
    description="AgentOS Learning Agent Version 1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routes
app.include_router(api_router)

DASHBOARD_FILE = "e:/meeting-agent/learning_agent/app/templates/dashboard.html"


@app.get("/", include_in_schema=False)
async def serve_dashboard(request: Request):
    if os.path.exists(DASHBOARD_FILE):
        with open(DASHBOARD_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    return HTMLResponse("<h2>Learning Agent Dashboard</h2>")


@app.on_event("startup")
async def startup_event():
    logger.info(f"🚀 {settings.SERVICE_NAME} v{settings.VERSION} starting on port {settings.PORT}...")
