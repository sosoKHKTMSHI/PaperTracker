from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from studyos.app import (
    ContentPage, DashboardPage, ErrorsPage, MainWindow, MetricCard, ReviewsPage,
    SchedulePage, SettingsPage, TelemetryPage, TodayPage, QHeaderView, QTableWidget,
)
from studyos.content_seed import seed_catalog
from studyos.db import Database
from studyos.services import (
    area_stats, dashboard_stats, ensure_default_schedule, operational_priority_rows,
)

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
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AMRIGS_STUDYOS_HOME"] = tmp
        db = Database(Path(tmp) / "ui-test.sqlite3")
        seed_catalog(db)
        ensure_default_schedule(db)

        if name == "dashboard-core":
            assert dashboard_stats(db)
            db.close()
            print("UI smoke test OK: dashboard-core")
            return 0

        if name == "dashboard-area":
            assert len(area_stats(db)) == 5
            db.close()
            print("UI smoke test OK: dashboard-area")
            return 0

        if name == "dashboard-priority":
            assert operational_priority_rows(db, 5)
            db.close()
            print("UI smoke test OK: dashboard-priority")
            return 0

        if name == "dashboard-widgets":
            metric = MetricCard("Teste", "1", "ok")
            table = QTableWidget(0, 3)
            table.setHorizontalHeaderLabels(["A", "B", "C"])
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            table.setSelectionBehavior(QTableWidget.SelectRows)
            metric.show(); table.show(); app.processEvents()
            assert metric.isVisible() and table.isVisible()
            metric.close(); table.close(); db.close()
            print("UI smoke test OK: dashboard-widgets")
            return 0

        cls = PAGES[name]
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
