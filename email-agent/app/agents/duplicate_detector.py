from typing import Dict, Optional


def find_duplicate(store, incoming: Dict[str, object]) -> Optional[Dict[str, object]]:
    meetings = store.list_meetings()
    email_id = incoming.get("email_id")
    meeting_link = incoming.get("meeting_link") or incoming.get("meeting_url")
    title = incoming.get("title")
    date = incoming.get("date")

    for existing in meetings:
        # Match by email ID
        if email_id and existing.get("email_id") == email_id:
            return existing
        # Match by exact meeting URL
        if meeting_link and existing.get("meeting_link") == meeting_link:
            return existing
        # Match by identical title and date
        if title and date and existing.get("title") == title and existing.get("date") == date:
            return existing

    return None


def merge_meeting(existing: Dict[str, object], incoming: Dict[str, object]) -> Dict[str, object]:
    merged = dict(existing)

    # Determine status transition
    incoming_status = str(incoming.get("status", "")).lower()
    if incoming_status == "cancelled" or "cancel" in str(incoming.get("title", "")).lower():
        computed_status = "cancelled"
    elif (incoming.get("date") and incoming.get("date") != existing.get("date")) or (
        incoming.get("start_time") and incoming.get("start_time") != existing.get("start_time")
    ):
        computed_status = "updated"
    else:
        computed_status = existing.get("status", "scheduled")

    # Update non-null incoming fields
    for k, v in incoming.items():
        if v is not None and k not in ("id", "created_at", "status"):
            merged[k] = v

    merged["status"] = computed_status
    return merged
