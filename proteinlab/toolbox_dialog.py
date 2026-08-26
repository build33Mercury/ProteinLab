from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .icons import make_icon, protein_thumbnail
from .models import ProteinRecord
from .tools import TOOLS, ToolSpec
from .ui_widgets import ToolboxCard


CATEGORY_ORDER = ("Protein", "View", "Inspect", "Measure", "Edit", "Analyze", "Simulation")


class ProteinToolboxDialog(QDialog):
    """Cello-style click-to-open chooser for proteins and protein tools."""

    def __init__(self, proteins: list[ProteinRecord], parent=None) -> None:
        super().__init__(parent)
        self.proteins = list(proteins)
        self.selection: str | None = None
        self.setWindowTitle("Protein Toolbox")
        self.resize(700, 740)
        self.setMinimumSize(600, 600)
        self.setModal(True)
        self.setObjectName("ProteinToolboxDialog")

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        logo = QLabel(); logo.setPixmap(make_icon("toolbox", 42).pixmap(42, 42)); logo.setFixedSize(46, 46)
        header.addWidget(logo)
        title_host = QWidget(); title_layout = QVBoxLayout(title_host); title_layout.setContentsMargins(0, 0, 0, 0); title_layout.setSpacing(1)
        title = QLabel("Protein Toolbox"); f = title.font(); f.setBold(True); f.setPointSize(f.pointSize()+4); title.setFont(f)
        subtitle = QLabel("Load a protein, import your own structure, or choose a tool."); subtitle.setObjectName("ToolboxDialogSubtitle")
        title_layout.addWidget(title); title_layout.addWidget(subtitle)
        header.addWidget(title_host, 1)
        root.addLayout(header)

        # Cello-style primary actions: impossible to miss, but still normal desktop UI.
        actions = QGridLayout(); actions.setHorizontalSpacing(8); actions.setVerticalSpacing(8)
        self.import_button = self._hero_button("import", "Import Your Own Protein", "PDB / PDBx-mmCIF from your computer")
        self.create_button = self._hero_button("create", "Create Protein", "Amino-acid sequence or coding-DNA text")
        self.my_button = self._hero_button("my-protein", "My Proteins", "Imported, created, prepared, minimized, and MD structures")
        self.builtin_button = self._hero_button("builtin", "Built-in Proteins", "Curated teaching and testing structures")
        actions.addWidget(self.import_button, 0, 0); actions.addWidget(self.create_button, 0, 1)
        actions.addWidget(self.my_button, 1, 0); actions.addWidget(self.builtin_button, 1, 1)
        root.addLayout(actions)
        self.import_button.clicked.connect(lambda: self._choose("tool|import"))
        self.create_button.clicked.connect(lambda: self._choose("tool|build-protein"))
        self.my_button.clicked.connect(lambda: self._set_category("My Proteins"))
        self.builtin_button.clicked.connect(lambda: self._set_category("Built-in Proteins"))

        separator = QFrame(); separator.setFrameShape(QFrame.HLine); separator.setFrameShadow(QFrame.Sunken); root.addWidget(separator)

        controls = QHBoxLayout()
        self.search = QLineEdit(); self.search.setClearButtonEnabled(True); self.search.setPlaceholderText("Search proteins or tools…")
        self.search.textChanged.connect(self._refresh)
        controls.addWidget(self.search, 1)
        self.category = QComboBox()
        self.category.addItems([
            "Everything", "Built-in Proteins", "My Proteins", "Protein Actions", "View", "Inspect", "Measure", "Edit", "Simulation", "Analysis"
        ])
        self.category.setMinimumWidth(170); self.category.currentTextChanged.connect(self._refresh)
        controls.addWidget(self.category)
        root.addLayout(controls)

        self.list = QListWidget(); self.list.setObjectName("CelloToolboxList"); self.list.setSpacing(3)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.itemClicked.connect(self._item_clicked); self.list.itemActivated.connect(self._item_clicked)
        root.addWidget(self.list, 1)

        hint = QLabel("Tip: search by protein name, PDB ID, operation, or concept — e.g. “hemoglobin”, “RMSD”, “mutate”, or “energy”.")
        hint.setObjectName("ToolboxHint"); hint.setWordWrap(True); root.addWidget(hint)
        self._refresh()

    def _hero_button(self, icon: str, title: str, subtitle: str) -> QPushButton:
        button = QPushButton(make_icon(icon, 30), f"{title}\n{subtitle}")
        button.setObjectName("ToolboxHeroButton")
        button.setMinimumHeight(58)
        button.setIconSize(QSize(30, 30))
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return button

    def _set_category(self, name: str) -> None:
        self.category.setCurrentText(name)
        self.search.clear()
        self.search.setFocus()

    def _choose(self, payload: str) -> None:
        self.selection = payload
        self.accept()

    def _add_header(self, text: str) -> None:
        item = QListWidgetItem(text.upper())
        f = item.font(); f.setBold(True); item.setFont(f)
        item.setFlags(Qt.NoItemFlags); item.setSizeHint(QSize(0, 28))
        self.list.addItem(item)

    def _add_card(self, payload: str, icon: QIcon, title: str, subtitle: str, badge: str, tooltip: str = "") -> None:
        item = QListWidgetItem(); item.setData(Qt.UserRole, payload); item.setToolTip(tooltip); item.setSizeHint(QSize(0, 76))
        self.list.addItem(item)
        self.list.setItemWidget(item, ToolboxCard(icon, title, subtitle, badge, image_size=54))

    def _protein_badge(self, record: ProteinRecord) -> str:
        return {
            "builtin": "BUILT-IN", "imported": "MY PROTEIN", "generated": "CREATED", "prepared": "PREPARED",
            "minimized": "MINIMIZED", "dynamics": "MD", "mutated": "MUTANT", "conformer": "CONFORMER",
            "predicted": "PREDICTED", "project": "PROJECT",
        }.get(record.origin, record.origin.upper())

    def _record_matches(self, record: ProteinRecord, q: str) -> bool:
        haystack = f"{record.name} {record.pdb_id or ''} {record.description} {' '.join(record.metadata.values())}".lower()
        return not q or q in haystack

    def _tool_matches(self, tool: ToolSpec, q: str) -> bool:
        haystack = f"{tool.name} {tool.category} {tool.description} {tool.keywords}".lower()
        return not q or q in haystack

    def _refresh(self) -> None:
        self.list.clear()
        q = self.search.text().strip().lower()
        category = self.category.currentText()

        show_builtin = category in {"Everything", "Built-in Proteins"}
        show_my = category in {"Everything", "My Proteins"}
        if show_builtin:
            records = [r for r in self.proteins if r.origin == "builtin" and self._record_matches(r, q)]
            if records:
                self._add_header("Built-in proteins")
                for r in records:
                    subtitle = f"PDB {r.pdb_id} · {r.description}" if r.pdb_id else r.description
                    self._add_card(f"protein|{r.id}", protein_thumbnail(r.file_path, 54), r.name, subtitle, self._protein_badge(r), r.description)
        if show_my:
            records = [r for r in self.proteins if r.origin != "builtin" and self._record_matches(r, q)]
            if records:
                self._add_header("My Proteins")
                for r in records:
                    subtitle = r.description or r.metadata.get("source_structure", "Saved protein structure")
                    self._add_card(f"protein|{r.id}", protein_thumbnail(r.file_path, 54), r.name, subtitle, self._protein_badge(r), r.description)

        category_map = {
            "Protein Actions": {"Protein"}, "View": {"View"}, "Inspect": {"Inspect"}, "Measure": {"Measure"},
            "Edit": {"Edit"}, "Simulation": {"Simulation"}, "Analysis": {"Analyze", "Measure"},
        }
        wanted = category_map.get(category)
        if category == "Everything" or wanted is not None:
            grouped: dict[str, list[ToolSpec]] = defaultdict(list)
            for tool in TOOLS:
                if wanted is not None and tool.category not in wanted:
                    continue
                if self._tool_matches(tool, q):
                    grouped[tool.category].append(tool)
            for group in CATEGORY_ORDER:
                tools = grouped.get(group, [])
                if not tools:
                    continue
                self._add_header(group)
                for tool in tools:
                    badge = group.upper() if tool.available else f"PHASE {tool.phase}"
                    subtitle = tool.description if tool.available else f"Unavailable · {tool.description}"
                    self._add_card(f"tool|{tool.key}", make_icon(tool.icon, 54), tool.name, subtitle, badge, tool.description)

        if self.list.count() == 0:
            item = QListWidgetItem("No matches — try a different search or category.")
            item.setFlags(Qt.NoItemFlags); item.setSizeHint(QSize(0, 44)); self.list.addItem(item)

    def _item_clicked(self, item: QListWidgetItem) -> None:
        payload = item.data(Qt.UserRole)
        if payload:
            self._choose(str(payload))
