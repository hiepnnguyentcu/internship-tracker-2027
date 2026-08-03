"""Creates the tracker spreadsheet with all 9 tabs + header rows, and writes
the resulting sheet_id back into config.yaml. Idempotent: safe to re-run —
it verifies/completes tabs rather than creating a duplicate spreadsheet."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402

from google_auth import get_credentials  # noqa: E402
from sheets_client import SheetsClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"

TABS: dict[str, list[str]] = {
    "Resumes": ["resume_id", "track", "variant", "email_used", "phone_used", "drive_link", "notes"],
    "Applications": [
        "app_id", "date_applied", "company", "role_title", "source", "job_url",
        "resume_id", "referral", "referral_name", "current_stage",
        "current_stage_date", "oa_due_date", "notes",
    ],
    "StageEvents": ["event_id", "app_id", "stage", "date", "notes"],
    "EmailTemplates": ["template_id", "subject", "body", "notes"],
    "ColdEmails": [
        "contact_id", "company", "recruiter_name", "recruiter_email", "template_id",
        "status", "queued_at", "date_sent", "gmail_thread_id", "last_checked_date", "notes",
    ],
    "ActionItems": ["item_id", "type", "ref_id", "due_date", "done", "notes"],
    "CompanyNotes": [
        "company", "target_tier", "interview_process_notes", "culture_notes",
        "key_people", "prep_links", "last_updated",
    ],
    "TargetCompanies": ["company", "tier", "notes"],
    "ListingsSeen": [
        "listing_key", "source_repo", "company", "role", "location", "url",
        "date_first_seen", "emailed",
    ],
}


def _load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text()) or {}


def _save_config(config: dict) -> None:
    CONFIG_PATH.write_text(yaml.safe_dump(config, sort_keys=False))


def main() -> None:
    config = _load_config()
    service = build("sheets", "v4", credentials=get_credentials())

    sheet_id = config.get("sheet_id")
    if sheet_id:
        print(f"config.yaml already has sheet_id={sheet_id}; verifying tabs instead of creating a new sheet.")
    else:
        spreadsheet = service.spreadsheets().create(
            body={"properties": {"title": "Internship Tracker 2027"}}
        ).execute()
        sheet_id = spreadsheet["spreadsheetId"]
        default_sheet_id = spreadsheet["sheets"][0]["properties"]["sheetId"]
        first_tab = next(iter(TABS))

        # Rename the auto-created "Sheet1" into our first tab instead of
        # leaving a stray empty sheet around.
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={
                "requests": [
                    {
                        "updateSheetProperties": {
                            "properties": {"sheetId": default_sheet_id, "title": first_tab},
                            "fields": "title",
                        }
                    }
                ]
            },
        ).execute()
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{first_tab}!A1",
            valueInputOption="RAW",
            body={"values": [TABS[first_tab]]},
        ).execute()

        config["sheet_id"] = sheet_id
        _save_config(config)
        print(f"Created new spreadsheet: {sheet_id}")

    client = SheetsClient(sheet_id=sheet_id)
    existing = set(client.list_tab_titles())
    for tab, headers in TABS.items():
        if tab in existing:
            print(f"  tab '{tab}' already exists, skipping")
            continue
        client.create_tab(tab, headers)
        print(f"  created tab '{tab}'")

    print(f"\nSheet URL: https://docs.google.com/spreadsheets/d/{sheet_id}/edit")


if __name__ == "__main__":
    main()
