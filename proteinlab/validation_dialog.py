from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout,
)

from .icons import make_icon
from .validation import ValidationReport, run_validation_suite, write_validation_report


class ValidationCenterDialog(QDialog):
    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.project_root = project_root
        self.report: ValidationReport | None = None
        self.setWindowTitle("Validation Center — Protein Lab")
        self.resize(1080, 720)
        self.setMinimumSize(820, 560)

        root = QVBoxLayout(self); root.setContentsMargins(14, 14, 14, 14); root.setSpacing(9)
        header = QHBoxLayout()
        icon = QLabel(); icon.setPixmap(make_icon("validate", 40).pixmap(40, 40)); header.addWidget(icon)
        title = QLabel("Validation Center")
        f = title.font(); f.setBold(True); f.setPointSize(f.pointSize()+4); title.setFont(f); header.addWidget(title)
        header.addStretch(1)
        self.run_button = QPushButton(make_icon("validate", 20), "Run full validation")
        self.run_button.clicked.connect(self.run_validation); header.addWidget(self.run_button)
        export = QPushButton(make_icon("export", 20), "Export report…")
        export.clicked.connect(self.export_report); header.addWidget(export)
        root.addLayout(header)

        self.summary = QLabel("Not run yet."); self.summary.setWordWrap(True); root.addWidget(self.summary)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Status", "Group", "Check", "Detail", "Time (ms)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False); self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); root.addWidget(self.table, 1)
        note = QTextEdit(); note.setReadOnly(True); note.setMaximumHeight(115)
        note.setPlainText(
            "Interpretation: PASS means that a specific deterministic benchmark, defensive QA case, dependency check, or structure-integrity check behaved as expected. "
            "It does not prove that a force field is exact, that a predicted structure is correct, or that a research trajectory is converged. Scientific validation remains method- and claim-specific."
        ); root.addWidget(note)
        close = QPushButton("Close"); close.clicked.connect(self.accept); row=QHBoxLayout(); row.addStretch(1); row.addWidget(close); root.addLayout(row)
        self.run_validation()

    def run_validation(self) -> None:
        self.run_button.setEnabled(False); self.summary.setText("Running validation…")
        try:
            self.report = run_validation_suite(self.project_root, include_runtime=True, include_builtins=True)
        except Exception as exc:
            QMessageBox.critical(self, "Validation failed", str(exc)); self.run_button.setEnabled(True); return
        self.table.setRowCount(0)
        for check in self.report.checks:
            row = self.table.rowCount(); self.table.insertRow(row)
            values = [check.status, check.group, check.name, check.detail, f"{check.elapsed_ms:.2f}"]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setTextAlignment(Qt.AlignCenter)
                    if check.status == "PASS": item.setToolTip("This check passed.")
                    elif check.status == "WARN": item.setToolTip("Non-fatal warning; inspect the detail.")
                    else: item.setToolTip("Required check failed; inspect before trusting this installation.")
                self.table.setItem(row, col, item)
        self.summary.setText(
            f"Protein Lab {self.report.protein_lab_version} · {self.report.pass_count} PASS · "
            f"{self.report.warn_count} WARN · {self.report.fail_count} FAIL. "
            + ("No required validation check failed." if self.report.all_required_passed else "One or more required checks FAILED — inspect the table before research use.")
        )
        self.run_button.setEnabled(True)

    def export_report(self) -> None:
        if self.report is None: return
        filename, selected = QFileDialog.getSaveFileName(self, "Export validation report", "ProteinLab_validation_report.txt", "Text (*.txt);;JSON (*.json)")
        if not filename: return
        path = Path(filename)
        if "JSON" in selected and path.suffix.lower() != ".json": path = path.with_suffix(".json")
        try:
            write_validation_report(path, self.report)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
