"""Checks every 'Sent' cold email for a reply and flags unanswered ones past
the stale threshold as follow-up ActionItems.

Reply detection: each thread starts at exactly 1 message (the one we sent),
so a thread with more than 1 message means the recipient replied — no need
to store/compare a previous count.

All Sheets writes are batched into a single call regardless of how many
contacts are being checked (up to ~300 across a full cold-email campaign) —
per-row update_cell calls hit the Sheets API's 60-writes/min/user quota for
real during Milestone 2's first run; this avoids repeating that here.

Usage:
    python scripts/check_cold_emails.py
"""
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from gmail_client import GmailClient  # noqa: E402
from sheets_client import SheetsClient  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def main() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text())
    stale_days = config.get("action_items", {}).get("stale_cold_email_days", 6)

    sheets = SheetsClient()
    cold_emails = sheets.read_tab("ColdEmails")
    action_items = sheets.read_tab("ActionItems")

    existing_follow_ups = {row["ref_id"] for row in action_items if row.get("type") == "Cold-Email Follow-up"}
    next_item_n = 0
    for row in action_items:
        item_id = row.get("item_id", "")
        if item_id.startswith("I") and item_id[1:].isdigit():
            next_item_n = max(next_item_n, int(item_id[1:]))
    next_item_n += 1

    gmail = GmailClient()
    today = date.today()

    cell_updates: list[tuple[int, str, object]] = []
    follow_up_rows: list[dict] = []
    replied_count = 0
    sent_rows_checked = 0

    for row_index, row in enumerate(cold_emails, start=1):
        if row.get("status") != "Sent":
            continue
        sent_rows_checked += 1

        thread_id = row.get("gmail_thread_id")
        if not thread_id:
            continue

        message_count = gmail.get_thread_message_count(thread_id)
        cell_updates.append((row_index, "last_checked_date", today.isoformat()))

        if message_count > 1:
            cell_updates.append((row_index, "status", "Replied"))
            replied_count += 1
            print(f"  {row['contact_id']} ({row['recruiter_name']}, {row['company']}): replied")
            continue

        date_sent = row.get("date_sent", "")
        if not date_sent:
            continue
        days_since_sent = (today - datetime.strptime(date_sent, "%Y-%m-%d").date()).days
        if days_since_sent > stale_days and row["contact_id"] not in existing_follow_ups:
            follow_up_rows.append(
                {
                    "item_id": f"I{next_item_n:04d}",
                    "type": "Cold-Email Follow-up",
                    "ref_id": row["contact_id"],
                    "due_date": today.isoformat(),
                    "done": "N",
                    "notes": f"No reply from {row['recruiter_name']} ({row['company']}) after {days_since_sent}d",
                }
            )
            next_item_n += 1

    if cell_updates:
        sheets.batch_update_cells("ColdEmails", cell_updates)
    if follow_up_rows:
        sheets.append_rows("ActionItems", follow_up_rows)

    print(
        f"Checked {sent_rows_checked} sent email(s): "
        f"{replied_count} replied, {len(follow_up_rows)} new follow-up(s) flagged."
    )


if __name__ == "__main__":
    main()
