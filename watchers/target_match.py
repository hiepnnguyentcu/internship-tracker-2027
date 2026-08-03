"""Flags new listings whose company matches the user's TargetCompanies tab."""
from __future__ import annotations

from watchers.dedup import normalize_key


def _normalize_company(company: str) -> str:
    return normalize_key(company, "")


def load_target_companies(sheets_client) -> set[str]:
    rows = sheets_client.read_tab("TargetCompanies")
    return {_normalize_company(row["company"]) for row in rows if row.get("company")}


def is_target(company: str, target_set: set[str]) -> bool:
    return _normalize_company(company) in target_set
