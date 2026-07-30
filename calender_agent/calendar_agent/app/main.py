import os
import logging
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from .database.database import init_db, get_db
from .api import calendar_routes, auth_routes

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("calendar_agent")

app = FastAPI(
    title="Calendar Agent Service | AgentOS",
    description="Standalone Schedule and Google Calendar Synchronization Agent",
    version="1.0.0"
)

# Startup database initialization
@app.on_event("startup")
def startup_event():
    init_db()
    logger.info("Calendar Agent Database initialized.")

# Static files and Jinja2 templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, "static")
templates_dir = os.path.join(BASE_DIR, "templates")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# Include API Routers
app.include_router(calendar_routes.router)
app.include_router(auth_routes.router)

@app.get("/", response_class=HTMLResponse)
def get_dashboard(request: Request):
    """
    Renders the main Calendar Dashboard UI.
    """
    return templates.TemplateResponse(request=request, name="dashboard.html")


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Check API + PostgreSQL database health.
    """
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "service": "Calendar Agent",
        "database": db_status,
        "version": "1.0.0"
    }
