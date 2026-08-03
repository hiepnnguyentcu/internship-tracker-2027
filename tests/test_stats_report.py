from stats_report import (
    compute_avg_days_in_stage,
    compute_funnel_counts,
    compute_rates_by_group,
)


def test_compute_rates_by_group_basic():
    applications = [
        {"app_id": "A1", "group": "x"},
        {"app_id": "A2", "group": "x"},
        {"app_id": "A3", "group": "y"},
    ]
    stage_history = {
        "A1": {"Applied", "OA"},
        "A2": {"Applied"},
        "A3": {"Applied", "OA", "Phone Screen"},
    }
    result = compute_rates_by_group(applications, stage_history, lambda app: app["group"])

    assert result["x"]["total"] == 2
    assert result["x"]["response_rate"] == 0.5  # only A1 responded
    assert result["x"]["interview_rate"] == 0.0
    assert result["y"]["total"] == 1
    assert result["y"]["response_rate"] == 1.0
    assert result["y"]["interview_rate"] == 1.0


def test_compute_rates_by_group_handles_zero_denominator():
    # no applications in a group at all -> function just never creates that
    # key, but callers must not divide by zero for empty overall data
    result = compute_rates_by_group([], {}, lambda app: "x")
    assert result == {}


def test_ghosted_does_not_count_as_response():
    applications = [{"app_id": "A1", "group": "x"}]
    stage_history = {"A1": {"Applied", "Ghosted"}}
    result = compute_rates_by_group(applications, stage_history, lambda app: app["group"])
    assert result["x"]["response_rate"] == 0.0


def test_compute_funnel_counts():
    applications = [
        {"app_id": "A1", "current_stage": "OA"},
        {"app_id": "A2", "current_stage": "Applied"},
    ]
    stage_history = {
        "A1": {"Applied", "OA"},
        "A2": {"Applied"},
    }
    funnel = compute_funnel_counts(applications, stage_history)
    assert funnel["Applied"] == 2
    assert funnel["OA"] == 1
    assert funnel["Offer"] == 0


def test_compute_avg_days_in_stage():
    stage_events = [
        {"app_id": "A1", "stage": "Applied", "date": "2026-01-01"},
        {"app_id": "A1", "stage": "OA", "date": "2026-01-08"},
        {"app_id": "A2", "stage": "Applied", "date": "2026-01-01"},
        {"app_id": "A2", "stage": "OA", "date": "2026-01-06"},
    ]
    result = compute_avg_days_in_stage(stage_events)
    assert result["Applied"] == 6.0  # avg of 7 and 5 days
