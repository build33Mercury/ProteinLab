from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget,
)

from .calculations import CALCULATIONS, CalculationSpec
from .notebook import ExperimentEntry


class CalculationInspectorDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calculation Inspector")
        self.resize(860, 620)
        root = QVBoxLayout(self)
        intro = QLabel("Every entry below states the equation, interpretation, and assumptions Protein Lab uses. Search by concept or equation name.")
        intro.setWordWrap(True); root.addWidget(intro)
        self.search = QLineEdit(); self.search.setPlaceholderText("Search equations or methods…"); self.search.textChanged.connect(self._refresh); root.addWidget(self.search)
        split = QSplitter(Qt.Horizontal)
        self.list = QListWidget(); self.list.itemSelectionChanged.connect(self._selected); split.addWidget(self.list)
        self.detail = QTextEdit(); self.detail.setReadOnly(True); split.addWidget(self.detail); split.setSizes([300, 540]); root.addWidget(split, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self._refresh()

    def _refresh(self) -> None:
        q = self.search.text().strip().lower(); self.list.clear()
        for spec in CALCULATIONS:
            hay = f"{spec.name} {spec.category} {spec.equation} {spec.description} {spec.assumptions}".lower()
            if q and q not in hay: continue
            item = QListWidgetItem(f"{spec.name}\n{spec.category}"); item.setData(Qt.UserRole, spec); self.list.addItem(item)
        if self.list.count(): self.list.setCurrentRow(0)

    def _selected(self) -> None:
        item = self.list.currentItem()
        if not item: return
        spec = item.data(Qt.UserRole)
        if not isinstance(spec, CalculationSpec): return
        self.detail.setPlainText(
            f"{spec.name}\n{'='*len(spec.name)}\n\nCategory\n--------\n{spec.category}\n\n"
            f"Equation / mathematical form\n----------------------------\n{spec.equation}\n\n"
            f"What Protein Lab calculates\n---------------------------\n{spec.description}\n\n"
            f"Assumptions / limitations\n-------------------------\n{spec.assumptions}"
        )


class ExperimentNotebookDialog(QDialog):
    def __init__(self, entries: list[ExperimentEntry], parent=None) -> None:
        super().__init__(parent)
        self.entries = entries
        self.setWindowTitle("Experiment Notebook")
        self.resize(980, 650)
        root = QVBoxLayout(self)
        intro = QLabel("Persistent provenance record. Operations are stored with UTC timestamp, method, parameters, and outputs.")
        intro.setWordWrap(True); root.addWidget(intro)
        split = QSplitter(Qt.Vertical)
        self.table = QTableWidget(0, 5); self.table.setHorizontalHeaderLabels(["UTC", "Protein", "Action", "Method", "ID"]); self.table.horizontalHeader().setStretchLastSection(True); self.table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.table.verticalHeader().setVisible(False); self.table.itemSelectionChanged.connect(self._selected); split.addWidget(self.table)
        self.detail = QTextEdit(); self.detail.setReadOnly(True); split.addWidget(self.detail); split.setSizes([360, 220]); root.addWidget(split, 1)
        buttons=QDialogButtonBox(QDialogButtonBox.Close); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        for e in reversed(entries):
            row=self.table.rowCount(); self.table.insertRow(row)
            for col,val in enumerate([e.timestamp_utc,e.protein_name,e.action,e.method,e.id]): self.table.setItem(row,col,QTableWidgetItem(str(val)))
            self.table.item(row,0).setData(Qt.UserRole,e)
        if self.table.rowCount(): self.table.selectRow(0)

    def _selected(self) -> None:
        row=self.table.currentRow()
        if row<0: return
        item=self.table.item(row,0); e=item.data(Qt.UserRole) if item else None
        if not isinstance(e,ExperimentEntry): return
        params='\n'.join(f"{k}: {v}" for k,v in e.parameters.items()) or '—'
        results='\n'.join(f"{k}: {v}" for k,v in e.results.items()) or '—'
        self.detail.setPlainText(f"{e.action}\n{'='*len(e.action)}\nProtein: {e.protein_name}\nProtein ID: {e.protein_id}\nUTC: {e.timestamp_utc}\nMethod: {e.method}\n\nParameters\n----------\n{params}\n\nResults\n-------\n{results}\n\nNotes\n-----\n{e.notes or '—'}")


class TextReportDialog(QDialog):
    def __init__(self, title: str, text: str, parent=None) -> None:
        super().__init__(parent); self.setWindowTitle(title); self.resize(820, 650)
        root=QVBoxLayout(self); self.text=QTextEdit(); self.text.setPlainText(text); root.addWidget(self.text,1)
        row=QHBoxLayout(); copy=QPushButton("Copy"); copy.clicked.connect(lambda: self.text.selectAll() or self.text.copy()); export=QPushButton("Export .txt…"); export.clicked.connect(self._export); row.addStretch(1); row.addWidget(copy); row.addWidget(export); root.addLayout(row)
        buttons=QDialogButtonBox(QDialogButtonBox.Close); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _export(self) -> None:
        filename,_=QFileDialog.getSaveFileName(self,"Export text","","Text files (*.txt);;All files (*.*)")
        if filename: Path(filename).write_text(self.text.toPlainText(),encoding="utf-8")


class StudentLearningDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent); self.setWindowTitle("Student Lab Guide"); self.resize(760,560)
        root=QVBoxLayout(self)
        title=QLabel("Guided structural-biology experiments"); f=title.font(); f.setBold(True); f.setPointSize(f.pointSize()+3); title.setFont(f); root.addWidget(title)
        body=QTextEdit(); body.setReadOnly(True); body.setPlainText(
            "1. Secondary structure\nLoad Ubiquitin or Lysozyme and use Ribbon view to identify alpha helices, beta strands, turns, and loops.\n\n"
            "2. Coordinate geometry\nUse Distance, Angle, and Dihedral tools. Then open Calculation Inspector to connect the 3D measurement to the exact equation.\n\n"
            "3. Mutation experiment\nSelect a residue, create a mutant, prepare both structures, minimize, and compare them. Keep prediction/model-dependent conclusions separate from experimental facts.\n\n"
            "4. Molecular dynamics\nPrepare a small protein, run a short MD trajectory, then calculate RMSD and RMSF. Ask what each metric measures—and what it does not.\n\n"
            "5. Folding vs prediction\nCreate a custom amino-acid sequence. Protein Lab first shows the constructed peptide strand, then (when enabled) requests an ESMFold structure prediction. The coordinate replacement is a prediction result, not a literal time-resolved folding movie."
        ); root.addWidget(body,1)
        buttons=QDialogButtonBox(QDialogButtonBox.Close); buttons.rejected.connect(self.reject); root.addWidget(buttons)
