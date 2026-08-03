"""Computes the live 'apply queue': ListingsSeen rows with no matching
Applications row yet (matched by job URL).

JD-match scoring and the "needs tweak" flag both depend on real resume TEXT,
which requires the Drive/Docs client. As of sub-chunk A this still isn't
built for scoring purposes (sub-chunk B only adds PDF export, not text
extraction for scoring) — both show as unavailable ("—") rather than faking
a number. Deliberate stub, not an oversight — see MILESTONES.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from sheets_client import SheetsClient


@dataclass
class QueueItem:
    listing_key: str
    company: str
    role: str
    location: str
    source_repo: str
    url: str
    date_first_seen: str
    jd_match_score: float | None = None  # None = not yet available
    needs_tweak: bool | None = None  # None = not yet available


def load_queue(sheets: SheetsClient | None = None) -> list[QueueItem]:
    sheets = sheets or SheetsClient()
    listings = sheets.read_tab("ListingsSeen")
    applications = sheets.read_tab("Applications")
    applied_urls = {app.get("job_url") for app in applications if app.get("job_url")}

    queue = [
        QueueItem(
            listing_key=listing.get("listing_key", ""),
            company=listing.get("company", ""),
            role=listing.get("role", ""),
            location=listing.get("location", ""),
            source_repo=listing.get("source_repo", ""),
            url=listing.get("url", ""),
            date_first_seen=listing.get("date_first_seen", ""),
        )
        for listing in listings
        if listing.get("url") not in applied_urls
    ]
    queue.sort(key=lambda item: item.date_first_seen, reverse=True)
    return queue


def load_resumes(sheets: SheetsClient | None = None) -> list[dict]:
    sheets = sheets or SheetsClient()
    return sheets.read_tab("Resumes")


def find_queue_item(listing_key: str, sheets: SheetsClient | None = None) -> QueueItem | None:
    for item in load_queue(sheets):
        if item.listing_key == listing_key:
            return item
    return None
