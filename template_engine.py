"""Simple {{field}} mail-merge template rendering — no Jinja2, just enough to
fail loudly on an unfilled or malformed placeholder rather than silently
sending a literal "{{recruiter_name}}" to a real person (NFR4)."""
from __future__ import annotations

import re

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def render(template: str, context: dict) -> str:
    def _sub(match: re.Match) -> str:
        key = match.group(1)
        if key not in context:
            raise ValueError(f"Template references a field not in context: {{{{{key}}}}}")
        return str(context[key])

    rendered = _PLACEHOLDER_RE.sub(_sub, template)

    if "{{" in rendered or "}}" in rendered:
        raise ValueError(f"Unfilled or malformed template placeholder(s) remain: {rendered!r}")

    return rendered
