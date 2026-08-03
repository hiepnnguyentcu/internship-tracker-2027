"""Bulk-queues cold-email contacts from a CSV into ColdEmails (status=Queued).

CSV columns required: company, recruiter_name, recruiter_email, template_id

Usage:
    python scripts/queue_cold_emails.py contacts.csv
"""
import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sheets_client import SheetsClient  # noqa: E402

REQUIRED_COLUMNS = {"company", "recruiter_name", "recruiter_email", "template_id"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"CSV is missing required column(s): {sorted(missing)}")
        contacts = list(reader)

    if not contacts:
        print("CSV has no rows. Nothing to queue.")
        return

    sheets = SheetsClient()

    known_templates = {row["template_id"] for row in sheets.read_tab("EmailTemplates")}
    unknown = {c["template_id"] for c in contacts} - known_templates
    if unknown:
        raise SystemExit(f"Unknown template_id(s) not found in EmailTemplates: {sorted(unknown)}")

    # Compute the starting contact_id once and increment locally for the
    # whole batch — calling a per-row id lookup here would re-read the sheet
    # once per contact for no reason (and risks duplicate ids within the
    # same batch, since a fresh read wouldn't see rows appended moments ago).
    existing = sheets.read_tab("ColdEmails")
    max_n = 0
    for row in existing:
        cid = row.get("contact_id", "")
        if cid.startswith("C") and cid[1:].isdigit():
            max_n = max(max_n, int(cid[1:]))

    now = datetime.now().isoformat(timespec="seconds")
    rows_to_append = []
    for i, contact in enumerate(contacts, start=1):
        rows_to_append.append(
            {
                "contact_id": f"C{max_n + i:04d}",
                "company": contact["company"],
                "recruiter_name": contact["recruiter_name"],
                "recruiter_email": contact["recruiter_email"],
                "template_id": contact["template_id"],
                "status": "Queued",
                "queued_at": now,
                "date_sent": "",
                "gmail_thread_id": "",
                "last_checked_date": "",
                "notes": "",
            }
        )

    sheets.append_rows("ColdEmails", rows_to_append)
    print(f"Queued {len(rows_to_append)} contact(s): {rows_to_append[0]['contact_id']}..{rows_to_append[-1]['contact_id']}")


if __name__ == "__main__":
    main()
