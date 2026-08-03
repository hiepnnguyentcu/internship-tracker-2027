"""Thin wrapper over the Google Calendar API for OA-deadline/interview reminders."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import yaml
from googleapiclient.discovery import build

from google_auth import get_credentials

CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"
CALENDAR_ID = "primary"
DEFAULT_TIMEZONE = "America/Los_Angeles"


def _load_timezone() -> str:
    config = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    return config.get("timezone", DEFAULT_TIMEZONE)


class CalendarClient:
    def __init__(self):
        self._service = build("calendar", "v3", credentials=get_credentials())
        self._timezone = _load_timezone()

    def create_event(
        self,
        title: str,
        start: datetime,
        reminder_minutes_before: int | list[int],
        description: str = "",
    ) -> str:
        """Creates a 30-minute calendar hold at `start` with popup reminder(s).
        Pass a list (e.g. [1440, 120] for 24h and 2h before) for more than one
        reminder. Returns the created event's id.
        """
        end = start + timedelta(minutes=30)
        offsets = reminder_minutes_before if isinstance(reminder_minutes_before, list) else [reminder_minutes_before]
        body = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": self._timezone},
            "end": {"dateTime": end.isoformat(), "timeZone": self._timezone},
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": m} for m in offsets],
            },
        }
        event = (
            self._service.events()
            .insert(calendarId=CALENDAR_ID, body=body)
            .execute()
        )
        return event["id"]
