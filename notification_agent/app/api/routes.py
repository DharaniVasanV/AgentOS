"""
app/api/routes.py

REST API Routes for Notification Agent Version 3.0.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services import notification_service, sound_service, email_service
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "Notification Agent",
        "version": "3.0"
    }


import traceback

from fastapi.responses import JSONResponse

@router.post("/notifications/create")
async def create_notification(payload: Dict[str, Any]):
    """
    Trigger a new notification (Standalone / Integrated mode).
    Creates a record in `notification_jobs` table.
    """
    try:
        result = await notification_service.create_notification_job(payload)
        return JSONResponse(content=result)
    except Exception as err:
        logger.error(f"Error creating notification job:\n{traceback.format_exc()}")
        return JSONResponse(status_code=400, content={
            "status": "failed",
            "reason": str(err)
        })


@router.get("/notifications")
async def list_notifications():
    """Retrieve all notification history."""
    return notification_service.get_all_notifications()


@router.get("/notifications/{notification_id}")
async def get_notification(notification_id: str):
    """Retrieve details for a single notification."""
    notifs = notification_service.get_all_notifications()
    for n in notifs:
        if n.get("notification_id") == notification_id:
            return n
    raise HTTPException(status_code=404, detail="Notification not found.")


@router.delete("/notifications/{notification_id}")
async def delete_notification(notification_id: str):
    """Delete a notification history record."""
    success = notification_service.delete_notification_record(notification_id)
    return {"status": "success", "deleted_id": notification_id}


@router.post("/notifications/{notification_id}/status")
async def update_status(notification_id: str, payload: Dict[str, Any]):
    """Update status (e.g. Read, Dismissed, Completed, Snoozed)."""
    new_status = payload.get("status", "Read")
    updated = notification_service.update_notification_status(notification_id, new_status)
    if not updated:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"status": "success", "notification_id": notification_id, "new_status": new_status}


@router.post("/notifications/{notification_id}/dismiss")
async def dismiss_notification(notification_id: str):
    """Dismiss notification and stop recurring reminders."""
    return notification_service.dismiss_notification(notification_id)


@router.post("/notifications/{notification_id}/complete")
async def complete_notification(notification_id: str):
    """Mark notification complete and stop recurring reminders."""
    return notification_service.complete_notification(notification_id)


@router.post("/notifications/{notification_id}/snooze")
async def snooze_notification(notification_id: str, payload: Optional[Dict[str, Any]] = None):
    """Snooze notification."""
    snooze_mins = payload.get("snooze_minutes", 15) if payload else 15
    return notification_service.snooze_notification(notification_id, snooze_mins)


@router.get("/preferences")
async def get_preferences():
    """Get current user notification preferences."""
    return notification_service.load_json_prefs()


@router.post("/preferences")
async def save_preferences(prefs: Dict[str, Any]):
    """Save user notification preferences."""
    notification_service.save_json_prefs(prefs)
    return {"status": "success", "preferences": prefs}


@router.get("/sounds")
async def list_sounds(user_id: str = "dharanivasan"):
    """Get list of system built-in sounds and uploaded custom sounds."""
    return sound_service.list_all_sounds(user_id)


@router.post("/sounds/upload")
async def upload_sound(file: UploadFile = File(...), user_id: str = Form("user_default")):
    """Upload custom notification audio sound (MP3, WAV, OGG)."""
    res = await sound_service.save_custom_sound(file, user_id)
    if res.get("status") == "failed":
        raise HTTPException(status_code=400, detail=res.get("reason"))
    return res


@router.post("/test-email")
async def test_email(payload: Dict[str, Any]):
    """Send immediate test email to verify SMTP configuration."""
    to_email = payload.get("to_email", "dharanivasanveeramani07@gmail.com")
    res = await email_service.send_notification_email(
        to_email=to_email,
        title="AgentOS SMTP Email Verification Test",
        description="This is a test notification sent autonomously by the AgentOS Notification Agent to verify Gmail SMTP integration.",
        priority="High",
        notification_type="System Test",
        actions=["Open Dashboard"]
    )
    return res
