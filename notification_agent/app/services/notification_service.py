"""
app/services/notification_service.py

Notification Agent Version 3.0 - Integrated & Standalone Delivery Microservice.
Monitors `notification_jobs` table every 5 seconds and delivers notifications.
"""

import os
import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.db import models
from app.db.database import AsyncSessionLocal
from app.services import sound_service, email_service, desktop_service
from app.utils.logger import get_logger

logger = get_logger(__name__)

JOBS_STORE_FILE = "e:/meeting-agent/notification_agent/data/notification_jobs.json"
PREFS_STORE_FILE = "e:/meeting-agent/notification_agent/data/user_preferences.json"


def ensure_store_dir():
    os.makedirs(os.path.dirname(JOBS_STORE_FILE), exist_ok=True)


def load_json_jobs() -> List[Dict[str, Any]]:
    ensure_store_dir()
    if os.path.exists(JOBS_STORE_FILE):
        try:
            with open(JOBS_STORE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_json_jobs(data: List[Dict[str, Any]]):
    ensure_store_dir()
    with open(JOBS_STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_json_prefs() -> Dict[str, Any]:
    ensure_store_dir()
    if os.path.exists(PREFS_STORE_FILE):
        try:
            with open(PREFS_STORE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "channels": ["Browser", "Dashboard", "Desktop", "Email"],
        "sound_type": "Bell",
        "custom_sound_name": None,
        "volume": 80,
        "quiet_hours_enabled": False,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "07:00",
        "dnd_enabled": False,
        "emergency_override": True,
        "default_snooze_duration": 15
    }


def save_json_prefs(prefs: Dict[str, Any]):
    ensure_store_dir()
    with open(PREFS_STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2)


async def create_notification_job(
    raw_payload: Dict[str, Any],
    session: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """
    Creates a notification job (used in Standalone Mode via UI/API).
    Stores directly in `notification_jobs` table.
    """
    title = raw_payload.get("title")
    description = raw_payload.get("description")
    priority = raw_payload.get("priority", "Medium")
    user_id = str(raw_payload.get("user_id", "user_default"))
    category = raw_payload.get("category") or raw_payload.get("type", "General")
    notif_time_raw = raw_payload.get("notification_time") or raw_payload.get("event_time") or datetime.now().isoformat()
    channels = raw_payload.get("channels") or ["Browser", "Dashboard", "Desktop", "Email"]
    sound = raw_payload.get("sound") or raw_payload.get("custom_sound")
    action_buttons = raw_payload.get("action_buttons") or raw_payload.get("actions") or ["Open Dashboard", "Dismiss"]
    action_url = raw_payload.get("action_url")
    calendar_event_id = raw_payload.get("calendar_event_id")

    if not title or not description or not priority or not user_id:
        return {
            "status": "failed",
            "reason": "Invalid notification request."
        }

    job_id = str(raw_payload.get("id") or uuid.uuid4())

    job_dict = {
        "id": job_id,
        "calendar_event_id": str(calendar_event_id) if calendar_event_id else None,
        "user_id": user_id,
        "title": title,
        "description": description,
        "category": category,
        "priority": priority,
        "notification_time": notif_time_raw,
        "channels": channels,
        "sound": sound,
        "action_buttons": action_buttons,
        "action_url": action_url,
        "user_email": raw_payload.get("user_email"),
        "status": "Pending",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    # Save to local JSON store fallback
    jobs = load_json_jobs()
    jobs.insert(0, job_dict)
    save_json_jobs(jobs)

    # Save to PostgreSQL database table notification_jobs
    if session:
        try:
            notif_dt = datetime.fromisoformat(notif_time_raw.replace("Z", "+00:00")) if "T" in notif_time_raw else datetime.now()
            db_job = models.NotificationJob(
                id=uuid.UUID(job_id),
                calendar_event_id=uuid.UUID(calendar_event_id) if calendar_event_id else None,
                user_id=user_id,
                title=title,
                description=description,
                category=category,
                priority=priority,
                notification_time=notif_dt,
                channels=channels,
                sound=sound,
                action_buttons=action_buttons,
                action_url=action_url,
                status="Pending",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            session.add(db_job)
            await session.commit()
        except Exception as err:
            logger.warning(f"PostgreSQL store skipped in create_notification_job: {err}")

    logger.info(f"📥 Notification job '{title}' created (Status: Pending).")

    # Immediate delivery trigger if notification_time <= now
    asyncio.create_task(process_single_job(job_dict))

    return {
        "status": "success",
        "notification_job_id": job_id,
        "delivery_status": "Scheduled",
        "channels": channels,
        "sound": sound or "default",
        "delivered_at": "",
        "user_action": "Pending"
    }


async def process_single_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the 10-Step Processing Workflow for a single notification_job record.
    """
    job_id = job.get("id") or str(uuid.uuid4())
    title = job.get("title")
    description = job.get("description")
    priority = job.get("priority")
    user_id = job.get("user_id")
    notif_time = job.get("notification_time")
    category = job.get("category", "General")
    calendar_event_id = job.get("calendar_event_id")

    # STEP 1: Validate Notification
    if not title or not description or not priority or not user_id or not notif_time:
        logger.warning(f"Step 1 Validation Failed for job {job_id}.")
        await update_job_status(job_id, "Failed")
        return {"status": "failed", "reason": "Invalid notification request."}

    # STEP 2: Load User Preferences
    user_prefs = load_json_prefs()

    # STEP 3: Determine Delivery
    dnd = user_prefs.get("dnd_enabled", False)
    emergency_override = user_prefs.get("emergency_override", True)
    job_channels = job.get("channels") or user_prefs.get("channels", ["Browser", "Dashboard", "Desktop", "Email"])

    effective_channels = list(job_channels)
    if dnd and not (str(priority).capitalize() == "Emergency" and emergency_override):
        effective_channels = [c for c in effective_channels if c == "Dashboard"]

    # STEP 5: Notification Sound
    custom_sound = job.get("sound") or user_prefs.get("custom_sound_name")
    default_sound = user_prefs.get("sound_type", "Bell")
    sound_info = sound_service.resolve_notification_sound(custom_sound, default_sound)
    sound_name = sound_info.get("name", "bell.mp3")

    # STEP 4: Send Notifications across channels
    now_iso = datetime.now().isoformat()
    delivered_at = now_iso

    # Native OS Desktop Toast Delivery
    if "Desktop" in effective_channels:
        try:
            await desktop_service.trigger_desktop_alert(
                title=title,
                message=description,
                priority=priority
            )
        except Exception as dt_err:
            logger.warning(f"Desktop alert dispatch error: {dt_err}")

    # Email Delivery
    to_email = job.get("user_email") or user_prefs.get("email") or settings.SMTP_USER
    if "Email" in effective_channels:
        asyncio.create_task(
            email_service.send_notification_email(
                to_email=to_email,
                title=title,
                description=description,
                priority=priority,
                notification_type=category,
                action_url=job.get("action_url"),
                actions=job.get("action_buttons") or ["Open Dashboard", "Dismiss"]
            )
        )

    # STEP 6, 7 & 9: Update notification_jobs status to Delivered
    await update_job_status(job_id, "Delivered")

    # STEP 10: Store notification_history
    await store_notification_history(
        job_id=job_id,
        calendar_event_id=calendar_event_id,
        user_id=user_id,
        priority=priority,
        category=category,
        channels_used=effective_channels,
        sound_used=sound_name,
        scheduled_time=str(notif_time),
        delivery_time=delivered_at,
        status="Delivered"
    )

    logger.info(f"🚀 Notification Job '{title}' Delivered successfully!")

    return {
        "status": "success",
        "notification_job_id": job_id,
        "delivery_status": "Delivered",
        "channels": effective_channels,
        "sound": sound_name,
        "delivered_at": delivered_at,
        "user_action": "Pending"
    }


async def update_job_status(job_id: str, new_status: str):
    # Update local JSON store
    jobs = load_json_jobs()
    for j in jobs:
        if j.get("id") == job_id or j.get("notification_job_id") == job_id:
            j["status"] = new_status
            j["updated_at"] = datetime.now().isoformat()
            break
    save_json_jobs(jobs)

    # Update PostgreSQL table notification_jobs
    try:
        async with AsyncSessionLocal() as session:
            try:
                job_uuid = uuid.UUID(job_id)
                stmt = update(models.NotificationJob).where(models.NotificationJob.id == job_uuid).values(
                    status=new_status,
                    updated_at=datetime.now()
                )
                await session.execute(stmt)
                await session.commit()
            except Exception:
                pass
    except Exception as err:
        logger.warning(f"PostgreSQL update_job_status skipped: {err}")


async def store_notification_history(
    job_id: str,
    calendar_event_id: Optional[str],
    user_id: str,
    priority: str,
    category: str,
    channels_used: List[str],
    sound_used: str,
    scheduled_time: str,
    delivery_time: str,
    status: str
):
    try:
        async with AsyncSessionLocal() as session:
            db_hist = models.NotificationHistory(
                id=str(uuid.uuid4()),
                notification_id=str(job_id),
                calendar_event_id=str(calendar_event_id) if calendar_event_id else None,
                user_id=user_id,
                type=category,
                priority=priority,
                channels_used=channels_used,
                sound_used=sound_used,
                scheduled_time=scheduled_time,
                delivery_time=datetime.now(timezone.utc),
                status=status
            )
            session.add(db_hist)
            await session.commit()
    except Exception as err:
        logger.warning(f"PostgreSQL store_notification_history skipped: {err}")


async def start_background_job_monitor():
    """
    BACKGROUND MONITORING WORKFLOW:
    Runs every 5 seconds.
    Queries `notification_jobs` WHERE status = 'Pending' AND notification_time <= CURRENT_TIMESTAMP
    ORDER BY notification_time ASC.
    """
    logger.info("🔄 Background Notification Job Monitor Started (Scanning every 5s)...")
    while True:
        try:
            await asyncio.sleep(5)
            now_utc = datetime.now(timezone.utc)
            now_naive_utc = datetime.utcnow()

            # 1. Scan PostgreSQL notification_jobs table
            try:
                async with AsyncSessionLocal() as session:
                    stmt = select(models.NotificationJob).where(
                        models.NotificationJob.status == "Pending"
                    ).order_by(models.NotificationJob.notification_time.asc())
                    res = await session.execute(stmt)
                    pending_jobs = res.scalars().all()

                    for db_job in pending_jobs:
                        notif_time = db_job.notification_time
                        if notif_time:
                            if getattr(notif_time, "tzinfo", None) is not None:
                                is_due = notif_time <= now_utc
                            else:
                                is_due = notif_time <= now_naive_utc

                            if is_due:
                                logger.info(f"⚡ Found Pending Job in PostgreSQL: {db_job.title}")
                                job_dict = {
                                    "id": str(db_job.id),
                                    "calendar_event_id": str(db_job.calendar_event_id) if db_job.calendar_event_id else None,
                                    "user_id": db_job.user_id,
                                    "title": db_job.title,
                                    "description": db_job.description,
                                    "category": db_job.category,
                                    "priority": db_job.priority,
                                    "notification_time": db_job.notification_time.isoformat() if db_job.notification_time else now_utc.isoformat(),
                                    "channels": db_job.channels,
                                    "sound": db_job.sound,
                                    "action_buttons": db_job.action_buttons,
                                    "action_url": db_job.action_url,
                                    "status": db_job.status
                                }
                                await process_single_job(job_dict)
            except Exception as db_err:
                logger.warning(f"PostgreSQL scan skipped: {db_err}")

            # 2. Scan JSON store fallback for pending jobs
            json_jobs = load_json_jobs()
            for j in json_jobs:
                if j.get("status") == "Pending":
                    notif_time_str = j.get("notification_time")
                    if notif_time_str:
                        try:
                            nt_dt = datetime.fromisoformat(notif_time_str.replace("Z", "+00:00"))
                            if nt_dt.tzinfo:
                                is_due = nt_dt <= now_utc
                            else:
                                is_due = nt_dt <= now_naive_utc

                            if is_due:
                                logger.info(f"⚡ Found Pending Job in JSON Store: {j.get('title')}")
                                await process_single_job(j)
                        except Exception:
                            pass

        except Exception as err:
            logger.error(f"Error in background job monitor: {err}")


def get_all_jobs() -> List[Dict[str, Any]]:
    return load_json_jobs()


def get_all_notifications() -> List[Dict[str, Any]]:
    return load_json_jobs()


def update_job_user_action(job_id: str, action: str) -> Dict[str, Any]:
    # Support actions: Dismiss, Read, Snooze, Mark Complete, Expired
    status_map = {
        "Dismiss": "Dismissed",
        "Read": "Read",
        "Snooze": "Snoozed",
        "Mark Complete": "Completed",
        "Expired": "Expired"
    }
    new_status = status_map.get(action, action)

    asyncio.create_task(update_job_status(job_id, new_status))

    return {
        "status": "success",
        "notification_job_id": job_id,
        "delivery_status": new_status,
        "user_action": action
    }
