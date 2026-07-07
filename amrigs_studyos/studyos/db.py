from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

APP_NAME = "AMRIGS StudyOS"
SCHEMA_VERSION = 1


def app_home() -> Path:
    override = os.environ.get("AMRIGS_STUDYOS_HOME")
    if override:
        root = Path(override).expanduser().resolve()
    elif os.name == "nt" and os.environ.get("APPDATA"):
        root = Path(os.environ["APPDATA"]) / "AMRIGS StudyOS"
    else:
        root = Path.home() / ".amrigs_studyos"
    root.mkdir(parents=True, exist_ok=True)
    (root / "backups").mkdir(exist_ok=True)
    return root


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or (app_home() / "studyos.sqlite3"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self._create_schema()

    def close(self) -> None:
        self.conn.close()

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> None:
        self.conn.executemany(sql, rows)
        self.conn.commit()

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        return list(self.conn.execute(sql, params).fetchall())

    def scalar(self, sql: str, params: Sequence[Any] = (), default: Any = None) -> Any:
        row = self.conn.execute(sql, params).fetchone()
        if row is None:
            return default
        return row[0]

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            self.conn.execute("BEGIN")
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def get_setting(self, key: str, default: str = "") -> str:
        value = self.scalar("SELECT value FROM settings WHERE key = ?", (key,), None)
        return default if value is None else str(value)

    def set_setting(self, key: str, value: Any) -> None:
        self.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    def integrity_ok(self) -> bool:
        return self.scalar("PRAGMA integrity_check", default="") == "ok"

    def _create_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS areas (
                id INTEGER PRIMARY KEY,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                color TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS blocks (
                id INTEGER PRIMARY KEY,
                area_id INTEGER NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS macro_families (
                id INTEGER PRIMARY KEY,
                block_id INTEGER NOT NULL REFERENCES blocks(id) ON DELETE CASCADE,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                base_priority INTEGER NOT NULL DEFAULT 5 CHECK(base_priority BETWEEN 1 AND 10),
                estimated_minutes INTEGER NOT NULL DEFAULT 60,
                manual_priority INTEGER NOT NULL DEFAULT 0 CHECK(manual_priority BETWEEN -1 AND 1),
                active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS content_items (
                id INTEGER PRIMARY KEY,
                macro_family_id INTEGER NOT NULL REFERENCES macro_families(id) ON DELETE CASCADE,
                source_code TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                original_priority INTEGER NOT NULL DEFAULT 5 CHECK(original_priority BETWEEN 1 AND 10),
                sort_order INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','partial','completed','deferred','dismissed')),
                completed_at TEXT,
                total_minutes INTEGER NOT NULL DEFAULT 0,
                total_questions INTEGER NOT NULL DEFAULT 0,
                total_correct INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS planned_sessions (
                id INTEGER PRIMARY KEY,
                session_date TEXT NOT NULL,
                week_number INTEGER NOT NULL,
                day_name TEXT NOT NULL,
                slot INTEGER NOT NULL DEFAULT 1,
                title TEXT NOT NULL,
                session_type TEXT NOT NULL DEFAULT 'study',
                area_id INTEGER REFERENCES areas(id),
                macro_family_id INTEGER REFERENCES macro_families(id),
                estimated_minutes INTEGER NOT NULL DEFAULT 60,
                planned_questions INTEGER NOT NULL DEFAULT 20,
                status TEXT NOT NULL DEFAULT 'planned' CHECK(status IN ('planned','partial','completed','cancelled','deferred')),
                locked INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                UNIQUE(session_date, slot)
            );

            CREATE TABLE IF NOT EXISTS planned_session_items (
                planned_session_id INTEGER NOT NULL REFERENCES planned_sessions(id) ON DELETE CASCADE,
                content_item_id INTEGER NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
                PRIMARY KEY(planned_session_id, content_item_id)
            );

            CREATE TABLE IF NOT EXISTS study_sessions (
                id INTEGER PRIMARY KEY,
                planned_session_id INTEGER REFERENCES planned_sessions(id) ON DELETE SET NULL,
                session_date TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                session_type TEXT NOT NULL DEFAULT 'study',
                area_id INTEGER REFERENCES areas(id),
                macro_family_id INTEGER REFERENCES macro_families(id),
                estimated_minutes INTEGER NOT NULL DEFAULT 0,
                actual_minutes INTEGER NOT NULL DEFAULT 0,
                questions_done INTEGER NOT NULL DEFAULT 0,
                correct_answers INTEGER NOT NULL DEFAULT 0,
                focus INTEGER CHECK(focus BETWEEN 1 AND 5),
                time_use INTEGER CHECK(time_use BETWEEN 1 AND 5),
                difficulty INTEGER CHECK(difficulty BETWEEN 1 AND 5),
                perceived_result TEXT CHECK(perceived_result IN ('insufficient','partial','adequate','consolidated')),
                restart_need TEXT CHECK(restart_need IN ('no','brief_review','restudy')),
                deviation_reason TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS study_session_items (
                study_session_id INTEGER NOT NULL REFERENCES study_sessions(id) ON DELETE CASCADE,
                content_item_id INTEGER NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
                item_status TEXT NOT NULL CHECK(item_status IN ('pending','partial','completed')),
                minutes INTEGER NOT NULL DEFAULT 0,
                questions INTEGER NOT NULL DEFAULT 0,
                correct INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(study_session_id, content_item_id)
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY,
                content_item_id INTEGER NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
                review_type TEXT NOT NULL CHECK(review_type IN ('D1','D7','D21','extra','final')),
                due_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','completed','skipped')),
                completed_at TEXT,
                study_session_id INTEGER REFERENCES study_sessions(id) ON DELETE SET NULL,
                UNIQUE(content_item_id, review_type, due_date)
            );

            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY,
                content_item_id INTEGER REFERENCES content_items(id) ON DELETE SET NULL,
                study_session_id INTEGER REFERENCES study_sessions(id) ON DELETE SET NULL,
                error_type TEXT NOT NULL DEFAULT 'concept',
                severity INTEGER NOT NULL DEFAULT 2 CHECK(severity BETWEEN 1 AND 3),
                description TEXT NOT NULL,
                correction TEXT NOT NULL DEFAULT '',
                resolved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS change_log (
                id INTEGER PRIMARY KEY,
                changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                action TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_items_macro ON content_items(macro_family_id);
            CREATE INDEX IF NOT EXISTS idx_planned_date ON planned_sessions(session_date);
            CREATE INDEX IF NOT EXISTS idx_study_date ON study_sessions(session_date);
            CREATE INDEX IF NOT EXISTS idx_reviews_due ON reviews(due_date, status);
            CREATE INDEX IF NOT EXISTS idx_errors_resolved ON errors(resolved, severity);
            """
        )
        defaults = {
            "schema_version": SCHEMA_VERSION,
            "app_version": "0.1.0",
            "theme": "dark",
            "accent": "violet",
            "font_scale": "1.0",
            "density": "comfortable",
            "study_start_date": "",
            "exam_date": "",
            "daily_minutes": "180",
            "backup_retention": "14",
            "auto_backup": "1",
            "profile_name": "Felipe",
        }
        for key, value in defaults.items():
            self.conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (key, str(value)))
        self.conn.commit()
