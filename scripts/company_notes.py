"""Lookup helper for the CompanyNotes tab (case-insensitive company match) —
used for a conversational "what do I know about Company X" flow.

Usage (CLI):
    python scripts/company_notes.py "Stripe"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sheets_client import SheetsClient  # noqa: E402


def lookup(company: str, sheets: SheetsClient | None = None) -> dict | None:
    sheets = sheets or SheetsClient()
    target = company.strip().lower()
    for row in sheets.read_tab("CompanyNotes"):
        if row.get("company", "").strip().lower() == target:
            return row
    return None


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/company_notes.py <company>")

    result = lookup(sys.argv[1])
    if result is None:
        print(f"No notes found for '{sys.argv[1]}'.")
        return

    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
