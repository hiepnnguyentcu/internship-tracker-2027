"""Logs a job application. If stage=OA, also creates an ActionItems row and
a Calendar reminder for the OA due date. The core logic is exposed as
`record_application()` so both this CLI and the desktop app (Phase 2) call
the exact same code path instead of duplicating it.

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
from id_utils import next_id  # noqa: E402
from jd_keyword_check import fetch_jd_text, overlap_score, top_missing_keywords  # noqa: E402
from sheets_client import SheetsClient  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
STAGES = ["Applied", "OA", "Phone Screen", "Onsite", "Offer", "Rejected", "Ghosted"]


def record_application(
    sheets: SheetsClient,
    company: str,
    role: str,
    resume_id: str,
    stage: str = "Applied",
    job_url: str = "",
    referral: str = "N",
    referral_name: str = "",
    source: str = "",
    date_applied: str | None = None,
    oa_due_date: str = "",
    notes: str = "",
) -> dict:
    """Writes the Applications + StageEvents rows (and, for stage=OA, the
    ActionItems row + Calendar reminder). Shared by the CLI and the desktop
    app. Returns {"app_id", "warnings": [...], "calendar_event_id" (if OA)}.
    """
    warnings = []
    known_resumes = {row["resume_id"] for row in sheets.read_tab("Resumes")}
    if resume_id not in known_resumes:
        warnings.append(f"resume_id '{resume_id}' not found in Resumes tab (logging anyway)")

    if stage == "OA" and not oa_due_date:
        raise ValueError("oa_due_date is required when stage='OA'")

    date_applied = date_applied or date.today().isoformat()
    app_id = next_id(sheets, "Applications", "app_id", "A")

    sheets.append_row(
        "Applications",
        {
            "app_id": app_id,
            "date_applied": date_applied,
            "company": company,
            "role_title": role,
            "source": source,
            "job_url": job_url,
            "resume_id": resume_id,
            "referral": referral,
            "referral_name": referral_name,
            "current_stage": stage,
            "current_stage_date": date_applied,
            "oa_due_date": oa_due_date,
            "notes": notes,
        },
    )

    event_id = next_id(sheets, "StageEvents", "event_id", "E")
    sheets.append_row(
        "StageEvents",
        {"event_id": event_id, "app_id": app_id, "stage": stage, "date": date_applied, "notes": notes},
    )

    result = {"app_id": app_id, "warnings": warnings}

    if stage == "OA":
        item_id = next_id(sheets, "ActionItems", "item_id", "I")
        sheets.append_row(
            "ActionItems",
            {
                "item_id": item_id,
                "type": "OA Deadline",
                "ref_id": app_id,
                "due_date": oa_due_date,
                "done": "N",
                "notes": f"OA for {company} — {role}",
            },
        )

        config = yaml.safe_load(CONFIG_PATH.read_text())
        reminder_minutes = config.get("action_items", {}).get("oa_reminder_minutes_before", [1440, 120])
        tz_name = config.get("timezone", "America/Los_Angeles")
        # Anchor "9am" to the *configured* timezone, not whatever timezone the
        # machine running this happens to be in (matters once this runs on a
        # scheduled cloud routine or a desktop app, not just a personal laptop).
        due = datetime.strptime(oa_due_date, "%Y-%m-%d").replace(hour=9, minute=0, tzinfo=ZoneInfo(tz_name))

        calendar = CalendarClient()
        cal_event_id = calendar.create_event(
            title=f"OA due: {company} — {role}",
            start=due,
            reminder_minutes_before=reminder_minutes,
            description=f"Application {app_id}. {notes}",
        )
        result["action_item_id"] = item_id
        result["calendar_event_id"] = cal_event_id

    return result


def check_jd_match(job_url: str, resume_text: str, threshold: float) -> dict | None:
    """Fetches the JD and scores it against resume_text. Returns None if it
    couldn't be assessed (fetch failure, empty page — NFR1: never raise),
    else {"score", "warning": bool, "missing_keywords"}."""
    if not job_url or not resume_text:
        return None
    try:
        jd_text = fetch_jd_text(job_url)
    except Exception:  # noqa: BLE001 - never let this crash the caller (NFR1)
        return None
    if not jd_text.strip():
        return None

    score = overlap_score(resume_text, jd_text)
    if score < threshold:
        return {"score": score, "warning": True, "missing_keywords": top_missing_keywords(resume_text, jd_text)}
    return {"score": score, "warning": False, "missing_keywords": []}


def _print_jd_check(job_url: str, resume_text_file: str, threshold: float) -> None:
    if not job_url or not resume_text_file:
        return
    resume_path = Path(resume_text_file)
    if not resume_path.exists():
        print(f"  [jd-check] resume text file not found: {resume_path}, skipping check")
        return

    result = check_jd_match(job_url, resume_path.read_text(), threshold)
    if result is None:
        print("  [jd-check] couldn't fetch/assess job description, skipping check")
    elif result["warning"]:
        print(f"  [jd-check] WARNING: low keyword overlap ({result['score']:.0%}). Missing: {', '.join(result['missing_keywords'])}")
    else:
        print(f"  [jd-check] keyword overlap looks fine ({result['score']:.0%}).")


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

    oa_due_date = args.oa_due_date
    if args.stage == "OA" and not oa_due_date:
        oa_due_date = input("OA due date (YYYY-MM-DD): ").strip()

    result = record_application(
        sheets,
        company=args.company,
        role=args.role,
        resume_id=args.resume_id,
        stage=args.stage,
        job_url=args.job_url,
        referral=args.referral,
        referral_name=args.referral_name,
        source=args.source,
        date_applied=args.date,
        oa_due_date=oa_due_date,
        notes=args.notes,
    )

    for warning in result["warnings"]:
        print(f"  [warn] {warning}")
    print(f"Logged application {result['app_id']}: {args.company} — {args.role} [{args.stage}]")
    if "calendar_event_id" in result:
        print(f"  Created ActionItems row {result['action_item_id']} and Calendar event {result['calendar_event_id']} for OA due {oa_due_date}")

    config = yaml.safe_load(CONFIG_PATH.read_text())
    threshold = config.get("action_items", {}).get("jd_overlap_warning_threshold", 0.08)
    _print_jd_check(args.job_url, args.resume_text_file, threshold)


if __name__ == "__main__":
    main()
