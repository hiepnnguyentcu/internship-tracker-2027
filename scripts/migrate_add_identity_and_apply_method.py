"""One-time migration for Phase 2 sub-chunk B: adds the Identity tab and an
apply_method column on Applications. Idempotent — safe to re-run.

Usage:
    python scripts/migrate_add_identity_and_apply_method.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sheets_client import SheetsClient  # noqa: E402

IDENTITY_HEADERS = [
    "identity_id", "full_name", "school", "grad_year", "linkedin_url",
    "work_authorization", "needs_sponsorship", "notes",
]


def main() -> None:
    sheets = SheetsClient()

    sheets.create_tab("Identity", IDENTITY_HEADERS)
    print("Identity tab: ensured present.")

    sheets.add_column("Applications", "apply_method")
    print("Applications.apply_method: ensured present.")

    # Backfill existing rows with no apply_method set — everything logged so
    # far was applied to manually (auto-apply didn't exist yet).
    updates = []
    for row_index, row in enumerate(sheets.read_tab("Applications"), start=1):
        if not row.get("apply_method"):
            updates.append((row_index, "apply_method", "Manual"))
    if updates:
        sheets.batch_update_cells("Applications", updates)
        print(f"Backfilled apply_method=Manual for {len(updates)} existing row(s).")


if __name__ == "__main__":
    main()
