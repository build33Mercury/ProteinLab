from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def _set_common(p: QPalette, dark: bool) -> None:
    if dark:
        window = QColor(32, 32, 34); base = QColor(24, 24, 26); alt = QColor(40, 40, 43)
        text = QColor(238, 238, 238); button = QColor(45, 45, 48); disabled = QColor(135, 135, 140); highlight = QColor(48, 112, 173)
    else:
        window = QColor(246, 247, 249); base = QColor(255, 255, 255); alt = QColor(248, 249, 251)
        text = QColor(28, 32, 36); button = QColor(249, 250, 251); disabled = QColor(132, 139, 145); highlight = QColor(37, 111, 169)
    p.setColor(QPalette.Window, window); p.setColor(QPalette.WindowText, text); p.setColor(QPalette.Base, base)
    p.setColor(QPalette.AlternateBase, alt); p.setColor(QPalette.Text, text); p.setColor(QPalette.Button, button)
    p.setColor(QPalette.ButtonText, text); p.setColor(QPalette.Highlight, highlight); p.setColor(QPalette.HighlightedText, QColor(255,255,255))
    p.setColor(QPalette.Link, highlight); p.setColor(QPalette.ToolTipBase, base); p.setColor(QPalette.ToolTipText, text)
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText): p.setColor(QPalette.Disabled, role, disabled)


_LIGHT_TEXT = "#1c2024"
_LIGHT_MUTED = "#606a73"
_LIGHT_BORDER = "#ccd2d8"
_LIGHT_BASE = "#ffffff"
_LIGHT_PANEL = "#f6f7f9"


def apply_light_theme(app: QApplication) -> None:
    palette = QPalette(); _set_common(palette, False); app.setPalette(palette)
    # Explicit foregrounds are deliberate. Qt/Windows can otherwise retain a dark-theme
    # foreground on child widgets after a live theme switch, which produced white-on-white text.
    app.setStyleSheet(f"""
        QMainWindow, QDialog, QDockWidget {{ color: {_LIGHT_TEXT}; }}
        QLabel, QCheckBox, QRadioButton, QGroupBox, QStatusBar {{ color: {_LIGHT_TEXT}; }}
        QPushButton, QToolButton {{ color: {_LIGHT_TEXT}; background: #fafbfc; border: 1px solid {_LIGHT_BORDER}; border-radius: 5px; padding: 5px 9px; }}
        QPushButton:hover, QToolButton:hover {{ background: #eef4f8; border-color: #9eb5c8; }}
        QPushButton:pressed, QToolButton:pressed {{ background: #e1ebf2; }}
        QPushButton:disabled, QToolButton:disabled {{ color: #8d959d; background: #f3f4f5; border-color: #dfe2e5; }}
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QAbstractSpinBox {{ color: {_LIGHT_TEXT}; background: {_LIGHT_BASE}; border: 1px solid {_LIGHT_BORDER}; border-radius: 4px; padding: 3px 5px; selection-background-color: #2878b6; selection-color: white; }}
        QComboBox QAbstractItemView {{ color: {_LIGHT_TEXT}; background: {_LIGHT_BASE}; selection-background-color: #e3f0fa; selection-color: {_LIGHT_TEXT}; }}
        QMenuBar {{ color: {_LIGHT_TEXT}; background: #f7f8fa; }}
        QMenuBar::item:selected {{ background: #e7edf2; }}
        QMenu {{ color: {_LIGHT_TEXT}; background: {_LIGHT_BASE}; border: 1px solid {_LIGHT_BORDER}; }}
        QMenu::item:selected {{ background: #e3f0fa; color: {_LIGHT_TEXT}; }}
        QTabWidget::pane {{ border: 1px solid {_LIGHT_BORDER}; background: {_LIGHT_BASE}; }}
        QTabBar::tab {{ color: {_LIGHT_TEXT}; background: #eef1f4; border: 1px solid {_LIGHT_BORDER}; padding: 6px 10px; margin-right: 1px; }}
        QTabBar::tab:selected {{ background: {_LIGHT_BASE}; border-bottom-color: {_LIGHT_BASE}; font-weight: 600; }}
        QHeaderView::section {{ color: {_LIGHT_TEXT}; background: #eef1f4; border: 0; border-right: 1px solid #d8dde2; border-bottom: 1px solid #d8dde2; padding: 5px; }}
        QTableWidget, QListWidget, QTreeWidget {{ color: {_LIGHT_TEXT}; background: {_LIGHT_BASE}; alternate-background-color: #f8f9fb; gridline-color: #e1e5e8; }}
        QToolTip {{ background: white; color: {_LIGHT_TEXT}; border: 1px solid #9a9a9a; padding: 3px; }}
        QDockWidget::title {{ color: {_LIGHT_TEXT}; background: #eef1f4; padding: 5px 7px; border-bottom: 1px solid {_LIGHT_BORDER}; }}

        QDialog#ProteinToolboxDialog {{ background: #f7f8fa; color: {_LIGHT_TEXT}; }}
        QDialog#ProteinToolboxDialog QLabel {{ color: {_LIGHT_TEXT}; }}
        QLabel#ToolboxDialogSubtitle {{ color: {_LIGHT_MUTED}; }}
        QPushButton#ToolboxHeroButton {{ color: {_LIGHT_TEXT}; background: white; text-align: left; border: 1px solid #cbd2d8; border-radius: 8px; padding: 8px 12px; font-weight: 600; }}
        QPushButton#ToolboxHeroButton:hover {{ background: #edf5fb; border-color: #7fa7c5; }}
        QListWidget#CelloToolboxList {{ color: {_LIGHT_TEXT}; background: #f3f5f7; border: 1px solid #cfd4da; outline: 0; }}
        QListWidget#CelloToolboxList QLabel {{ color: {_LIGHT_TEXT}; background: transparent; }}
        QListWidget#CelloToolboxList QWidget {{ color: {_LIGHT_TEXT}; background: transparent; }}
        QListWidget#CelloToolboxList::item {{ color: {_LIGHT_TEXT}; background: #ffffff; border: 1px solid #dde2e7; border-radius: 6px; margin: 2px 3px; }}
        QListWidget#CelloToolboxList::item:selected {{ background: #e7f1fb; border: 1px solid #6ca5d8; color: {_LIGHT_TEXT}; }}
        QListWidget#CelloToolboxList::item:disabled {{ background: transparent; border: 0px; margin: 0px 3px; color: #59616a; }}
        QLabel#ToolboxSubtitle {{ color: #59636c; font-size: 8.5pt; }}
        QLabel#ToolboxBadge {{ color: #34414b; background: #edf1f4; border: 1px solid #d1d7dc; border-radius: 4px; padding: 2px 5px; font-size: 7.5pt; font-weight: 600; }}
        QLabel#ToolboxHint {{ color: #5b6269; }}
        QToolButton#ToolboxFilter {{ color: {_LIGHT_TEXT}; padding: 3px 7px; border: 1px solid #cbd1d6; border-radius: 4px; background: #f6f7f8; }}
        QToolButton#ToolboxFilter:checked {{ background: #dfeefa; border-color: #75a7cf; }}
    """)


