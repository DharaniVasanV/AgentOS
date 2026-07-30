"""
app/api/routes.py

FastAPI Routes for Learning Agent Version 1.0.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import learning_service
from app.db.session import get_db

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "Learning Agent", "version": "1.0"}


@router.post("/learning/generate")
@router.post("/learning/create")
async def generate_plan(payload: Dict[str, Any], session: Optional[AsyncSession] = Depends(get_db)):
    """Generate a personalized 12-step learning plan."""
    res = await learning_service.generate_learning_plan(payload, session)
    if res.get("status") == "failed":
        return res
    return res


@router.get("/learning/plans")
@router.get("/learning")
async def list_plans():
    """Retrieve all learning plans."""
    return learning_service.get_all_plans()


@router.get("/learning/plans/{plan_id}")
async def get_plan(plan_id: str):
    """Retrieve a specific learning plan by ID."""
    plans = learning_service.get_all_plans()
    for p in plans:
        if p.get("plan_id") == plan_id or p.get("id") == plan_id:
            return p
    raise HTTPException(status_code=404, detail="Learning plan not found.")


@router.post("/learning/plans/{plan_id}/progress")
async def update_progress(plan_id: str, payload: Dict[str, Any] = None):
    """Update progress for a plan."""
    inc = payload.get("completed_increment", 1) if payload else 1
    return learning_service.update_plan_progress(plan_id, inc)


@router.delete("/learning/plans/{plan_id}")
async def delete_plan(plan_id: str):
    """Delete a plan record."""
    success = learning_service.delete_plan_record(plan_id)
    return {"status": "success", "deleted_id": plan_id}
