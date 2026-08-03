from watchers.dedup import cross_repo_dedupe, normalize_key
from watchers.models import Listing


def _listing(company: str, title: str, source: str = "X") -> Listing:
    return Listing(id="1", source=source, company=company, title=title, location="", url="", date_posted="")


def test_normalize_key_ignores_case_and_punctuation():
    assert normalize_key("Stripe", "SWE Intern") == normalize_key("stripe", "swe intern")
    assert normalize_key("Stripe Inc.", "SWE Intern!") == normalize_key("Stripe Inc", "SWE Intern")


def test_cross_repo_dedupe_collapses_same_company_title_across_sources():
    listings = [
        _listing("Stripe", "SWE Intern", source="SimplifyJobs"),
        _listing("stripe", "swe intern", source="vanshb03"),
        _listing("Airbnb", "SWE Intern", source="SimplifyJobs"),
    ]
    deduped = cross_repo_dedupe(listings)

    assert len(deduped) == 2
    assert deduped[0].source == "SimplifyJobs"  # first-seen wins
