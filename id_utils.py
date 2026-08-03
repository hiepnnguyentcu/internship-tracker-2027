"""Shared incrementing id generator (e.g. A0001, E0001, C0001) used across
the log_*/queue_* scripts. Single-row use only — for generating many ids in
one batch, compute the starting max once and increment locally instead of
calling this in a loop (each call re-reads the sheet)."""
from __future__ import annotations

from sheets_client import SheetsClient


def next_id(sheets: SheetsClient, tab: str, id_col: str, prefix: str) -> str:
    rows = sheets.read_tab(tab)
    max_n = 0
    for row in rows:
        value = row.get(id_col, "")
        if value.startswith(prefix) and value[len(prefix):].isdigit():
            max_n = max(max_n, int(value[len(prefix):]))
    return f"{prefix}{max_n + 1:04d}"
