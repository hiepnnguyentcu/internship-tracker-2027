"""Milestone 1 acceptance check: verifies Sheets, Gmail, and Calendar access
all work end to end. Writes/sends real (clearly-labeled) test data."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from calendar_client import CalendarClient  # noqa: E402
from gmail_client import GmailClient  # noqa: E402
from sheets_client import SheetsClient  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def test_sheets() -> None:
    client = SheetsClient()
    dummy = {
        "resume_id": "SMOKE-TEST",
        "track": "Full-Stack",
        "variant": "A",
        "email_used": "test@example.com",
        "phone_used": "000-000-0000",
        "drive_link": "https://example.com",
        "notes": "smoke test row - safe to delete",
    }
    client.append_row("Resumes", dummy)
    matches = client.find_rows("Resumes", resume_id="SMOKE-TEST")
    assert matches, "appended row was not found on read-back"
    _, row = matches[-1]
    assert row["email_used"] == dummy["email_used"], f"round-trip mismatch: {row}"
    print("[PASS] Sheets: append_row + find_rows round-trip")


def test_gmail() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text())
    client = GmailClient()
    message_id, thread_id = client.send(
        to=config["digest_email"],
        subject="Internship Tracker — Milestone 1 smoke test",
        body_html="<p>If you're reading this, GmailClient.send works.</p>",
    )
    assert message_id and thread_id
    print(f"[PASS] Gmail: sent message {message_id} (thread {thread_id})")


def test_calendar() -> None:
    client = CalendarClient()
    start = datetime.now().astimezone() + timedelta(hours=1)
    event_id = client.create_event(
        title="Internship Tracker — Milestone 1 smoke test",
        start=start,
        reminder_minutes_before=10,
        description="Safe to delete.",
    )
    assert event_id
    print(f"[PASS] Calendar: created event {event_id} at {start.isoformat()}")


def main() -> None:
    test_sheets()
    test_gmail()
    test_calendar()
    print("\nAll smoke tests passed.")


if __name__ == "__main__":
    main()
