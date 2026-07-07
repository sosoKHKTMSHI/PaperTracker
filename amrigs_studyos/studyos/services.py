from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from . import __version__
from .db import Database, app_home

DATE_FMT = "%Y-%m-%d"


def iso_today() -> str:
    return date.today().isoformat()


def next_monday(day: date | None = None) -> date:
    day = day or date.today()
    return day + timedelta(days=(7 - day.weekday()) % 7)


def phase_for_week(week: int) -> str:
    if week <= 8:
        return "Cobertura estruturada"
    if week <= 14:
        return "Consolidação adaptativa"
    if week <= 17:
        return "Integração por questões"
    return "Revisão final"


def ensure_default_schedule(db: Database, start: date | None = None, force: bool = False) -> None:
    if db.scalar("SELECT COUNT(*) FROM planned_sessions", default=0) and not force:
        return
    if force:
        db.execute("DELETE FROM planned_session_items")
        db.execute("DELETE FROM planned_sessions")

    start = start or next_monday()
    db.set_setting("study_start_date", start.isoformat())

    areas = {row["code"]: row for row in db.query("SELECT * FROM areas")}
    queues: dict[str, list[sqlite3.Row]] = {}
    for code, area in areas.items():
        queues[code] = db.query(
            """
            SELECT mf.*, b.weight AS block_weight
            FROM macro_families mf
            JOIN blocks b ON b.id = mf.block_id
            WHERE b.area_id = ? AND mf.active = 1
            ORDER BY mf.base_priority DESC, b.weight DESC, mf.sort_order, mf.id
            """,
            (area["id"],),
        )

    indices = {code: 0 for code in queues}
    pattern = {
        0: [(1, "CLI"), (2, "PRE")],
        1: [(1, "PED"), (2, "GO")],
        2: [(1, "CIR"), (2, "PED")],
        3: [(1, "CLI"), (2, "PRE")],
        4: [(1, "CIR"), (2, "GO")],
    }
    day_names = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

    with db.transaction() as con:
        for week in range(1, 21):
            phase = phase_for_week(week)
            for weekday in range(5):
                session_date = start + timedelta(days=(week - 1) * 7 + weekday)
                for slot, area_code in pattern[weekday]:
                    area = areas[area_code]
                    macro = None
                    title = ""
                    session_type = "study"
                    est = 60
                    planned_questions = 20

                    if week <= 14:
                        q = queues[area_code]
                        if q:
                            macro = q[indices[area_code] % len(q)]
                            indices[area_code] += 1
                            title = macro["name"]
                            est = int(macro["estimated_minutes"])
                            planned_questions = 25 if int(macro["base_priority"]) >= 9 else 18
                    elif week <= 17:
                        q = queues[area_code]
                        macro = q[(indices[area_code] + week) % len(q)] if q else None
                        title = f"Questões mistas — {area['name']}"
                        session_type = "questions"
                        est = 75
                        planned_questions = 40
                    else:
                        title = f"Revisão final — {area['name']}"
                        session_type = "final_review"
                        est = 60
                        planned_questions = 30

                    cur = con.execute(
                        """
                        INSERT INTO planned_sessions(
                            session_date, week_number, day_name, slot, title, session_type,
                            area_id, macro_family_id, estimated_minutes, planned_questions, notes
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            session_date.isoformat(), week, day_names[weekday], slot, title,
                            session_type, area["id"], macro["id"] if macro else None,
                            est, planned_questions, phase,
                        ),
                    )
                    planned_id = cur.lastrowid
                    if macro:
                        items = con.execute(
                            "SELECT id FROM content_items WHERE macro_family_id = ? ORDER BY sort_order",
                            (macro["id"],),
                        ).fetchall()
                        con.executemany(
                            "INSERT INTO planned_session_items(planned_session_id, content_item_id) VALUES(?,?)",
                            [(planned_id, item["id"]) for item in items],
                        )

            saturday = start + timedelta(days=(week - 1) * 7 + 5)
            sat_title = "Simulado ou prova antiga" if week % 2 == 0 else "Recuperação e banco de erros"
            sat_type = "simulation" if week % 2 == 0 else "recovery"
            con.execute(
                """
                INSERT INTO planned_sessions(
                    session_date, week_number, day_name, slot, title, session_type,
                    estimated_minutes, planned_questions, notes
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (saturday.isoformat(), week, "Sábado", 1, sat_title, sat_type, 120, 80 if week % 2 == 0 else 20, phase),
            )


def dashboard_stats(db: Database, target_date: str | None = None) -> dict[str, Any]:
    target_date = target_date or iso_today()
    start = date.fromisoformat(target_date) - timedelta(days=date.fromisoformat(target_date).weekday())
    end = start + timedelta(days=6)
    total_items = int(db.scalar("SELECT COUNT(*) FROM content_items", default=0))
    completed_items = int(db.scalar("SELECT COUNT(*) FROM content_items WHERE status='completed'", default=0))
    partial_items = int(db.scalar("SELECT COUNT(*) FROM content_items WHERE status='partial'", default=0))
    sessions_today = int(db.scalar("SELECT COUNT(*) FROM planned_sessions WHERE session_date=?", (target_date,), 0))
    completed_today = int(db.scalar("SELECT COUNT(*) FROM planned_sessions WHERE session_date=? AND status='completed'", (target_date,), 0))
    due_today = int(db.scalar("SELECT COUNT(*) FROM reviews WHERE due_date<=? AND status='pending'", (target_date,), 0))
    week_sessions = int(db.scalar("SELECT COUNT(*) FROM planned_sessions WHERE session_date BETWEEN ? AND ?", (start.isoformat(), end.isoformat()), 0))
    week_done = int(db.scalar("SELECT COUNT(*) FROM planned_sessions WHERE session_date BETWEEN ? AND ? AND status='completed'", (start.isoformat(), end.isoformat()), 0))
    week_minutes = int(db.scalar("SELECT COALESCE(SUM(actual_minutes),0) FROM study_sessions WHERE session_date BETWEEN ? AND ?", (start.isoformat(), end.isoformat()), 0))
    week_q = int(db.scalar("SELECT COALESCE(SUM(questions_done),0) FROM study_sessions WHERE session_date BETWEEN ? AND ?", (start.isoformat(), end.isoformat()), 0))
    week_correct = int(db.scalar("SELECT COALESCE(SUM(correct_answers),0) FROM study_sessions WHERE session_date BETWEEN ? AND ?", (start.isoformat(), end.isoformat()), 0))
    return {
        "total_items": total_items,
        "completed_items": completed_items,
        "partial_items": partial_items,
        "coverage_pct": round(100 * completed_items / total_items, 1) if total_items else 0,
        "sessions_today": sessions_today,
        "completed_today": completed_today,
        "due_today": due_today,
        "week_sessions": week_sessions,
        "week_done": week_done,
        "week_adherence": round(100 * week_done / week_sessions, 1) if week_sessions else 0,
        "week_minutes": week_minutes,
        "week_questions": week_q,
        "week_accuracy": round(100 * week_correct / week_q, 1) if week_q else 0,
    }


def area_stats(db: Database) -> list[sqlite3.Row]:
    return db.query(
        """
        SELECT a.name, a.color,
               COUNT(ci.id) AS total_items,
               SUM(CASE WHEN ci.status='completed' THEN 1 ELSE 0 END) AS completed_items,
               COALESCE(SUM(ci.total_questions),0) AS questions,
               COALESCE(SUM(ci.total_correct),0) AS correct,
               COALESCE(SUM(ci.total_minutes),0) AS minutes
        FROM areas a
        LEFT JOIN blocks b ON b.area_id=a.id
        LEFT JOIN macro_families mf ON mf.block_id=b.id
        LEFT JOIN content_items ci ON ci.macro_family_id=mf.id
        GROUP BY a.id ORDER BY a.sort_order
        """
    )


def planned_for_date(db: Database, target_date: str) -> list[sqlite3.Row]:
    return db.query(
        """
        SELECT ps.*, a.name AS area_name, a.color AS area_color, mf.name AS macro_name
        FROM planned_sessions ps
        LEFT JOIN areas a ON a.id=ps.area_id
        LEFT JOIN macro_families mf ON mf.id=ps.macro_family_id
        WHERE ps.session_date=? ORDER BY ps.slot
        """,
        (target_date,),
    )


def items_for_planned(db: Database, planned_id: int) -> list[sqlite3.Row]:
    return db.query(
        """
        SELECT ci.* FROM content_items ci
        JOIN planned_session_items psi ON psi.content_item_id=ci.id
        WHERE psi.planned_session_id=? ORDER BY ci.sort_order
        """,
        (planned_id,),
    )


def generate_reviews(con: sqlite3.Connection, content_item_id: int, completed_day: date) -> None:
    for review_type, offset in (("D1", 1), ("D7", 7), ("D21", 21)):
        con.execute(
            "INSERT OR IGNORE INTO reviews(content_item_id, review_type, due_date) VALUES(?,?,?)",
            (content_item_id, review_type, (completed_day + timedelta(days=offset)).isoformat()),
        )


def save_study_session(db: Database, payload: dict[str, Any]) -> int:
    session_date = payload.get("session_date") or iso_today()
    item_rows = payload.get("items", [])
    with db.transaction() as con:
        cur = con.execute(
            """
            INSERT INTO study_sessions(
                planned_session_id, session_date, started_at, ended_at, session_type,
                area_id, macro_family_id, estimated_minutes, actual_minutes,
                questions_done, correct_answers, focus, time_use, difficulty,
                perceived_result, restart_need, deviation_reason, notes
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                payload.get("planned_session_id"), session_date, payload.get("started_at"),
                payload.get("ended_at"), payload.get("session_type", "study"),
                payload.get("area_id"), payload.get("macro_family_id"),
                int(payload.get("estimated_minutes") or 0), int(payload.get("actual_minutes") or 0),
                int(payload.get("questions_done") or 0), int(payload.get("correct_answers") or 0),
                payload.get("focus"), payload.get("time_use"), payload.get("difficulty"),
                payload.get("perceived_result"), payload.get("restart_need"),
                payload.get("deviation_reason", ""), payload.get("notes", ""),
            ),
        )
        study_id = int(cur.lastrowid)
        newly_completed: list[int] = []
        for row in item_rows:
            item_id = int(row["content_item_id"])
            status = row.get("status", "pending")
            minutes = int(row.get("minutes") or 0)
            questions = int(row.get("questions") or 0)
            correct = int(row.get("correct") or 0)
            previous = con.execute("SELECT status FROM content_items WHERE id=?", (item_id,)).fetchone()
            con.execute(
                "INSERT INTO study_session_items(study_session_id, content_item_id, item_status, minutes, questions, correct) VALUES(?,?,?,?,?,?)",
                (study_id, item_id, status, minutes, questions, correct),
            )
            completed_at = f"{session_date}T23:59:59" if status == "completed" else None
            con.execute(
                """
                UPDATE content_items SET
                    status = CASE
                        WHEN ?='completed' THEN 'completed'
                        WHEN ?='partial' AND status!='completed' THEN 'partial'
                        ELSE status END,
                    completed_at = COALESCE(completed_at, ?),
                    total_minutes = total_minutes + ?,
                    total_questions = total_questions + ?,
                    total_correct = total_correct + ?
                WHERE id=?
                """,
                (status, status, completed_at, minutes, questions, correct, item_id),
            )
            if status == "completed" and previous and previous["status"] != "completed":
                newly_completed.append(item_id)

        completed_day = date.fromisoformat(session_date)
        for item_id in newly_completed:
            generate_reviews(con, item_id, completed_day)

        planned_id = payload.get("planned_session_id")
        if planned_id:
            planned_items = con.execute(
                """
                SELECT ci.status FROM content_items ci
                JOIN planned_session_items psi ON psi.content_item_id=ci.id
                WHERE psi.planned_session_id=?
                """,
                (planned_id,),
            ).fetchall()
            statuses = [r["status"] for r in planned_items]
            if statuses and all(s == "completed" for s in statuses):
                plan_status = "completed"
            elif any(s in ("partial", "completed") for s in statuses):
                plan_status = "partial"
            else:
                plan_status = "planned"
            con.execute("UPDATE planned_sessions SET status=? WHERE id=?", (plan_status, planned_id))

        con.execute(
            "INSERT INTO change_log(entity_type, entity_id, action, details) VALUES('study_session', ?, 'created', ?)",
            (study_id, json.dumps({"date": session_date, "items": len(item_rows)}, ensure_ascii=False)),
        )
    return study_id


def mark_review_completed(db: Database, review_id: int, session_id: int | None = None) -> None:
    db.execute(
        "UPDATE reviews SET status='completed', completed_at=CURRENT_TIMESTAMP, study_session_id=? WHERE id=?",
        (session_id, review_id),
    )


def operational_priority_rows(db: Database, limit: int = 25) -> list[sqlite3.Row]:
    return db.query(
        """
        SELECT ci.id, ci.title, ci.status, ci.original_priority,
               mf.name AS macro_name, mf.manual_priority, a.name AS area_name,
               ci.total_questions, ci.total_correct,
               (ci.original_priority * 10
                + CASE WHEN ci.status='pending' THEN 18 WHEN ci.status='partial' THEN 24 ELSE 0 END
                + CASE WHEN mf.manual_priority=1 THEN 20 WHEN mf.manual_priority=-1 THEN -20 ELSE 0 END
                + CASE WHEN ci.total_questions>=10 AND (1.0*ci.total_correct/ci.total_questions)<0.60 THEN 28
                       WHEN ci.total_questions>=10 AND (1.0*ci.total_correct/ci.total_questions)<0.75 THEN 15 ELSE 0 END
                + COALESCE((SELECT COUNT(*)*6 FROM reviews r WHERE r.content_item_id=ci.id AND r.status='pending' AND r.due_date<=date('now')),0)
               ) AS score
        FROM content_items ci
        JOIN macro_families mf ON mf.id=ci.macro_family_id
        JOIN blocks b ON b.id=mf.block_id
        JOIN areas a ON a.id=b.area_id
        WHERE ci.status!='completed' OR EXISTS(
            SELECT 1 FROM reviews r WHERE r.content_item_id=ci.id AND r.status='pending' AND r.due_date<=date('now')
        )
        ORDER BY score DESC, ci.original_priority DESC, ci.id
        LIMIT ?
        """,
        (limit,),
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def create_save(db: Database, destination: Path) -> Path:
    destination = destination.with_suffix(".amrigs-save")
    destination.parent.mkdir(parents=True, exist_ok=True)
    db.conn.execute("PRAGMA wal_checkpoint(FULL)")
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / "studyos.sqlite3"
        backup_conn = sqlite3.connect(snapshot)
        db.conn.backup(backup_conn)
        backup_conn.close()
        manifest = {
            "format": "amrigs-studyos-save",
            "format_version": 1,
            "app_version": __version__,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "database_sha256": _sha256(snapshot),
        }
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(snapshot, "studyos.sqlite3")
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return destination


def validate_save(source: Path) -> tuple[bool, str, dict[str, Any] | None]:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(source, "r") as zf:
                if not {"manifest.json", "studyos.sqlite3"}.issubset(set(zf.namelist())):
                    return False, "Arquivo de save incompleto.", None
                zf.extract("manifest.json", tmp)
                zf.extract("studyos.sqlite3", tmp)
            manifest = json.loads((Path(tmp) / "manifest.json").read_text(encoding="utf-8"))
            db_path = Path(tmp) / "studyos.sqlite3"
            if manifest.get("format") != "amrigs-studyos-save":
                return False, "Formato de save incompatível.", manifest
            if _sha256(db_path) != manifest.get("database_sha256"):
                return False, "Falha de integridade: checksum divergente.", manifest
            con = sqlite3.connect(db_path)
            check = con.execute("PRAGMA integrity_check").fetchone()[0]
            con.close()
            if check != "ok":
                return False, "Banco de dados corrompido.", manifest
            return True, "Save válido.", manifest
    except Exception as exc:
        return False, f"Não foi possível validar o save: {exc}", None


def restore_save(db: Database, source: Path) -> Path:
    ok, message, _ = validate_save(source)
    if not ok:
        raise ValueError(message)
    automatic = app_home() / "backups" / f"pre_restore_{datetime.now():%Y%m%d_%H%M%S}.amrigs-save"
    create_save(db, automatic)
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(source, "r") as zf:
            zf.extract("studyos.sqlite3", tmp)
        incoming = Path(tmp) / "studyos.sqlite3"
        pending = app_home() / "restore_pending.sqlite3"
        shutil.copy2(incoming, pending)
    return pending


def apply_pending_restore() -> bool:
    pending = app_home() / "restore_pending.sqlite3"
    target = app_home() / "studyos.sqlite3"
    if not pending.exists():
        return False
    shutil.move(str(pending), str(target))
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(target) + suffix)
        if sidecar.exists():
            sidecar.unlink(missing_ok=True)
    return True


def automatic_backup(db: Database) -> Path | None:
    if db.get_setting("auto_backup", "1") != "1":
        return None
    today = date.today().strftime("%Y%m%d")
    target = app_home() / "backups" / f"auto_{today}.amrigs-save"
    if not target.exists():
        create_save(db, target)
    retention = max(3, int(db.get_setting("backup_retention", "14") or 14))
    backups = sorted((app_home() / "backups").glob("auto_*.amrigs-save"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[retention:]:
        old.unlink(missing_ok=True)
    return target
