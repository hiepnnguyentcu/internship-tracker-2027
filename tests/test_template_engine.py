import pytest

from template_engine import render


def test_render_substitutes_all_fields():
    result = render("Hi {{recruiter_name}}, interested in {{company}}?", {"recruiter_name": "Jane", "company": "Stripe"})
    assert result == "Hi Jane, interested in Stripe?"


def test_render_raises_on_missing_field():
    with pytest.raises(ValueError):
        render("Hi {{recruiter_name}}", {})


def test_render_raises_on_malformed_placeholder():
    with pytest.raises(ValueError):
        render("Hi {{recruiter_name}", {"recruiter_name": "Jane"})


def test_render_tolerates_extra_context_fields():
    # context can have fields the template doesn't use, that's fine
    result = render("Hi {{recruiter_name}}", {"recruiter_name": "Jane", "unused": "x"})
    assert result == "Hi Jane"


def test_render_does_not_partially_send_on_failure():
    with pytest.raises(ValueError):
        render("Hi {{recruiter_name}}, re: {{missing_field}}", {"recruiter_name": "Jane"})
