import httpx
import json

examples = [
    "Project review meeting tomorrow at 2 PM for 1 hour.",
    "AI Hackathon registration deadline is August 15 at 11:59 PM.",
    "Submit DBMS assignment on Friday. Remind me one day before.",
    "Internship interview on August 20 from 10 AM to 11 AM.",
    "Complete the presentation by September 5. Priority: High.",
    "Google Meet with project team tomorrow at 7 PM.\nMeeting link: https://meet.google.com/xxx-xxxx-xxx\nPriority: High"
]

for i, text in enumerate(examples, 1):
    res = httpx.post("http://127.0.0.1:8005/api/calendar/analyze-manual-input", json={"text": text})
    data = res.json()
    evt = data.get("event", {})
    print(f"=== EXAMPLE {i} ===")
    print(f"Input: {text.splitlines()[0]}")
    print(f"Status: {data.get('status')}")
    print(f"Title: {evt.get('title')}")
    print(f"Type: {evt.get('event_type')}")
    print(f"Start Date: {evt.get('start_date')}, Time: {evt.get('start_time')}")
    print(f"End Date: {evt.get('end_date')}, Time: {evt.get('end_time')}")
    print(f"Deadline: {evt.get('deadline')}")
    print(f"Meeting URL: {evt.get('meeting_url')}")
    print(f"Priority: {evt.get('priority')}")
    print(f"Reminders: {evt.get('reminders')}")
    print(f"Needs Clarification: {data.get('needs_clarification')}\n")
