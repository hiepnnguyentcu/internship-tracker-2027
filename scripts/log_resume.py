"""Registers a resume version. Enforces version integrity: refuses to
silently overwrite an existing resume_id's linked file — bump the id instead
(e.g. R1 -> R1.1) if the resume content actually changed, so past
applications keep pointing at the exact version that was sent.

The core logic is exposed as `register_resume()` so both this CLI and the
desktop app (Phase 2) call the exact same code path.

Usage:
    python scripts/log_resume.py --resume-id R1 --track "Full-Stack" \\
        --variant A --email you@example.com --phone 555-555-5555 \\
        --drive-link https://drive.google.com/... [--notes "..."]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sheets_client import SheetsClient  # noqa: E402


class ResumeConflictError(Exception):
    """Raised when resume_id already exists with a different drive_link."""


def register_resume(
    sheets: SheetsClient,
    resume_id: str,
    track: str,
    variant: str,
    email: str,
    phone: str,
    drive_link: str,
    notes: str = "",
) -> str:
    """Returns 'registered', 'unchanged' (already identical), or raises
    ResumeConflictError if resume_id exists with a different drive_link."""
    matches = sheets.find_rows("Resumes", resume_id=resume_id)

    if matches:
        _, existing = matches[-1]
        if existing.get("drive_link") != drive_link:
            raise ResumeConflictError(
                f"resume_id '{resume_id}' already exists with a different drive_link "
                f"({existing.get('drive_link')!r} vs {drive_link!r}). If the resume content "
                "actually changed, register it under a NEW resume_id instead (e.g. bump "
                "R1 -> R1.1) so past applications keep pointing at the exact version that was sent."
            )
        return "unchanged"

    sheets.append_row(
        "Resumes",
        {
            "resume_id": resume_id,
            "track": track,
            "variant": variant,
            "email_used": email,
            "phone_used": phone,
            "drive_link": drive_link,
            "notes": notes,
        },
    )
    return "registered"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-id", required=True)
    parser.add_argument("--track", required=True, choices=["Full-Stack", "Low-Level Systems"])
    parser.add_argument("--variant", required=True, choices=["A", "B"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--phone", required=True)
    parser.add_argument("--drive-link", required=True)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    sheets = SheetsClient()
    try:
        outcome = register_resume(
            sheets, args.resume_id, args.track, args.variant, args.email, args.phone, args.drive_link, args.notes
        )
    except ResumeConflictError as exc:
        raise SystemExit(str(exc)) from exc

    if outcome == "unchanged":
        print(f"resume_id '{args.resume_id}' is already registered identically. No changes made.")
    else:
        print(f"Registered resume '{args.resume_id}' ({args.track} / variant {args.variant}).")


if __name__ == "__main__":
    main()
