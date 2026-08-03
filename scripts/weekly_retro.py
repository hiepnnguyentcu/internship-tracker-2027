"""Weekly momentum email: this week vs. last week, reusing stats_report's
data-loading logic. Meant for a separate weekly (not hourly) schedule, kept
distinct from the constant new-listings/action-items digest.

Usage:
    python scripts/weekly_retro.py
"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from gmail_client import GmailClient  # noqa: E402
from sheets_client import SheetsClient  # noqa: E402
from stats_report import load_stats  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
INTERVIEW_STAGES = {"Phone Screen", "Onsite"}


def _count_in_window(rows: list[dict], date_field: str, start: date, end: date) -> int:
    count = 0
    for row in rows:
        raw = row.get(date_field, "")
        if not raw:
            continue
        try:
            d = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            continue
        if start <= d < end:
            count += 1
    return count


def _delta_str(curr: int, prev: int) -> str:
    if prev == 0:
        return "n/a" if curr == 0 else "new"
    return f"{(curr - prev) / prev:+.0%}"


def main() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text())
    sheets = SheetsClient()

    applications = sheets.read_tab("Applications")
    stage_events = sheets.read_tab("StageEvents")

    today = date.today()
    this_week_start = today - timedelta(days=7)
    last_week_start = today - timedelta(days=14)

    apps_this_week = _count_in_window(applications, "date_applied", this_week_start, today)
    apps_last_week = _count_in_window(applications, "date_applied", last_week_start, this_week_start)

    interview_events = [e for e in stage_events if e.get("stage") in INTERVIEW_STAGES]
    interviews_this_week = _count_in_window(interview_events, "date", this_week_start, today)
    interviews_last_week = _count_in_window(interview_events, "date", last_week_start, this_week_start)

    stats = load_stats(sheets)
    overall = stats["overall"].get("Overall", {"response_rate": 0.0, "total": 0})

    body = f"""
    <h2>Weekly Retro — {today.isoformat()}</h2>
    <p>Applications sent this week: <b>{apps_this_week}</b> (last week: {apps_last_week}, {_delta_str(apps_this_week, apps_last_week)})</p>
    <p>Interviews landed this week: <b>{interviews_this_week}</b> (last week: {interviews_last_week}, {_delta_str(interviews_this_week, interviews_last_week)})</p>
    <p>Overall response rate to date: <b>{overall['response_rate']:.0%}</b></p>
    <p>Total applications to date: <b>{stats['total_applications']}</b></p>
    """

    gmail = GmailClient()
    gmail.send(to=config["digest_email"], subject=f"Weekly Retro — {today.isoformat()}", body_html=body)
    print(
        f"Sent weekly retro: {apps_this_week} apps this week (prev {apps_last_week}), "
        f"{interviews_this_week} interviews this week (prev {interviews_last_week})."
    )


if __name__ == "__main__":
    main()
