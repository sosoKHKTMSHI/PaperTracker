from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QApplication
from studyos.app import (
    ContentPage, DashboardPage, ErrorsPage, MainWindow, ReviewsPage,
    SchedulePage, SettingsPage, TelemetryPage, TodayPage,
)
from studyos.content_seed import seed_catalog
from studyos.db import Database
from studyos.services import ensure_default_schedule

PAGES = {
    "dashboard": DashboardPage,
    "today": TodayPage,
    "schedule": SchedulePage,
    "reviews": ReviewsPage,
    "content": ContentPage,
    "errors": ErrorsPage,
    "telemetry": TelemetryPage,
    "settings": SettingsPage,
    "main": MainWindow,
}


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "main"
    cls = PAGES[name]
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AMRIGS_STUDYOS_HOME"] = tmp
        db = Database(Path(tmp) / "ui-test.sqlite3")
        seed_catalog(db)
        ensure_default_schedule(db)
        widget = cls(db)
        widget.show()
        app.processEvents()
        assert widget.isVisible()
        widget.close()
        app.processEvents()
        if name != "main":
            db.close()
    print(f"UI smoke test OK: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
