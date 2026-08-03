"""Parses markdown-table-based listing repos (speedyapply, jobright-ai).

These two repos don't share a cell format: speedyapply uses raw HTML anchors
(`<a href="..."><strong>Company</strong></a>`) while jobright-ai uses bolded
markdown links (`**[Company](url)**`) plus a "↳" marker on continuation rows
that repeat the company above. This parser handles both without assuming
which one it's looking at, and degrades to plain-text extraction for cells
that don't match either link style (NFR3: tolerate formatting drift instead
of silently dropping rows).
"""
from __future__ import annotations

import hashlib
import re

from watchers.models import Listing

_TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_SEPARATOR_CELL_RE = re.compile(r"^:?-{2,}:?$")
_HTML_LINK_RE = re.compile(r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
_TAG_RE = re.compile(r"<[^>]+>")
_CONTINUATION_MARKERS = {"", "↳", "-", "—"}


def _split_row(line: str) -> list[str]:
    match = _TABLE_ROW_RE.match(line.strip())
    if not match:
        return []
    return [cell.strip() for cell in match.group(1).split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(_SEPARATOR_CELL_RE.match(c) for c in cells if c)


def _strip_markup(text: str) -> str:
    text = _TAG_RE.sub("", text)
    text = _MD_LINK_RE.sub(r"\1", text)
    text = text.replace("**", "").replace("__", "")
    return text.strip()


def _extract_link(cell: str) -> tuple[str, str]:
    """Returns (visible_text, url), or ("", "") if the cell has no link."""
    md = _MD_LINK_RE.search(cell)
    if md:
        return _strip_markup(md.group(1)), md.group(2).strip()

    html = _HTML_LINK_RE.search(cell)
    if html:
        url, inner = html.group(1), html.group(2)
        return _strip_markup(inner), url.strip()

    return "", ""


def _is_continuation_marker(cell: str) -> bool:
    return _strip_markup(cell) in _CONTINUATION_MARKERS


def parse_markdown_table(readme_text: str) -> list[Listing]:
    lines = readme_text.splitlines()
    listings: list[Listing] = []

    in_data_section = False
    last_company = ""
    last_company_url = ""

    i = 0
    while i < len(lines):
        cells = _split_row(lines[i])
        if not cells:
            in_data_section = False
            i += 1
            continue

        next_cells = _split_row(lines[i + 1]) if i + 1 < len(lines) else []
        if next_cells and _is_separator_row(next_cells):
            # This row is a header immediately followed by its separator —
            # skip both and start a fresh data section (repos like speedyapply
            # have multiple header/separator/data blocks in one file).
            in_data_section = True
            last_company = ""
            last_company_url = ""
            i += 2
            continue

        if _is_separator_row(cells) or not in_data_section:
            i += 1
            continue

        if len(cells) < 3:
            i += 1
            continue

        company_cell = cells[0]
        if _is_continuation_marker(company_cell):
            company, company_url = last_company, last_company_url
        else:
            company, company_url = _extract_link(company_cell)
            if not company:
                company = _strip_markup(company_cell)
            last_company, last_company_url = company, company_url

        title_cell = cells[1]
        title, title_url = _extract_link(title_cell)
        if not title:
            title = _strip_markup(title_cell)

        location = _strip_markup(cells[2]) if len(cells) > 2 else ""

        apply_url = ""
        for cell in cells[2:]:
            _, link_url = _extract_link(cell)
            if link_url and ("apply" in cell.lower() or "<img" in cell.lower()):
                apply_url = link_url
                break
        if not apply_url:
            apply_url = title_url or company_url

        date_posted = _strip_markup(cells[-1]) if cells else ""

        i += 1

        if not company or not title:
            continue

        synthetic_id = hashlib.sha256(
            f"{company}|{title}|{apply_url}".lower().encode()
        ).hexdigest()[:16]

        listings.append(
            Listing(
                id=synthetic_id,
                source="",
                company=company,
                title=title,
                location=location,
                url=apply_url,
                date_posted=date_posted,
            )
        )

    return listings
