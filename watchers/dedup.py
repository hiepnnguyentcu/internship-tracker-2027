"""Cross-repo dedup: the same posting can appear in more than one source repo
(SimplifyJobs and vanshb03 in particular are likely to overlap heavily)."""
from __future__ import annotations

import re

from watchers.models import Listing

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_key(company: str, title: str) -> str:
    combined = f"{company}|{title}".lower()
    return _NON_ALNUM_RE.sub("", combined)


def cross_repo_dedupe(listings: list[Listing]) -> list[Listing]:
    """First-seen wins: keeps the first listing for each normalized
    (company, title) pair, in input order."""
    seen: set[str] = set()
    out: list[Listing] = []
    for listing in listings:
        key = normalize_key(listing.company, listing.title)
        if key in seen:
            continue
        seen.add(key)
        out.append(listing)
    return out
