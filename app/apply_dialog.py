"""Apply dialog: pick an identity/resume, optionally open the (stubbed)
tweak dialog, then apply.

Automation (Playwright/ATS form-filling) isn't built in this chunk — "Open &
Apply" opens the real job URL in the browser for you to apply manually, then
logs the application for real via the same `record_application()` the CLI
uses, once you confirm you actually submitted it. This is an honest interim
behavior, not a placeholder pretending to auto-apply.
"""
from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import (  # noqa: E402
    QComboBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout,
)

from app.queue_model import QueueItem  # noqa: E402
from app.tweak_dialog import TweakDialog  # noqa: E402
from scripts.log_application import record_application  # noqa: E402
from sheets_client import SheetsClient  # noqa: E402


class ApplyDialog(QDialog):
    def __init__(self, item: QueueItem, resumes: list[dict], sheets: SheetsClient, parent=None):
        super().__init__(parent)
        self.item = item
        self.sheets = sheets
        self.applied = False

        self.setWindowTitle(f"Apply — {item.company}")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{item.company} — {item.role}</b>"))
        layout.addWidget(QLabel(f"{item.location} · via {item.source_repo}"))

        layout.addWidget(QLabel("Identity / resume:"))
        self.resume_combo = QComboBox()
        for resume in resumes:
            label = f"{resume['resume_id']} — {resume['track']} / {resume['variant']}"
            self.resume_combo.addItem(label, resume["resume_id"])
        layout.addWidget(self.resume_combo)

        note = QLabel(
            "JD-match scoring isn't available yet (needs the Drive integration "
            "to read resume text) — pick manually for now."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(note)

        button_row = QHBoxLayout()
        tweak_button = QPushButton("Adjust Resume…")
        tweak_button.clicked.connect(self._open_tweak_dialog)
        button_row.addWidget(tweak_button)

        apply_button = QPushButton("Open && Apply")
        apply_button.clicked.connect(self._open_and_apply)
        button_row.addWidget(apply_button)
        layout.addLayout(button_row)

    def _open_tweak_dialog(self) -> None:
        TweakDialog(self.item.company, self.item.role, parent=self).exec()

    def _open_and_apply(self) -> None:
        webbrowser.open(self.item.url)
        confirm = QMessageBox.question(
            self,
            "Confirm application",
            f"Opened {self.item.company} — {self.item.role} in your browser.\n\n"
            "Once you've actually submitted the application there, click Yes to log it. "
            "Click No if you didn't finish applying.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        resume_id = self.resume_combo.currentData()
        try:
            result = record_application(
                self.sheets,
                company=self.item.company,
                role=self.item.role,
                resume_id=resume_id,
                stage="Applied",
                job_url=self.item.url,
                source=self.item.source_repo,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Failed to log application", str(exc))
            return

        self.applied = True
        QMessageBox.information(self, "Logged", f"Logged application {result['app_id']}.")
        self.accept()
