import json
from pathlib import Path

from watchers.parsers.json_parser import parse_json_listings

FIXTURE = Path(__file__).parent / "fixtures" / "simplify_sample.json"


def test_parses_visible_active_software_only():
    raw = json.loads(FIXTURE.read_text())
    listings = parse_json_listings(raw, category_filter=["Software"])

    # fixture: 3 Software+visible+active (pass), 2 Software+visible+NOT active
    # (excluded), 1 wrong-category+active (excluded), 1 not-visible (excluded)
    assert len(listings) == 3
    companies = {l.company for l in listings}
    assert companies == {"Amazon", "Palantir", "Oracle"}


def test_excludes_inactive_even_if_visible_and_right_category():
    raw = json.loads(FIXTURE.read_text())
    listings = parse_json_listings(raw, category_filter=["Software"])
    companies = {l.company for l in listings}
    assert "Powell" not in companies  # active=False
    assert "Axiom Space" not in companies  # active=False


def test_no_category_filter_skips_category_check():
    # vanshb03's feed has no "category" field at all — an empty filter list
    # must not exclude everything.
    raw = json.loads(FIXTURE.read_text())
    listings = parse_json_listings(raw, category_filter=[])
    companies = {l.company for l in listings}
    assert "Amazon" in companies  # the AI/ML/Data Amazon entry should now pass too


def test_maps_fields_correctly():
    raw = json.loads(FIXTURE.read_text())
    listings = parse_json_listings(raw, category_filter=["Software"])
    listing = listings[0]

    assert listing.id
    assert listing.company
    assert listing.title
    assert listing.url.startswith("http")
    assert listing.location