def apply_dark_theme(app: QApplication) -> None:
    palette = QPalette(); _set_common(palette, True); app.setPalette(palette)
    app.setStyleSheet("""
        QMainWindow, QDialog, QDockWidget, QLabel, QCheckBox, QRadioButton, QGroupBox, QStatusBar { color: #eeeeee; }
        QPushButton, QToolButton { color: #eeeeee; background: #303236; border: 1px solid #555960; border-radius: 5px; padding: 5px 9px; }
        QPushButton:hover, QToolButton:hover { background: #3a3d42; }
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QAbstractSpinBox { color: #eeeeee; background: #202226; border: 1px solid #555960; border-radius: 4px; padding: 3px 5px; }
        QComboBox QAbstractItemView, QMenu { color: #eeeeee; background: #27292d; selection-background-color: #3b5870; }
        QMenuBar { color: #eeeeee; background: #24262a; }
        QMenuBar::item:selected, QMenu::item:selected { background: #3b5870; }
        QTabWidget::pane { border: 1px solid #4b4f54; background: #202226; }
        QTabBar::tab { color: #e8e8e8; background: #303237; border: 1px solid #4b4f54; padding: 6px 10px; }
        QTabBar::tab:selected { background: #202226; }
        QHeaderView::section { color: #eeeeee; background: #303237; border: 0; border-right: 1px solid #4b4f54; border-bottom: 1px solid #4b4f54; padding: 5px; }
        QTableWidget, QListWidget, QTreeWidget { color: #eeeeee; background: #202226; gridline-color: #45484d; }
        QToolTip { background: #2b2b2d; color: #f0f0f0; border: 1px solid #666; padding: 3px; }
        QDockWidget::title { color: #eeeeee; background: #2d2f33; padding: 5px 7px; border-bottom: 1px solid #4b4f54; }
        QDialog#ProteinToolboxDialog { background: #24262a; }
        QDialog#ProteinToolboxDialog QLabel { color: #eeeeee; }
        QLabel#ToolboxDialogSubtitle { color: #b7bcc2; }
        QPushButton#ToolboxHeroButton { color: #eeeeee; background: #2d3034; text-align: left; border: 1px solid #555a60; border-radius: 8px; padding: 8px 12px; font-weight: 600; }
        QPushButton#ToolboxHeroButton:hover { background: #354553; border-color: #7396b0; }
        QListWidget#CelloToolboxList { color: #eeeeee; background: #202226; border: 1px solid #484b50; outline: 0; }
        QListWidget#CelloToolboxList QLabel, QListWidget#CelloToolboxList QWidget { color: #eeeeee; background: transparent; }
        QListWidget#CelloToolboxList::item { color: #eeeeee; background: #2b2d31; border: 1px solid #44474c; border-radius: 6px; margin: 2px 3px; }
        QListWidget#CelloToolboxList::item:selected { background: #334e66; border: 1px solid #6496be; color: white; }
        QListWidget#CelloToolboxList::item:disabled { background: transparent; border: 0px; margin: 0px 3px; color: #adb3ba; }
        QLabel#ToolboxSubtitle { color: #b1b6bc; font-size: 8.5pt; }
        QLabel#ToolboxBadge { color: #e3e5e7; background: #3b3e43; border: 1px solid #53575d; border-radius: 4px; padding: 2px 5px; font-size: 7.5pt; font-weight: 600; }
        QLabel#ToolboxHint { color: #b9bdc2; }
        QToolButton#ToolboxFilter { color: #eeeeee; padding: 3px 7px; border: 1px solid #555960; border-radius: 4px; background: #303237; }
        QToolButton#ToolboxFilter:checked { background: #3b5870; border-color: #729fc3; }
    """)
