"""Parses the machine-readable `listings.json` format exposed by SimplifyJobs-
style repos (confirmed present on SimplifyJobs and vanshb03's `dev` branch)."""
from __future__ import annotations

from watchers.models import Listing


def parse_json_listings(raw_json: list[dict], category_filter: list[str]) -> list[Listing]:
    out: list[Listing] = []
    for entry in raw_json:
        if not entry.get("is_visible", False):
            continue
        # `is_visible` is true for ~99.9% of entries in these feeds (it just
        # means "not moderator-hidden", not "currently open") — `active` is
        # the real "still accepting applications" signal. Without this,
        # every closed posting from prior cycles counts as "new" forever.
        if not entry.get("active", False):
            continue
        if category_filter and entry.get("category") not in category_filter:
            continue

        locations = entry.get("locations") or []
        out.append(
            Listing(
                id=str(entry.get("id", "")),
                source=str(entry.get("source", "")),
                company=str(entry.get("company_name", "")),
                title=str(entry.get("title", "")),
                location=str(locations[0]) if locations else "",
                url=str(entry.get("url", "")),
                date_posted=str(entry.get("date_posted", "")),
            )
        )
    return out
