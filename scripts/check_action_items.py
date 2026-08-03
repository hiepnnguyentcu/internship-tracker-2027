"""Scans Applications for stage-stalled rows (no movement in
config.action_items.stale_application_days) and creates a follow-up
ActionItems row for each, unless one is already open (done=N) for that
application — so re-running doesn't pile up duplicate flags.

Usage:
    python scripts/check_action_items.py
"""
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from sheets_client import SheetsClient  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
TERMINAL_STAGES = {"Offer", "Rejected", "Ghosted"}


def main() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text())
    stale_days = config.get("action_items", {}).get("stale_application_days", 14)

    sheets = SheetsClient()
    applications = sheets.read_tab("Applications")
    action_items = sheets.read_tab("ActionItems")

    open_follow_ups = {
        row["ref_id"]
        for row in action_items
        if row.get("type") == "Application Follow-up" and row.get("done") == "N"
    }

    next_item_n = 0
    for row in action_items:
        item_id = row.get("item_id", "")
        if item_id.startswith("I") and item_id[1:].isdigit():
            next_item_n = max(next_item_n, int(item_id[1:]))
    next_item_n += 1

    today = date.today()
    new_rows = []
    for app in applications:
        if app.get("current_stage") in TERMINAL_STAGES:
            continue
        if app.get("app_id") in open_follow_ups:
            continue

        stage_date = app.get("current_stage_date", "")
        if not stage_date:
            continue
        days_stale = (today - datetime.strptime(stage_date, "%Y-%m-%d").date()).days
        if days_stale > stale_days:
            new_rows.append(
                {
                    "item_id": f"I{next_item_n:04d}",
                    "type": "Application Follow-up",
                    "ref_id": app["app_id"],
                    "due_date": today.isoformat(),
                    "done": "N",
                    "notes": f"{app['company']} — {app['role_title']} stuck at '{app['current_stage']}' for {days_stale}d",
                }
            )
            next_item_n += 1

    if new_rows:
        sheets.append_rows("ActionItems", new_rows)

    print(f"Checked {len(applications)} application(s): {len(new_rows)} new follow-up(s) flagged.")


if __name__ == "__main__":
    main()
