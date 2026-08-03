"""Thin wrapper over the Gmail API: sending mail and inspecting thread replies."""
from __future__ import annotations

import base64
from email.mime.text import MIMEText

from googleapiclient.discovery import build

from google_auth import get_credentials


class GmailClient:
    def __init__(self):
        self._service = build("gmail", "v1", credentials=get_credentials())

    def send(self, to: str, subject: str, body_html: str) -> tuple[str, str]:
        """Sends an HTML email. Returns (message_id, thread_id)."""
        message = MIMEText(body_html, "html")
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        sent = (
            self._service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )
        return sent["id"], sent["threadId"]

    def get_thread_message_count(self, thread_id: str) -> int:
        thread = (
            self._service.users()
            .threads()
            .get(userId="me", id=thread_id, format="metadata")
            .execute()
        )
        return len(thread.get("messages", []))
