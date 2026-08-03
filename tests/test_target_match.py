from watchers.target_match import is_target, load_target_companies


class _FakeSheetsClient:
    def __init__(self, rows):
        self._rows = rows

    def read_tab(self, tab):
        assert tab == "TargetCompanies"
        return self._rows


def test_load_target_companies_normalizes():
    client = _FakeSheetsClient([{"company": "Stripe", "tier": "1"}, {"company": ""}])
    targets = load_target_companies(client)
    assert targets == {"stripe"}


def test_is_target_matches_despite_case_and_whitespace():
    targets = {"stripe"}
    assert is_target("Stripe ", targets)
    assert is_target("STRIPE", targets)
    assert not is_target("Airbnb", targets)
