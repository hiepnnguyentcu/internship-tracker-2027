"""Thin wrapper over the Google Sheets API v4 for the tracker spreadsheet."""
from __future__ import annotations

from pathlib import Path

import yaml
from googleapiclient.discovery import build

from google_auth import get_credentials

CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


def _load_sheet_id() -> str:
    config = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    sheet_id = config.get("sheet_id")
    if not sheet_id:
        raise RuntimeError(
            "config.yaml has no sheet_id set. Run `python scripts/setup_sheet.py` first."
        )
    return sheet_id


def _col_letter(index0: int) -> str:
    """0-based column index -> spreadsheet column letters (0 -> 'A', 26 -> 'AA')."""
    index = index0 + 1
    letters = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


class SheetsClient:
    def __init__(self, sheet_id: str | None = None):
        self.sheet_id = sheet_id or _load_sheet_id()
        self._service = build("sheets", "v4", credentials=get_credentials())
        self._sheets = self._service.spreadsheets()

    def _headers(self, tab: str) -> list[str]:
        values = (
            self._sheets.values()
            .get(spreadsheetId=self.sheet_id, range=f"{tab}!1:1")
            .execute()
            .get("values", [])
        )
        if not values:
            raise RuntimeError(f"Tab '{tab}' has no header row.")
        return values[0]

    def read_tab(self, tab: str) -> list[dict]:
        values = (
            self._sheets.values()
            .get(spreadsheetId=self.sheet_id, range=tab)
            .execute()
            .get("values", [])
        )
        if not values:
            return []
        headers, *rows = values
        out = []
        for row in rows:
            padded = row + [""] * (len(headers) - len(row))
            out.append(dict(zip(headers, padded)))
        return out

    def append_row(self, tab: str, row: dict) -> None:
        headers = self._headers(tab)
        ordered = [str(row.get(h, "")) for h in headers]
        self._sheets.values().append(
            spreadsheetId=self.sheet_id,
            range=tab,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [ordered]},
        ).execute()

    def update_cell(self, tab: str, row_index: int, col_name: str, value) -> None:
        """row_index is 1-based over data rows (1 = first row under the header)."""
        headers = self._headers(tab)
        if col_name not in headers:
            raise ValueError(f"Column '{col_name}' not found in tab '{tab}'.")
        col_letter = _col_letter(headers.index(col_name))
        sheet_row = row_index + 1  # +1 to skip the header row
        self._sheets.values().update(
            spreadsheetId=self.sheet_id,
            range=f"{tab}!{col_letter}{sheet_row}",
            valueInputOption="RAW",
            body={"values": [[value]]},
        ).execute()

    def append_rows(self, tab: str, rows: list[dict]) -> None:
        """Appends many rows in a single API call. The Sheets API default quota
        is 60 write requests/min/user — looping append_row() per row blows
        through that well before a few hundred rows are written."""
        if not rows:
            return
        headers = self._headers(tab)
        values = [[str(row.get(h, "")) for h in headers] for row in rows]
        self._sheets.values().append(
            spreadsheetId=self.sheet_id,
            range=tab,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()

    def batch_update_cells(self, tab: str, updates: list[tuple[int, str, object]]) -> None:
        """Updates many (row_index, col_name, value) cells in a single API call."""
        if not updates:
            return
        headers = self._headers(tab)
        data = []
        for row_index, col_name, value in updates:
            if col_name not in headers:
                raise ValueError(f"Column '{col_name}' not found in tab '{tab}'.")
            col_letter = _col_letter(headers.index(col_name))
            sheet_row = row_index + 1
            data.append({"range": f"{tab}!{col_letter}{sheet_row}", "values": [[value]]})
        self._sheets.values().batchUpdate(
            spreadsheetId=self.sheet_id,
            body={"valueInputOption": "RAW", "data": data},
        ).execute()

    def find_rows(self, tab: str, **match) -> list[tuple[int, dict]]:
        rows = self.read_tab(tab)
        out = []
        for idx, row in enumerate(rows, start=1):
            if all(str(row.get(k, "")) == str(v) for k, v in match.items()):
                out.append((idx, row))
        return out

    def list_tab_titles(self) -> list[str]:
        meta = self._sheets.get(spreadsheetId=self.sheet_id).execute()
        return [s["properties"]["title"] for s in meta.get("sheets", [])]

    def create_tab(self, tab: str, headers: list[str]) -> None:
        """Idempotent: no-ops if the tab already exists."""
        if tab in self.list_tab_titles():
            return
        self._sheets.batchUpdate(
            spreadsheetId=self.sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": tab}}}]},
        ).execute()
        self._sheets.values().update(
            spreadsheetId=self.sheet_id,
            range=f"{tab}!A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()
