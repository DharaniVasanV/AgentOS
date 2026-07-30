from typing import List

class ReminderService:
    @staticmethod
    def get_default_reminders(event_type: str, priority: str = "MEDIUM") -> List[int]:
        """
        Determines appropriate reminder intervals (in minutes before event/deadline)
        based on event type and priority level.
        
        Priority Rules:
        - URGENT / CRITICAL: Reminders at 7 days, 3 days, 1 day, 6 hours, 1 hour, 15 mins, 0 mins
        - HIGH: Reminders at 3 days, 1 day, 3 hours, 1 hour, 15 mins, 0 mins
        - MEDIUM: Reminders at 1 day, 2 hours, 30 mins, 0 mins
        - LOW: Reminders at 1 day, 1 hour, 0 mins
        """
        reminders = set()
        p = (priority or "MEDIUM").upper()

        if p in ("URGENT", "CRITICAL"):
            reminders.update([10080, 4320, 1440, 360, 60, 15, 0])
        elif p == "HIGH":
            reminders.update([4320, 1440, 180, 60, 15, 0])
        elif p == "LOW":
            reminders.update([1440, 60, 0])
        else:
            reminders.update([1440, 120, 30, 0])

        et = (event_type or "").upper()
        if et == "MEETING":
            reminders.update([30, 10, 0])
        elif et in ("APPLICATION_DEADLINE", "HACKATHON", "INTERNSHIP", "CERTIFICATION", "TASK_DEADLINE"):
            reminders.update([4320, 1440, 60, 0])

        return sorted(list(reminders), reverse=True)
