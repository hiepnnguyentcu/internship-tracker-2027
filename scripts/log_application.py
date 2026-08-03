"""Logs a job application. If --stage OA, also creates an ActionItems row
and a Calendar reminder for the OA due date. If --job-url and
--resume-text-file are both given, runs a keyword-overlap sanity check
against the job description (never blocks logging — just warns).

Usage:
    python scripts/log_application.py --company Stripe --role "SWE Intern" \\
        --resume-id R2 --referral N --source SimplifyJobs --stage Applied \\
        --job-url https://... [--resume-text-file resume.txt]

    python scripts/log_application.py --company Airbnb --role "SWE Intern" \\
        --resume-id R2 --stage OA --oa-due-date 2026-08-10
"""
import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from calendar_client import CalendarClient  # noqa: E402
from id_utils import next_id as _next_id  # noqa: E402
from jd_keyword_check import fetch_jd_text, overlap_score, top_missing_keywords  # noqa: E402
from sheets_client import SheetsClient  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
STAGES = ["Applied", "OA", "Phone Screen", "Onsite", "Offer", "Rejected", "Ghosted"]


def _maybe_check_jd_match(job_url: str, resume_text_file: str, threshold: float) -> None:
    if not job_url or not resume_text_file:
        return

    resume_path = Path(resume_text_file)
    if not resume_path.exists():
        print(f"  [jd-check] resume text file not found: {resume_path}, skipping check")
        return

    try:
        jd_text = fetch_jd_text(job_url)
    except Exception as exc:  # noqa: BLE001 - never let this crash the logging flow (NFR1)
        print(f"  [jd-check] couldn't fetch job description ({exc!r}), skipping check")
        return

    if not jd_text.strip():
        print("  [jd-check] job description page had no extractable text, skipping check")
        return

    resume_text = resume_path.read_text()
    score = overlap_score(resume_text, jd_text)
    if score < threshold:
        missing = top_missing_keywords(resume_text, jd_text)
        print(f"  [jd-check] WARNING: low keyword overlap ({score:.0%}). Missing: {', '.join(missing)}")
    else:
        print(f"  [jd-check] keyword overlap looks fine ({score:.0%}).")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--job-url", default="")
    parser.add_argument("--resume-id", required=True)
    parser.add_argument("--referral", choices=["Y", "N"], default="N")
    parser.add_argument("--referral-name", default="")
    parser.add_argument("--source", default="")
    parser.add_argument("--stage", choices=STAGES, default="Applied")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--oa-due-date", default="", help="YYYY-MM-DD. Prompted for if --stage OA and omitted.")
    parser.add_argument("--notes", default="")
    parser.add_argument(
        "--resume-text-file", default="",
        help="Local .txt copy of the resume, for the JD-keyword sanity check.",
    )
    args = parser.parse_args()

    sheets = SheetsClient()

    known_resumes = {row["resume_id"] for row in sheets.read_tab("Resumes")}
    if args.resume_id not in known_resumes:
        print(f"  [warn] resume_id '{args.resume_id}' not found in Resumes tab (logging anyway)")

    app_id = _next_id(sheets, "Applications", "app_id", "A")

    oa_due_date = args.oa_due_date
    if args.stage == "OA" and not oa_due_date:
        oa_due_date = input("OA due date (YYYY-MM-DD): ").strip()

    sheets.append_row(
        "Applications",
        {
            "app_id": app_id,
            "date_applied": args.date,
            "company": args.company,
            "role_title": args.role,
            "source": args.source,
            "job_url": args.job_url,
            "resume_id": args.resume_id,
            "referral": args.referral,
            "referral_name": args.referral_name,
            "current_stage": args.stage,
            "current_stage_date": args.date,
            "oa_due_date": oa_due_date,
            "notes": args.notes,
        },
    )

    event_id = _next_id(sheets, "StageEvents", "event_id", "E")
    sheets.append_row(
        "StageEvents",
        {"event_id": event_id, "app_id": app_id, "stage": args.stage, "date": args.date, "notes": args.notes},
    )

    print(f"Logged application {app_id}: {args.company} — {args.role} [{args.stage}]")

    if args.stage == "OA":
        item_id = _next_id(sheets, "ActionItems", "item_id", "I")
        sheets.append_row(
            "ActionItems",
            {
                "item_id": item_id,
                "type": "OA Deadline",
                "ref_id": app_id,
                "due_date": oa_due_date,
                "done": "N",
                "notes": f"OA for {args.company} — {args.role}",
            },
        )

        config = yaml.safe_load(CONFIG_PATH.read_text())
        reminder_minutes = config.get("action_items", {}).get("oa_reminder_minutes_before", [1440, 120])
        tz_name = config.get("timezone", "America/Los_Angeles")
        # Anchor "9am" to the *configured* timezone, not whatever timezone the
        # machine running this script happens to be in (matters once this
        # runs on a scheduled cloud routine instead of a personal laptop).
        due = datetime.strptime(oa_due_date, "%Y-%m-%d").replace(hour=9, minute=0, tzinfo=ZoneInfo(tz_name))

        calendar = CalendarClient()
        cal_event_id = calendar.create_event(
            title=f"OA due: {args.company} — {args.role}",
            start=due,
            reminder_minutes_before=reminder_minutes,
            description=f"Application {app_id}. {args.notes}",
        )
        print(f"  Created ActionItems row {item_id} and Calendar event {cal_event_id} for OA due {oa_due_date}")

    config = yaml.safe_load(CONFIG_PATH.read_text())
    threshold = config.get("action_items", {}).get("jd_overlap_warning_threshold", 0.08)
    _maybe_check_jd_match(args.job_url, args.resume_text_file, threshold)


if __name__ == "__main__":
    main()
