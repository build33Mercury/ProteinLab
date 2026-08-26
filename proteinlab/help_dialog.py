from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from .help_content import TOPICS, HelpTopic, topic_by_key
from .icons import make_icon


class HelpAidDialog(QDialog):
    """Searchable in-app manual for both research and student workflows."""

    def __init__(self, parent=None, *, topic_key: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Help Aid — Protein Lab")
        self.resize(1000, 720)
        self.setMinimumSize(780, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        icon = QLabel(); icon.setPixmap(make_icon("help", 42).pixmap(42, 42)); icon.setFixedSize(46, 46)
        header.addWidget(icon)
        title_host = QWidget(); titles = QVBoxLayout(title_host); titles.setContentsMargins(0, 0, 0, 0); titles.setSpacing(1)
        title = QLabel("Help Aid")
        f = title.font(); f.setBold(True); f.setPointSize(f.pointSize() + 5); title.setFont(f)
        subtitle = QLabel("Search what a feature does, how to use it, what mathematics it uses, and what claims it does not support.")
        subtitle.setWordWrap(True); subtitle.setObjectName("HelpSubtitle")
        titles.addWidget(title); titles.addWidget(subtitle); header.addWidget(title_host, 1)
        root.addLayout(header)

        search_row = QHBoxLayout()
        self.search = QLineEdit(); self.search.setClearButtonEnabled(True); self.search.setPlaceholderText("Search Help Aid — e.g. fold, RMSD, import, mutation, NPT, project…")
        self.search.textChanged.connect(self._refresh)
        search_row.addWidget(self.search, 1)
        quick = QPushButton(make_icon("learn", 22), "Quick start")
        quick.clicked.connect(lambda: self.show_topic("quick-start")); search_row.addWidget(quick)
        root.addLayout(search_row)

        split = QSplitter(Qt.Horizontal)
        self.list = QListWidget(); self.list.setMinimumWidth(300); self.list.itemSelectionChanged.connect(self._selected)
        split.addWidget(self.list)
        self.detail = QTextEdit(); self.detail.setReadOnly(True); self.detail.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        split.addWidget(self.detail); split.setSizes([330, 650]); root.addWidget(split, 1)

        hint = QLabel("Tip: Help Aid describes the exact current workflow. For formulas, open Calculation Inspector. For implementation health, open Validation Center.")
        hint.setObjectName("HelpHint"); hint.setWordWrap(True); root.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Close); buttons.rejected.connect(self.reject); root.addWidget(buttons)

        self._refresh()
        if topic_key:
            self.show_topic(topic_key)

    def _refresh(self) -> None:
        query = self.search.text().strip().lower()
        self.list.clear()
        grouped: dict[str, list[HelpTopic]] = defaultdict(list)
        for topic in TOPICS:
            hay = f"{topic.title} {topic.category} {topic.summary} {topic.body} {topic.keywords}".lower()
            if query and query not in hay:
                continue
            grouped[topic.category].append(topic)
        for category in sorted(grouped):
            header = QListWidgetItem(category.upper())
            f = header.font(); f.setBold(True); header.setFont(f); header.setFlags(Qt.NoItemFlags)
            self.list.addItem(header)
            for topic in grouped[category]:
                item = QListWidgetItem(make_icon(self._icon_for(topic), 20), f"{topic.title}\n{topic.summary}")
                item.setData(Qt.UserRole, topic.key)
                item.setToolTip(topic.summary)
                self.list.addItem(item)
        for row in range(self.list.count()):
            if self.list.item(row).flags() != Qt.NoItemFlags:
                self.list.setCurrentRow(row); break
        if not self.list.count():
            self.detail.setPlainText("No Help Aid topic matched that search.")

    @staticmethod
    def _icon_for(topic: HelpTopic) -> str:
        category = topic.category.lower()
        if "simulation" in category: return "md"
        if "analysis" in category: return "analysis"
        if "geometry" in category: return "distance"
        if "protein input" in category: return "protein"
        if "research" in category: return "notebook"
        if "quality" in category: return "validate"
        if "integrity" in category: return "equation"
        return "help"

    def _selected(self) -> None:
        item = self.list.currentItem()
        if not item: return
        key = item.data(Qt.UserRole)
        if not key: return
        topic = topic_by_key(str(key))
        if topic:
            self._render(topic)

    def _render(self, topic: HelpTopic) -> None:
        body = topic.body.strip()
        self.detail.setPlainText(
            f"{topic.title}\n{'=' * len(topic.title)}\n\n"
            f"{topic.summary}\n\n"
            f"Category: {topic.category}\n\n"
            f"{body}"
        )

    def show_topic(self, key: str) -> None:
        topic = topic_by_key(key)
        if topic is None: return
        self.search.clear()
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.data(Qt.UserRole) == key:
                self.list.setCurrentRow(row)
                self.list.scrollToItem(item)
                self._render(topic)
                return
        self._render(topic)
