from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QSplashScreen

from . import __version__


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = PROJECT_ROOT / "assets"
APP_ICON = ASSET_DIR / "ProteinLab.ico"
SPLASH_IMAGE = ASSET_DIR / "ProteinLab_splash.png"


class ProteinLabSplash(QSplashScreen):
    """Small native startup screen shown while the scientific UI is imported and initialized."""

    def __init__(self) -> None:
        if SPLASH_IMAGE.exists():
            pixmap = QPixmap(str(SPLASH_IMAGE))
        else:
            pixmap = QPixmap(920, 520)
            pixmap.fill(QColor("#f7fafc"))
        super().__init__(pixmap, Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.FramelessWindowHint, True)

        self.status_label = QLabel("Starting Protein Lab…", self)
        self.status_label.setGeometry(QRect(74, 454, 620, 24))
        self.status_label.setStyleSheet("color:#42515b;background:transparent;font-size:10pt;")

        self.progress = QProgressBar(self)
        self.progress.setGeometry(QRect(74, 486, 772, 8))
        self.progress.setRange(0, 100)
        self.progress.setValue(4)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(
            "QProgressBar{background:#dbe5eb;border:0;border-radius:4px;}"
            "QProgressBar::chunk{background:#2f709b;border-radius:4px;}"
        )

    def stage(self, percent: int, text: str, app: QApplication) -> None:
        self.progress.setValue(max(0, min(100, int(percent))))
        self.status_label.setText(text)
        app.processEvents()


def configure_application(app: QApplication) -> None:
    app.setOrganizationName("ProteinLab")
    app.setApplicationName("Protein Lab")
    app.setApplicationDisplayName("Protein Lab")
    app.setApplicationVersion(__version__)
    if sys.platform.startswith("win"):
        app.setFont(QFont("Segoe UI", 9))
    if APP_ICON.exists():
        app.setWindowIcon(QIcon(str(APP_ICON)))


def main() -> int:
    app = QApplication(sys.argv)
    configure_application(app)

    no_splash = (
        os.environ.get("PROTEINLAB_NO_SPLASH", "").strip() == "1"
        or os.environ.get("PROTEINLAB_BOOTSTRAPPED", "").strip() == "1"
    )
    splash: ProteinLabSplash | None = None
    if not no_splash:
        splash = ProteinLabSplash()
        splash.show()
        splash.stage(8, "Loading Protein Lab 1.0.3…", app)

    if splash:
        splash.stage(20, "Loading structural-biology modules…", app)

    # Import the main window only after the splash is visible. This keeps VTK/OpenMM/PySide
    # import time behind a real loading screen instead of a blank desktop pause.
    from .app import MainWindow

    if splash:
        splash.stage(58, "Initializing the molecular viewport and protein library…", app)

    window = MainWindow(app)
    if APP_ICON.exists():
        window.setWindowIcon(QIcon(str(APP_ICON)))

    if splash:
        splash.stage(88, "Restoring the research workspace…", app)

    window.show()
    app.processEvents()

    ready_file = os.environ.get("PROTEINLAB_READY_FILE", "").strip()
    if ready_file:
        try:
            Path(ready_file).write_text(f"Protein Lab {__version__} ready\n", encoding="utf-8")
        except Exception:
            pass

    if splash:
        splash.stage(100, "Ready", app)
        splash.finish(window)

    return app.exec()
