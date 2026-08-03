"""Fetches all configured job-listing repos, finds genuinely new postings,
dedupes across repos, flags target-company matches, and emails a digest.

Usage:
    python scripts/check_listings.py             # real run
    python scripts/check_listings.py --dry-run   # print digest, no writes/send
"""
import argparse
import sys
from datetime import date
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402
import yaml  # noqa: E402

from gmail_client import GmailClient  # noqa: E402
from sheets_client import SheetsClient  # noqa: E402
from watchers.dedup import cross_repo_dedupe, normalize_key  # noqa: E402
from watchers.models import Listing  # noqa: E402
from watchers.parsers.json_parser import parse_json_listings  # noqa: E402
from watchers.parsers.markdown_parser import parse_markdown_table  # noqa: E402
from watchers.target_match import is_target, load_target_companies  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def _fetch_repo_listings(repo: dict) -> list[Listing]:
    response = requests.get(repo["url"], timeout=20)
    response.raise_for_status()

    if repo["type"] == "json":
        listings = parse_json_listings(response.json(), repo.get("category_filter") or [])
    elif repo["type"] == "markdown":
        listings = parse_markdown_table(response.text)
    else:
        raise ValueError(f"Unknown repo type: {repo['type']!r}")

    for listing in listings:
        listing.source = repo["name"]
    return listings


def _group_by_source(listings: list[Listing], repo_order: list[str]) -> dict[str, list[Listing]]:
    groups: dict[str, list[Listing]] = {name: [] for name in repo_order}
    for listing in listings:
        groups.setdefault(listing.source, []).append(listing)
    return {name: items for name, items in groups.items() if items}


def _listing_li_html(listing: Listing) -> str:
    return (
        f"<li><a href=\"{escape(listing.url)}\">{escape(listing.company)} "
        f"&mdash; {escape(listing.title)}</a> "
        f"({escape(listing.location)}, {escape(listing.date_posted)})</li>"
    )


def _build_digest_html(target_matches: list[Listing], rest_by_source: dict[str, list[Listing]]) -> str:
    parts = ["<div>"]
    if target_matches:
        parts.append("<h2>\U0001F3AF Target companies</h2><ul>")
        parts.extend(_listing_li_html(l) for l in target_matches)
        parts.append("</ul>")
    for source, items in rest_by_source.items():
        parts.append(f"<h3>{escape(source)}</h3><ul>")
        parts.extend(_listing_li_html(l) for l in items)
        parts.append("</ul>")
    parts.append("</div>")
    return "".join(parts)


def _mark_emailed(sheets: SheetsClient, keys: list[str]) -> None:
    rows = sheets.read_tab("ListingsSeen")
    key_to_index = {row["listing_key"]: idx for idx, row in enumerate(rows, start=1)}
    updates = [(key_to_index[key], "emailed", "Y") for key in keys if key in key_to_index]
    sheets.batch_update_cells("ListingsSeen", updates)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print the digest, write/send nothing.")
    args = parser.parse_args()

    config = yaml.safe_load(CONFIG_PATH.read_text())
    repos = config["repos"]
    repo_order = [r["name"] for r in repos]

    all_listings: list[Listing] = []
    for repo in repos:
        try:
            listings = _fetch_repo_listings(repo)
            print(f"  {repo['name']}: {len(listings)} listings parsed")
            all_listings.extend(listings)
        except Exception as exc:  # noqa: BLE001 - one bad repo must not kill the run (NFR2)
            print(f"  {repo['name']}: FAILED ({exc!r}) - skipping")

    deduped = cross_repo_dedupe(all_listings)
    print(f"{len(all_listings)} total listings -> {len(deduped)} after cross-repo dedup")

    sheets = SheetsClient()
    seen_keys = {row["listing_key"] for row in sheets.read_tab("ListingsSeen")}

    new_listings = [l for l in deduped if normalize_key(l.company, l.title) not in seen_keys]

    if not new_listings:
        print("No new listings. Nothing to do.")
        return

    target_set = load_target_companies(sheets)
    target_matches = [l for l in new_listings if is_target(l.company, target_set)]
    target_ids = {id(l) for l in target_matches}
    rest = [l for l in new_listings if id(l) not in target_ids]
    rest_by_source = _group_by_source(rest, repo_order)

    digest_html = _build_digest_html(target_matches, rest_by_source)
    subject = f"Internship listings digest — {len(new_listings)} new"
    if target_matches:
        subject += f" ({len(target_matches)} \U0001F3AF target)"

    if args.dry_run:
        print(f"\n--dry-run: would send '{subject}' with {len(new_listings)} listing(s):\n")
        print(digest_html)
        return

    today = date.today().isoformat()
    new_keys = [normalize_key(l.company, l.title) for l in new_listings]
    rows_to_append = [
        {
            "listing_key": key,
            "source_repo": listing.source,
            "company": listing.company,
            "role": listing.title,
            "location": listing.location,
            "url": listing.url,
            "date_first_seen": today,
            "emailed": "N",
        }
        for key, listing in zip(new_keys, new_listings)
    ]
    # One batched write, not one API call per row — the Sheets API's default
    # 60-writes/min/user quota makes a per-row loop fail well before a few
    # hundred rows are written (hit this for real on the first live run).
    sheets.append_rows("ListingsSeen", rows_to_append)

    gmail = GmailClient()
    gmail.send(to=config["digest_email"], subject=subject, body_html=digest_html)

    _mark_emailed(sheets, new_keys)
    print(f"Sent digest with {len(new_listings)} new listing(s), {len(target_matches)} target-company match(es).")


if __name__ == "__main__":
    main()
