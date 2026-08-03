"""Thin wrapper over the Drive API — minimal for Phase 2 sub-chunk B: just
enough to export a resume Google Doc as a PDF for an ATS form's file-upload
field. Read-only (drive.readonly scope) — never writes to Drive. The
copy/edit/re-upload machinery for resume tweaking is separate, later work.
"""
from __future__ import annotations

import re
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from google_auth import get_credentials

_DOC_ID_RE = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")


def extract_doc_id(doc_url_or_id: str) -> str:
    """Accepts either a bare Doc id or a full Google Docs URL."""
    match = _DOC_ID_RE.search(doc_url_or_id)
    if match:
        return match.group(1)
    return doc_url_or_id


class DriveClient:
    def __init__(self):
        self._service = build("drive", "v3", credentials=get_credentials())

    def export_doc_as_pdf(self, doc_url_or_id: str, output_path: Path) -> Path:
        doc_id = extract_doc_id(doc_url_or_id)
        request = self._service.files().export_media(fileId=doc_id, mimeType="application/pdf")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        return output_path
