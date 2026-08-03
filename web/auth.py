"""Shared-password session gate. This app is reachable over Tailscale (a
private network between the user's own devices), not the public internet —
this is defense-in-depth on top of that, not the sole access control, so a
simple in-memory session store is sufficient for a single-user personal tool.
"""
from __future__ import annotations

import os
import secrets

SESSION_COOKIE_NAME = "tracker_session"

_valid_sessions: set[str] = set()


def get_web_password() -> str:
    password = os.environ.get("TRACKER_WEB_PASSWORD")
    if not password:
        raise RuntimeError(
            "TRACKER_WEB_PASSWORD environment variable is not set. "
            "Set it before starting the server, e.g.: export TRACKER_WEB_PASSWORD='...'"
        )
    return password


def check_password(candidate: str) -> bool:
    return secrets.compare_digest(candidate, get_web_password())


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    _valid_sessions.add(token)
    return token


def is_valid_session(token: str | None) -> bool:
    return token is not None and token in _valid_sessions


def invalidate_session(token: str | None) -> None:
    if token is not None:
        _valid_sessions.discard(token)
