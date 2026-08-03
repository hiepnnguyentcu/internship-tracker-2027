"""Shared OAuth2 credential loading for the Sheets, Gmail, and Calendar clients."""
from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

CREDENTIALS_DIR = Path(__file__).resolve().parent / "credentials"
CLIENT_SECRET_PATH = CREDENTIALS_DIR / "client_secret.json"
TOKEN_PATH = CREDENTIALS_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive.readonly",  # Phase 2 sub-chunk B: resume PDF export only, never writes to Drive
]


def get_credentials() -> Credentials:
    """Load stored credentials, refreshing the access token if needed.

    Raises a clear RuntimeError (not a raw stack trace) if setup_auth.py
    hasn't been run yet, or needs to be re-run.
    """
    if not TOKEN_PATH.exists():
        raise RuntimeError(
            f"No stored credentials found at {TOKEN_PATH}. "
            "Run `python scripts/setup_auth.py` first to authorize this app."
        )

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())

    if not creds or not creds.valid:
        raise RuntimeError(
            "Stored credentials are invalid or missing a refresh token. "
            "Run `python scripts/setup_auth.py` again to re-authorize."
        )

    return creds
