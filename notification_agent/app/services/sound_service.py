"""
app/services/sound_service.py

Notification Sound Management & Custom Sound Upload Service.
"""

import os
import shutil
from typing import Dict, Any, List
from fastapi import UploadFile

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Standard Built-in System Sounds
SYSTEM_SOUNDS = {
    "Bell": "/static/sounds/bell.mp3",
    "Reminder": "/static/sounds/reminder.mp3",
    "Warning": "/static/sounds/warning.mp3",
    "Success": "/static/sounds/success.mp3",
    "Alarm": "/static/sounds/alarm.mp3",
    "Silent": None
}


def ensure_upload_dir():
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


async def save_custom_sound(file: UploadFile, user_id: str) -> Dict[str, Any]:
    """Save an uploaded custom sound (MP3, WAV, OGG)."""
    ensure_upload_dir()

    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()

    if ext not in [".mp3", ".wav", ".ogg"]:
        return {"status": "failed", "reason": "Invalid file format. Only MP3, WAV, and OGG are allowed."}

    # Store with raw filename or user prefix
    file_path = os.path.join(settings.UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    web_url = f"/static/uploads/sounds/{filename}"
    logger.info(f"Saved custom notification sound: {filename}")

    return {
        "status": "success",
        "sound_name": filename,
        "filename": filename,
        "file_path": file_path,
        "url": web_url
    }


def list_all_sounds(user_id: str = "dharanivasan") -> Dict[str, Any]:
    """Scans upload directory and returns system + custom sound options."""
    ensure_upload_dir()
    custom_sounds = []

    try:
        for f in os.listdir(settings.UPLOAD_DIR):
            ext = os.path.splitext(f)[1].lower()
            if ext in [".mp3", ".wav", ".ogg"]:
                custom_sounds.append({
                    "name": f,
                    "type": "Custom",
                    "url": f"/static/uploads/sounds/{f}"
                })
    except Exception as err:
        logger.warning(f"Error scanning custom sound uploads: {err}")

    system_sounds_list = [
        {"name": k, "type": "System", "url": v} for k, v in SYSTEM_SOUNDS.items()
    ]

    return {
        "system_sounds": system_sounds_list,
        "custom_sounds": custom_sounds
    }


def resolve_notification_sound(sound_selection: str = None, default_sound_type: str = "Bell") -> Dict[str, Any]:
    """
    Step 5: Notification Sound Resolution Logic:
    Resolves custom sound file or standard system sound option.
    """
    ensure_upload_dir()

    if sound_selection and sound_selection.strip() and sound_selection != "None":
        # Check if sound_selection matches a custom uploaded file
        if os.path.exists(settings.UPLOAD_DIR):
            for f in os.listdir(settings.UPLOAD_DIR):
                if f == sound_selection or f.endswith(f"_{sound_selection}") or sound_selection in f:
                    return {
                        "type": "Custom",
                        "name": f,
                        "url": f"/static/uploads/sounds/{f}"
                    }

        # If passed as a full URL
        if sound_selection.startswith("/static/"):
            return {
                "type": "Custom" if "uploads" in sound_selection else "System",
                "name": os.path.basename(sound_selection),
                "url": sound_selection
            }
        # Check system sounds
        elif sound_selection in SYSTEM_SOUNDS:
            return {
                "type": "System",
                "name": sound_selection,
                "url": SYSTEM_SOUNDS.get(sound_selection)
            }

    sound_name = default_sound_type if default_sound_type in SYSTEM_SOUNDS else "Bell"
    return {
        "type": "System",
        "name": sound_name,
        "url": SYSTEM_SOUNDS.get(sound_name)
    }
