"""Sends up to `cold_email.throttle_per_run` queued cold emails per run,
rendering the merge-field template and recording the Gmail thread id for
later reply detection. Run this on a recurring schedule to get natural
pacing across a company's recruiter list instead of firing all at once.

Usage:
    python scripts/send_cold_emails.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from gmail_client import GmailClient  # noqa: E402
from sheets_client import SheetsClient  # noqa: E402
from template_engine import render  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def main() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text())
    throttle = config.get("cold_email", {}).get("throttle_per_run", 3)

    sheets = SheetsClient()
    cold_emails = sheets.read_tab("ColdEmails")
    templates = {row["template_id"]: row for row in sheets.read_tab("EmailTemplates")}

    queued = [(idx, row) for idx, row in enumerate(cold_emails, start=1) if row.get("status") == "Queued"]
    queued.sort(key=lambda item: item[1].get("queued_at", ""))
    batch = queued[:throttle]

    if not batch:
        print("No queued cold emails. Nothing to do.")
        return

    gmail = GmailClient()
    today = date.today().isoformat()
    sent_count = 0

    for row_index, row in batch:
        template = templates.get(row["template_id"])
        if template is None:
            print(f"  [skip] {row['contact_id']}: unknown template_id '{row['template_id']}'")
            continue

        context = {"recruiter_name": row["recruiter_name"], "company": row["company"]}
        try:
            subject = render(template["subject"], context)
            body = render(template["body"], context)
        except ValueError as exc:
            # NFR4: fail loud before send, never send a half-broken template
            print(f"  [ABORT] {row['contact_id']}: template render failed ({exc}) - not sending")
            continue

        message_id, thread_id = gmail.send(to=row["recruiter_email"], subject=subject, body_html=body)

        sheets.batch_update_cells(
            "ColdEmails",
            [
                (row_index, "status", "Sent"),
                (row_index, "date_sent", today),
                (row_index, "gmail_thread_id", thread_id),
            ],
        )
        sent_count += 1
        print(f"  Sent to {row['recruiter_name']} <{row['recruiter_email']}> ({row['company']}) - thread {thread_id}")

    print(f"Sent {sent_count}/{len(batch)} queued email(s) this run.")


if __name__ == "__main__":
    main()
