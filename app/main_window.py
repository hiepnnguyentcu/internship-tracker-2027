"""Main window: table of unapplied listings (the live 'apply queue')."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import (  # noqa: E402
    QHeaderView, QMainWindow, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.apply_dialog import ApplyDialog  # noqa: E402
from app.queue_model import load_queue, load_resumes  # noqa: E402
from sheets_client import SheetsClient  # noqa: E402

COLUMNS = ["Company", "Role", "Location", "Source", "First Seen", "JD Match", "Needs Tweak", ""]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Internship Tracker — Apply Queue")
        self.resize(900, 600)

        self.sheets = SheetsClient()
        self.queue = []
        self.resumes = []

        central = QWidget()
        layout = QVBoxLayout(central)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)
        layout.addWidget(refresh_button)

        self.table = QTableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        self.setCentralWidget(central)
        self.refresh()

    def refresh(self) -> None:
        try:
            self.queue = load_queue(self.sheets)
            self.resumes = load_resumes(self.sheets)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error loading queue", str(exc))
            self.queue, self.resumes = [], []

        self.table.setRowCount(len(self.queue))
        for row, item in enumerate(self.queue):
            self.table.setItem(row, 0, QTableWidgetItem(item.company))
            self.table.setItem(row, 1, QTableWidgetItem(item.role))
            self.table.setItem(row, 2, QTableWidgetItem(item.location))
            self.table.setItem(row, 3, QTableWidgetItem(item.source_repo))
            self.table.setItem(row, 4, QTableWidgetItem(item.date_first_seen))
            self.table.setItem(row, 5, QTableWidgetItem("—"))  # JD match: not available yet
            self.table.setItem(row, 6, QTableWidgetItem("—"))  # needs tweak: not available yet

            apply_button = QPushButton("Apply")
            apply_button.clicked.connect(lambda checked=False, r=row: self._open_apply_dialog(r))
            self.table.setCellWidget(row, 7, apply_button)

    def _open_apply_dialog(self, row: int) -> None:
        item = self.queue[row]
        if not self.resumes:
            QMessageBox.warning(
                self, "No resumes registered",
                "Register a resume first: python scripts/log_resume.py ...",
            )
            return
        dialog = ApplyDialog(item, self.resumes, self.sheets, parent=self)
        dialog.exec()
        if dialog.applied:
            self.refresh()
