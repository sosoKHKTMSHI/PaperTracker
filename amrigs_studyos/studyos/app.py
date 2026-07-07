from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from PySide6.QtCore import QDate, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
)

from . import __version__
from .content_seed import seed_catalog
from .db import Database, app_home
from .services import (
    apply_pending_restore, area_stats, automatic_backup, create_save,
    dashboard_stats, ensure_default_schedule, iso_today, items_for_planned,
    mark_review_completed, operational_priority_rows, phase_for_week,
    planned_for_date, restore_save, save_study_session, validate_save,
)
from .theme import ACCENTS, stylesheet


RESULT_LABELS = {
    "insufficient": "Insuficiente",
    "partial": "Parcial",
    "adequate": "Adequado",
    "consolidated": "Consolidado",
}
RESTART_LABELS = {"no": "Não", "brief_review": "Revisão breve", "restudy": "Novo estudo"}
DEVIATION_REASONS = [
    "Sem desvio relevante",
    "Conteúdo mais extenso que o estimado",
    "Dificuldade conceitual",
    "Correção aprofundada de questões",
    "Necessidade de busca complementar",
    "Material não estava preparado",
    "Interrupções externas",
    "Distração ou baixa concentração",
    "Atividade adicional não prevista",
    "Estimativa excessiva",
]


def title_label(text: str, subtitle: str = "") -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 8)
    title = QLabel(text)
    title.setObjectName("pageTitle")
    lay.addWidget(title)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        lay.addWidget(sub)
    return box


def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 14, 16, 14)
    return frame, lay


def readonly_item(value: Any, align: Qt.AlignmentFlag = Qt.AlignCenter) -> QTableWidgetItem:
    item = QTableWidgetItem("" if value is None else str(value))
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    item.setTextAlignment(align)
    return item


class MetricCard(QFrame):
    def __init__(self, label: str, value: str = "—", hint: str = "") -> None:
        super().__init__()
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 13, 16, 13)
        self.label = QLabel(label)
        self.label.setObjectName("muted")
        self.value = QLabel(value)
        font = self.value.font()
        font.setPointSize(22)
        font.setBold(True)
        self.value.setFont(font)
        self.hint = QLabel(hint)
        self.hint.setObjectName("muted")
        lay.addWidget(self.label)
        lay.addWidget(self.value)
        lay.addWidget(self.hint)

    def set_value(self, value: str, hint: str = "") -> None:
        self.value.setText(value)
        self.hint.setText(hint)


class BasePage(QWidget):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db

    def refresh(self) -> None:
        pass


class DashboardPage(BasePage):
    def __init__(self, db: Database) -> None:
        super().__init__(db)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 24)
        outer.addWidget(title_label("Dashboard", "Acompanhamento de adesão, cobertura, desempenho e tempo."))

        grid = QGridLayout()
        self.coverage = MetricCard("Cobertura total")
        self.adherence = MetricCard("Adesão semanal")
        self.questions = MetricCard("Questões na semana")
        self.accuracy = MetricCard("Aproveitamento semanal")
        self.time = MetricCard("Tempo na semana")
        self.reviews = MetricCard("Revisões pendentes")
        for idx, widget in enumerate([self.coverage, self.adherence, self.questions, self.accuracy, self.time, self.reviews]):
            grid.addWidget(widget, idx // 3, idx % 3)
        outer.addLayout(grid)

        body = QHBoxLayout()
        area_frame, area_lay = card()
        area_title = QLabel("Desempenho por área")
        area_title.setObjectName("sectionTitle")
        area_lay.addWidget(area_title)
        self.area_table = QTableWidget(0, 5)
        self.area_table.setHorizontalHeaderLabels(["Área", "Cobertura", "Questões", "Acertos", "Tempo"])
        self.area_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 5):
            self.area_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.area_table.setAlternatingRowColors(True)
        self.area_table.setSelectionBehavior(QTableWidget.SelectRows)
        area_lay.addWidget(self.area_table)
        body.addWidget(area_frame, 3)

        priority_frame, priority_lay = card()
        p_title = QLabel("Prioridades operacionais")
        p_title.setObjectName("sectionTitle")
        priority_lay.addWidget(p_title)
        self.priority_table = QTableWidget(0, 3)
        self.priority_table.setHorizontalHeaderLabels(["Conteúdo", "Área", "Score"])
        self.priority_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.priority_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.priority_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.priority_table.setAlternatingRowColors(True)
        priority_lay.addWidget(self.priority_table)
        body.addWidget(priority_frame, 2)
        outer.addLayout(body, 1)
        self.refresh()

    def refresh(self) -> None:
        s = dashboard_stats(self.db)
        self.coverage.set_value(f"{s['coverage_pct']:.1f}%", f"{s['completed_items']} de {s['total_items']} itens")
        self.adherence.set_value(f"{s['week_adherence']:.1f}%", f"{s['week_done']} de {s['week_sessions']} sessões")
        self.questions.set_value(str(s["week_questions"]), "questões registradas")
        self.accuracy.set_value(f"{s['week_accuracy']:.1f}%", "acertos em questões")
        self.time.set_value(f"{s['week_minutes'] // 60}h {s['week_minutes'] % 60:02d}", "tempo real registrado")
        self.reviews.set_value(str(s["due_today"]), "vencidas ou para hoje")

        rows = area_stats(self.db)
        self.area_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            total = int(row["total_items"] or 0)
            completed = int(row["completed_items"] or 0)
            questions = int(row["questions"] or 0)
            correct = int(row["correct"] or 0)
            pct = 100 * completed / total if total else 0
            acc = 100 * correct / questions if questions else 0
            name = readonly_item(row["name"], Qt.AlignLeft | Qt.AlignVCenter)
            name.setForeground(QColor(row["color"]))
            self.area_table.setItem(r, 0, name)
            self.area_table.setItem(r, 1, readonly_item(f"{pct:.1f}%"))
            self.area_table.setItem(r, 2, readonly_item(questions))
            self.area_table.setItem(r, 3, readonly_item(f"{acc:.1f}%" if questions else "—"))
            mins = int(row["minutes"] or 0)
            self.area_table.setItem(r, 4, readonly_item(f"{mins // 60}h {mins % 60:02d}"))

        priorities = operational_priority_rows(self.db, 16)
        self.priority_table.setRowCount(len(priorities))
        for r, row in enumerate(priorities):
            self.priority_table.setItem(r, 0, readonly_item(row["title"], Qt.AlignLeft | Qt.AlignVCenter))
            self.priority_table.setItem(r, 1, readonly_item(row["area_name"]))
            self.priority_table.setItem(r, 2, readonly_item(int(row["score"])))


class SessionDialog(QDialog):
    saved = Signal()

    def __init__(self, db: Database, planned: dict[str, Any] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.planned = planned
        self.elapsed_seconds = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.setWindowTitle("Registrar sessão de estudo")
        self.resize(900, 720)

        outer = QVBoxLayout(self)
        top = QHBoxLayout()
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.type_combo = QComboBox()
        self.type_combo.addItem("Estudo", "study")
        self.type_combo.addItem("Questões", "questions")
        self.type_combo.addItem("Revisão", "review")
        self.type_combo.addItem("Simulado", "simulation")
        self.area_combo = QComboBox()
        self.macro_combo = QComboBox()
        top.addWidget(QLabel("Data"))
        top.addWidget(self.date_edit)
        top.addWidget(QLabel("Tipo"))
        top.addWidget(self.type_combo)
        top.addWidget(QLabel("Área"))
        top.addWidget(self.area_combo, 1)
        top.addWidget(QLabel("Macrofamília"))
        top.addWidget(self.macro_combo, 2)
        outer.addLayout(top)

        self.area_rows = self.db.query("SELECT * FROM areas ORDER BY sort_order")
        for row in self.area_rows:
            self.area_combo.addItem(row["name"], row["id"])
        self.area_combo.currentIndexChanged.connect(self._load_macros)
        self.macro_combo.currentIndexChanged.connect(self._load_items)

        timer_row = QHBoxLayout()
        self.timer_label = QLabel("00:00:00")
        tf = self.timer_label.font(); tf.setPointSize(22); tf.setBold(True); self.timer_label.setFont(tf)
        self.timer_button = QPushButton("Iniciar cronômetro")
        self.timer_button.setObjectName("primary")
        self.timer_button.clicked.connect(self._toggle_timer)
        self.reset_button = QPushButton("Zerar")
        self.reset_button.clicked.connect(self._reset_timer)
        self.estimated = QSpinBox(); self.estimated.setRange(0, 600); self.estimated.setSuffix(" min")
        self.actual = QSpinBox(); self.actual.setRange(0, 600); self.actual.setSuffix(" min")
        timer_row.addWidget(self.timer_label)
        timer_row.addWidget(self.timer_button)
        timer_row.addWidget(self.reset_button)
        timer_row.addStretch()
        timer_row.addWidget(QLabel("Estimado")); timer_row.addWidget(self.estimated)
        timer_row.addWidget(QLabel("Real")); timer_row.addWidget(self.actual)
        outer.addLayout(timer_row)

        self.items = QTableWidget(0, 4)
        self.items.setHorizontalHeaderLabels(["Conteúdo", "IP", "Situação", "Tempo"])
        self.items.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 4): self.items.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.items.setAlternatingRowColors(True)
        outer.addWidget(self.items, 2)

        metrics = QGridLayout()
        self.questions = QSpinBox(); self.questions.setRange(0, 1000)
        self.correct = QSpinBox(); self.correct.setRange(0, 1000)
        self.focus = QSpinBox(); self.focus.setRange(1, 5); self.focus.setValue(4)
        self.time_use = QSpinBox(); self.time_use.setRange(1, 5); self.time_use.setValue(4)
        self.difficulty = QSpinBox(); self.difficulty.setRange(1, 5); self.difficulty.setValue(3)
        self.result = QComboBox()
        for key, label in RESULT_LABELS.items(): self.result.addItem(label, key)
        self.result.setCurrentIndex(2)
        self.restart = QComboBox()
        for key, label in RESTART_LABELS.items(): self.restart.addItem(label, key)
        self.deviation = QComboBox(); self.deviation.addItems(DEVIATION_REASONS)
        labels_widgets = [
            ("Questões", self.questions), ("Acertos", self.correct), ("Foco (1–5)", self.focus),
            ("Uso do tempo (1–5)", self.time_use), ("Dificuldade (1–5)", self.difficulty),
            ("Resultado", self.result), ("Retomada", self.restart), ("Motivo do desvio", self.deviation),
        ]
        for i, (label, widget) in enumerate(labels_widgets):
            metrics.addWidget(QLabel(label), i // 4 * 2, i % 4)
            metrics.addWidget(widget, i // 4 * 2 + 1, i % 4)
        outer.addLayout(metrics)

        self.notes = QTextEdit(); self.notes.setPlaceholderText("Observações, materiais procurados, dificuldades e decisões para a próxima sessão...")
        self.notes.setMaximumHeight(90)
        outer.addWidget(self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._load_macros()
        if planned:
            self._apply_planned(planned)

    def _load_macros(self) -> None:
        area_id = self.area_combo.currentData()
        self.macro_combo.blockSignals(True)
        self.macro_combo.clear()
        if area_id:
            rows = self.db.query(
                "SELECT mf.* FROM macro_families mf JOIN blocks b ON b.id=mf.block_id WHERE b.area_id=? AND mf.active=1 ORDER BY mf.base_priority DESC, mf.sort_order",
                (area_id,),
            )
            for row in rows:
                self.macro_combo.addItem(row["name"], row["id"])
        self.macro_combo.blockSignals(False)
        self._load_items()

    def _load_items(self) -> None:
        macro_id = self.macro_combo.currentData()
        rows = self.db.query("SELECT * FROM content_items WHERE macro_family_id=? ORDER BY sort_order", (macro_id,)) if macro_id else []
        self._set_items(rows)
        if macro_id:
            est = self.db.scalar("SELECT estimated_minutes FROM macro_families WHERE id=?", (macro_id,), 60)
            self.estimated.setValue(int(est or 60))

    def _set_items(self, rows: list[Any]) -> None:
        self.items.setRowCount(len(rows))
        for r, row in enumerate(rows):
            title = readonly_item(row["title"], Qt.AlignLeft | Qt.AlignVCenter)
            title.setData(Qt.UserRole, row["id"])
            self.items.setItem(r, 0, title)
            self.items.setItem(r, 1, readonly_item(row["original_priority"]))
            combo = QComboBox()
            combo.addItem("Pendente", "pending")
            combo.addItem("Parcial", "partial")
            combo.addItem("Concluído", "completed")
            if row["status"] == "completed": combo.setCurrentIndex(2)
            elif row["status"] == "partial": combo.setCurrentIndex(1)
            self.items.setCellWidget(r, 2, combo)
            minutes = QSpinBox(); minutes.setRange(0, 600); minutes.setSuffix(" min")
            self.items.setCellWidget(r, 3, minutes)

    def _apply_planned(self, planned: dict[str, Any]) -> None:
        self.date_edit.setDate(QDate.fromString(planned["session_date"], "yyyy-MM-dd"))
        idx = self.type_combo.findData(planned.get("session_type", "study")); self.type_combo.setCurrentIndex(max(0, idx))
        if planned.get("area_id"):
            idx = self.area_combo.findData(planned["area_id"]); self.area_combo.setCurrentIndex(max(0, idx))
        if planned.get("macro_family_id"):
            idx = self.macro_combo.findData(planned["macro_family_id"]); self.macro_combo.setCurrentIndex(max(0, idx))
        self.estimated.setValue(int(planned.get("estimated_minutes") or 60))
        rows = items_for_planned(self.db, int(planned["id"]))
        if rows: self._set_items(rows)

    def _toggle_timer(self) -> None:
        if self.timer.isActive():
            self.timer.stop(); self.timer_button.setText("Continuar")
        else:
            self.timer.start(1000); self.timer_button.setText("Pausar")

    def _tick(self) -> None:
        self.elapsed_seconds += 1
        h, rem = divmod(self.elapsed_seconds, 3600); m, s = divmod(rem, 60)
        self.timer_label.setText(f"{h:02d}:{m:02d}:{s:02d}")
        self.actual.setValue(max(self.actual.value(), round(self.elapsed_seconds / 60)))

    def _reset_timer(self) -> None:
        self.timer.stop(); self.elapsed_seconds = 0; self.timer_label.setText("00:00:00"); self.actual.setValue(0); self.timer_button.setText("Iniciar cronômetro")

    def _save(self) -> None:
        if self.correct.value() > self.questions.value():
            QMessageBox.warning(self, "Dados inválidos", "O número de acertos não pode exceder o número de questões.")
            return
        item_payload = []
        active_rows = []
        for r in range(self.items.rowCount()):
            item_id = self.items.item(r, 0).data(Qt.UserRole)
            status = self.items.cellWidget(r, 2).currentData()
            mins = self.items.cellWidget(r, 3).value()
            if status != "pending": active_rows.append(r)
            item_payload.append({"content_item_id": item_id, "status": status, "minutes": mins, "questions": 0, "correct": 0})
        if active_rows and all(item_payload[r]["minutes"] == 0 for r in active_rows):
            share = max(1, self.actual.value() // len(active_rows))
            for r in active_rows: item_payload[r]["minutes"] = share
        if active_rows:
            q_share = self.questions.value() // len(active_rows)
            c_share = self.correct.value() // len(active_rows)
            for r in active_rows:
                item_payload[r]["questions"] = q_share
                item_payload[r]["correct"] = min(c_share, q_share)
        payload = {
            "planned_session_id": self.planned.get("id") if self.planned else None,
            "session_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "session_type": self.type_combo.currentData(),
            "area_id": self.area_combo.currentData(),
            "macro_family_id": self.macro_combo.currentData(),
            "estimated_minutes": self.estimated.value(), "actual_minutes": self.actual.value(),
            "questions_done": self.questions.value(), "correct_answers": self.correct.value(),
            "focus": self.focus.value(), "time_use": self.time_use.value(), "difficulty": self.difficulty.value(),
            "perceived_result": self.result.currentData(), "restart_need": self.restart.currentData(),
            "deviation_reason": self.deviation.currentText(), "notes": self.notes.toPlainText().strip(),
            "started_at": None, "ended_at": datetime.now().isoformat(timespec="seconds"), "items": item_payload,
        }
        save_study_session(self.db, payload)
        self.saved.emit(); self.accept()


class TodayPage(BasePage):
    changed = Signal()

    def __init__(self, db: Database) -> None:
        super().__init__(db)
        outer = QVBoxLayout(self); outer.setContentsMargins(24, 20, 24, 24)
        header = QHBoxLayout()
        header.addWidget(title_label("Hoje", "Plano operacional, revisões e sessões livres."), 1)
        self.date_edit = QDateEdit(QDate.currentDate()); self.date_edit.setCalendarPopup(True)
        self.date_edit.dateChanged.connect(self.refresh)
        new_btn = QPushButton("+ Sessão livre"); new_btn.setObjectName("primary"); new_btn.clicked.connect(self._new_free)
        header.addWidget(self.date_edit); header.addWidget(new_btn)
        outer.addLayout(header)

        self.summary = QLabel(); self.summary.setObjectName("muted"); outer.addWidget(self.summary)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Bloco", "Área", "Sessão", "Tipo", "Estimado", "Status", "Ação"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for c in [0,1,3,4,5,6]: self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True); self.table.setSelectionBehavior(QTableWidget.SelectRows)
        outer.addWidget(self.table, 1)

        reviews_frame, reviews_lay = card(); t = QLabel("Revisões vencidas ou para a data"); t.setObjectName("sectionTitle"); reviews_lay.addWidget(t)
        self.review_table = QTableWidget(0, 5)
        self.review_table.setHorizontalHeaderLabels(["Prazo", "Tipo", "Conteúdo", "Área", "Ação"])
        self.review_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for c in [0,1,3,4]: self.review_table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        reviews_lay.addWidget(self.review_table)
        outer.addWidget(reviews_frame, 1)
        self.refresh()

    def refresh(self, *args: Any) -> None:
        target = self.date_edit.date().toString("yyyy-MM-dd")
        rows = planned_for_date(self.db, target)
        total_est = sum(int(r["estimated_minutes"] or 0) for r in rows)
        self.summary.setText(f"{len(rows)} tarefas · {total_est} minutos planejados · alterações ficam registradas no histórico")
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.table.setItem(r, 0, readonly_item(row["slot"]))
            self.table.setItem(r, 1, readonly_item(row["area_name"] or "Flexível"))
            self.table.setItem(r, 2, readonly_item(row["title"], Qt.AlignLeft | Qt.AlignVCenter))
            self.table.setItem(r, 3, readonly_item(row["session_type"]))
            self.table.setItem(r, 4, readonly_item(f"{row['estimated_minutes']} min"))
            self.table.setItem(r, 5, readonly_item(row["status"]))
            btn = QPushButton("Abrir")
            btn.clicked.connect(lambda _=False, data=dict(row): self._open_planned(data))
            self.table.setCellWidget(r, 6, btn)

        reviews = self.db.query(
            """
            SELECT r.*, ci.title, a.name AS area_name FROM reviews r
            JOIN content_items ci ON ci.id=r.content_item_id
            JOIN macro_families mf ON mf.id=ci.macro_family_id
            JOIN blocks b ON b.id=mf.block_id JOIN areas a ON a.id=b.area_id
            WHERE r.status='pending' AND r.due_date<=? ORDER BY r.due_date, ci.original_priority DESC
            """, (target,)
        )
        self.review_table.setRowCount(len(reviews))
        for r, row in enumerate(reviews):
            self.review_table.setItem(r, 0, readonly_item(row["due_date"]))
            self.review_table.setItem(r, 1, readonly_item(row["review_type"]))
            self.review_table.setItem(r, 2, readonly_item(row["title"], Qt.AlignLeft | Qt.AlignVCenter))
            self.review_table.setItem(r, 3, readonly_item(row["area_name"]))
            btn = QPushButton("Concluir")
            btn.clicked.connect(lambda _=False, review_id=row["id"]: self._complete_review(review_id))
            self.review_table.setCellWidget(r, 4, btn)

    def _open_planned(self, row: dict[str, Any]) -> None:
        dlg = SessionDialog(self.db, row, self); dlg.saved.connect(self._after_save); dlg.exec()

    def _new_free(self) -> None:
        dlg = SessionDialog(self.db, None, self); dlg.saved.connect(self._after_save); dlg.exec()

    def _complete_review(self, review_id: int) -> None:
        mark_review_completed(self.db, review_id); self._after_save()

    def _after_save(self) -> None:
        self.refresh(); self.changed.emit()


class SchedulePage(BasePage):
    changed = Signal()

    def __init__(self, db: Database) -> None:
        super().__init__(db)
        outer = QVBoxLayout(self); outer.setContentsMargins(24, 20, 24, 24)
        header = QHBoxLayout(); header.addWidget(title_label("Cronograma", "Visão editável das 20 semanas e das quatro fases."), 1)
        self.week = QSpinBox(); self.week.setRange(1, 20); self.week.valueChanged.connect(self.refresh)
        regen = QPushButton("Regenerar cronograma"); regen.clicked.connect(self._regenerate)
        header.addWidget(QLabel("Semana")); header.addWidget(self.week); header.addWidget(regen)
        outer.addLayout(header)
        self.phase = QLabel(); self.phase.setObjectName("sectionTitle"); outer.addWidget(self.phase)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Data", "Dia", "Bloco", "Área", "Sessão", "Tipo", "Tempo", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        for c in [0,1,2,3,5,6,7]: self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True); outer.addWidget(self.table, 1)
        self.refresh()

    def refresh(self, *args: Any) -> None:
        week = self.week.value(); self.phase.setText(f"Semana {week} — {phase_for_week(week)}")
        rows = self.db.query(
            """SELECT ps.*, a.name AS area_name FROM planned_sessions ps
            LEFT JOIN areas a ON a.id=ps.area_id WHERE week_number=? ORDER BY session_date, slot""", (week,)
        )
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals = [row["session_date"], row["day_name"], row["slot"], row["area_name"] or "Flexível", row["title"], row["session_type"], f"{row['estimated_minutes']} min", row["status"]]
            for c, val in enumerate(vals): self.table.setItem(r, c, readonly_item(val, Qt.AlignLeft | Qt.AlignVCenter if c == 4 else Qt.AlignCenter))

    def _regenerate(self) -> None:
        if QMessageBox.question(self, "Regenerar", "Isso substituirá apenas o planejamento. Sessões já registradas permanecerão preservadas. Continuar?") != QMessageBox.Yes:
            return
        start_txt = self.db.get_setting("study_start_date", "")
        start = date.fromisoformat(start_txt) if start_txt else None
        ensure_default_schedule(self.db, start, force=True)
        self.refresh(); self.changed.emit()


class ReviewsPage(BasePage):
    def __init__(self, db: Database) -> None:
        super().__init__(db)
        outer = QVBoxLayout(self); outer.setContentsMargins(24, 20, 24, 24)
        outer.addWidget(title_label("Revisões", "D+1, D+7, D+21, extraordinárias e revisão final."))
        filters = QHBoxLayout()
        self.status = QComboBox(); self.status.addItem("Pendentes", "pending"); self.status.addItem("Concluídas", "completed"); self.status.addItem("Todas", "all")
        self.status.currentIndexChanged.connect(self.refresh)
        self.horizon = QSpinBox(); self.horizon.setRange(0, 180); self.horizon.setValue(30); self.horizon.setSuffix(" dias"); self.horizon.valueChanged.connect(self.refresh)
        filters.addWidget(QLabel("Situação")); filters.addWidget(self.status); filters.addWidget(QLabel("Horizonte")); filters.addWidget(self.horizon); filters.addStretch()
        outer.addLayout(filters)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Prazo", "Atraso", "Tipo", "Área", "Macrofamília", "Conteúdo", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        for c in [0,1,2,3,4,6]: self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True); outer.addWidget(self.table, 1)
        self.refresh()

    def refresh(self, *args: Any) -> None:
        status = self.status.currentData(); limit_date = (date.today() + timedelta(days=self.horizon.value())).isoformat()
        where = "r.due_date<=?"; params: list[Any] = [limit_date]
        if status != "all": where += " AND r.status=?"; params.append(status)
        rows = self.db.query(
            f"""SELECT r.*, ci.title, mf.name AS macro_name, a.name AS area_name,
            CAST(julianday(date('now'))-julianday(r.due_date) AS INTEGER) AS late_days
            FROM reviews r JOIN content_items ci ON ci.id=r.content_item_id
            JOIN macro_families mf ON mf.id=ci.macro_family_id JOIN blocks b ON b.id=mf.block_id
            JOIN areas a ON a.id=b.area_id WHERE {where} ORDER BY r.due_date, ci.original_priority DESC""", params
        )
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            late = max(0, int(row["late_days"] or 0))
            vals = [row["due_date"], f"{late} d" if late else "—", row["review_type"], row["area_name"], row["macro_name"], row["title"], row["status"]]
            for c, val in enumerate(vals): self.table.setItem(r, c, readonly_item(val, Qt.AlignLeft | Qt.AlignVCenter if c in (4,5) else Qt.AlignCenter))


class ContentPage(BasePage):
    def __init__(self, db: Database) -> None:
        super().__init__(db)
        outer = QVBoxLayout(self); outer.setContentsMargins(24, 20, 24, 24)
        header = QHBoxLayout(); header.addWidget(title_label("Mapa de conteúdos", "Linhas originais, macrofamílias e progresso individual."), 1)
        self.search = QLineEdit(); self.search.setPlaceholderText("Pesquisar conteúdo..."); self.search.textChanged.connect(self.refresh)
        header.addWidget(self.search); outer.addLayout(header)
        self.tree = QTreeWidget(); self.tree.setHeaderLabels(["Estrutura", "IP", "Status", "Questões", "Tempo"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1,5): self.tree.header().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        outer.addWidget(self.tree, 1)
        self.refresh()

    def refresh(self, *args: Any) -> None:
        term = self.search.text().strip().lower(); self.tree.clear()
        areas = self.db.query("SELECT * FROM areas ORDER BY sort_order")
        for area in areas:
            area_node = QTreeWidgetItem([area["name"], "", "", "", ""]); area_node.setForeground(0, QColor(area["color"])); self.tree.addTopLevelItem(area_node)
            blocks = self.db.query("SELECT * FROM blocks WHERE area_id=? ORDER BY sort_order", (area["id"],))
            for block in blocks:
                block_node = QTreeWidgetItem([f"{block['code']} — {block['name']}", "", "", "", ""]); area_node.addChild(block_node)
                macros = self.db.query("SELECT * FROM macro_families WHERE block_id=? ORDER BY sort_order", (block["id"],))
                for macro in macros:
                    items = self.db.query("SELECT * FROM content_items WHERE macro_family_id=? ORDER BY sort_order", (macro["id"],))
                    visible = not term or term in macro["name"].lower() or any(term in item["title"].lower() for item in items)
                    if not visible: continue
                    done = sum(1 for i in items if i["status"] == "completed")
                    macro_node = QTreeWidgetItem([macro["name"], str(macro["base_priority"]), f"{done}/{len(items)}", "", f"{macro['estimated_minutes']} min"]); block_node.addChild(macro_node)
                    for item in items:
                        mins = int(item["total_minutes"] or 0)
                        child = QTreeWidgetItem([item["title"], str(item["original_priority"]), item["status"], str(item["total_questions"]), f"{mins} min"])
                        macro_node.addChild(child)
            area_node.setExpanded(bool(term))
        if term: self.tree.expandAll()


class ErrorsPage(BasePage):
    def __init__(self, db: Database) -> None:
        super().__init__(db)
        outer = QVBoxLayout(self); outer.setContentsMargins(24, 20, 24, 24)
        header = QHBoxLayout(); header.addWidget(title_label("Banco de erros", "Registro de falhas conceituais, interpretação, memória, cálculo e conduta."), 1)
        add = QPushButton("+ Registrar erro"); add.setObjectName("primary"); add.clicked.connect(self._add_error); header.addWidget(add)
        outer.addLayout(header)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Data", "Gravidade", "Tipo", "Área", "Conteúdo", "Descrição", "Resolvido"])
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        for c in [0,1,2,3,4,6]: self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True); outer.addWidget(self.table, 1); self.refresh()

    def refresh(self) -> None:
        rows = self.db.query(
            """SELECT e.*, ci.title, a.name AS area_name FROM errors e
            LEFT JOIN content_items ci ON ci.id=e.content_item_id
            LEFT JOIN macro_families mf ON mf.id=ci.macro_family_id LEFT JOIN blocks b ON b.id=mf.block_id
            LEFT JOIN areas a ON a.id=b.area_id ORDER BY e.resolved, e.severity DESC, e.created_at DESC"""
        )
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals = [row["created_at"][:10], row["severity"], row["error_type"], row["area_name"] or "—", row["title"] or "Livre", row["description"], "Sim" if row["resolved"] else "Não"]
            for c, val in enumerate(vals): self.table.setItem(r, c, readonly_item(val, Qt.AlignLeft | Qt.AlignVCenter if c in (4,5) else Qt.AlignCenter))

    def _add_error(self) -> None:
        dlg = QDialog(self); dlg.setWindowTitle("Registrar erro"); dlg.resize(620, 420); form = QFormLayout(dlg)
        area = QComboBox(); macros = QComboBox(); content = QComboBox(); err_type = QComboBox(); err_type.addItems(["concept", "interpretation", "memory", "calculation", "conduct"])
        severity = QSpinBox(); severity.setRange(1,3); severity.setValue(2)
        desc = QTextEdit(); correction = QTextEdit()
        areas = self.db.query("SELECT * FROM areas ORDER BY sort_order")
        for row in areas: area.addItem(row["name"], row["id"])
        def load_macros():
            macros.clear()
            for row in self.db.query("SELECT mf.* FROM macro_families mf JOIN blocks b ON b.id=mf.block_id WHERE b.area_id=? ORDER BY mf.name", (area.currentData(),)):
                macros.addItem(row["name"], row["id"])
        def load_items():
            content.clear()
            for row in self.db.query("SELECT * FROM content_items WHERE macro_family_id=? ORDER BY sort_order", (macros.currentData(),)):
                content.addItem(row["title"], row["id"])
        area.currentIndexChanged.connect(load_macros); macros.currentIndexChanged.connect(load_items); load_macros(); load_items()
        form.addRow("Área", area); form.addRow("Macrofamília", macros); form.addRow("Conteúdo", content); form.addRow("Tipo", err_type); form.addRow("Gravidade", severity); form.addRow("Erro", desc); form.addRow("Correção", correction)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); form.addRow(buttons); buttons.rejected.connect(dlg.reject)
        def save():
            if not desc.toPlainText().strip(): QMessageBox.warning(dlg, "Obrigatório", "Descreva o erro."); return
            self.db.execute("INSERT INTO errors(content_item_id,error_type,severity,description,correction) VALUES(?,?,?,?,?)", (content.currentData(), err_type.currentText(), severity.value(), desc.toPlainText().strip(), correction.toPlainText().strip()))
            dlg.accept(); self.refresh()
        buttons.accepted.connect(save); dlg.exec()


class TelemetryPage(BasePage):
    def __init__(self, db: Database) -> None:
        super().__init__(db)
        outer = QVBoxLayout(self); outer.setContentsMargins(24, 20, 24, 24)
        outer.addWidget(title_label("Telemetria", "Eficiência temporal, desempenho cognitivo e qualidade percebida."))
        self.cards = QGridLayout(); outer.addLayout(self.cards)
        self.metric_widgets = [MetricCard("Sessões registradas"), MetricCard("Tempo total"), MetricCard("Tempo médio"), MetricCard("Questões por hora"), MetricCard("Foco médio"), MetricCard("Uso do tempo")]
        for i,w in enumerate(self.metric_widgets): self.cards.addWidget(w, i//3, i%3)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["Data", "Área", "Macrofamília", "Previsto", "Real", "Desvio", "Questões", "Acertos", "Qualidade"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for c in [0,1,3,4,5,6,7,8]: self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True); outer.addWidget(self.table, 1); self.refresh()

    def refresh(self) -> None:
        totals = self.db.query("SELECT COUNT(*) n, COALESCE(SUM(actual_minutes),0) mins, COALESCE(SUM(questions_done),0) q, COALESCE(SUM(correct_answers),0) c, AVG(focus) focus, AVG(time_use) tuse FROM study_sessions")[0]
        n = int(totals["n"] or 0); mins = int(totals["mins"] or 0); q = int(totals["q"] or 0)
        vals = [str(n), f"{mins//60}h {mins%60:02d}", f"{mins/n:.0f} min" if n else "—", f"{q/(mins/60):.1f}" if mins else "—", f"{float(totals['focus']):.1f}/5" if totals["focus"] else "—", f"{float(totals['tuse']):.1f}/5" if totals["tuse"] else "—"]
        for w,v in zip(self.metric_widgets, vals): w.set_value(v)
        rows = self.db.query("""SELECT ss.*, a.name area_name, mf.name macro_name FROM study_sessions ss LEFT JOIN areas a ON a.id=ss.area_id LEFT JOIN macro_families mf ON mf.id=ss.macro_family_id ORDER BY ss.session_date DESC, ss.id DESC LIMIT 200""")
        self.table.setRowCount(len(rows))
        for r,row in enumerate(rows):
            est = int(row["estimated_minutes"] or 0); actual = int(row["actual_minutes"] or 0); dev = (100*(actual-est)/est) if est else 0; qn=int(row["questions_done"] or 0); corr=int(row["correct_answers"] or 0); acc=100*corr/qn if qn else 0
            quality = f"F{row['focus'] or '—'} · T{row['time_use'] or '—'}"
            vals=[row["session_date"],row["area_name"] or "Flexível",row["macro_name"] or row["session_type"],f"{est} min",f"{actual} min",f"{dev:+.0f}%" if est else "—",qn,f"{acc:.1f}%" if qn else "—",quality]
            for c,val in enumerate(vals): self.table.setItem(r,c,readonly_item(val,Qt.AlignLeft|Qt.AlignVCenter if c==2 else Qt.AlignCenter))


class SettingsPage(BasePage):
    theme_changed = Signal()

    def __init__(self, db: Database) -> None:
        super().__init__(db)
        outer = QVBoxLayout(self); outer.setContentsMargins(24, 20, 24, 24)
        outer.addWidget(title_label("Configurações", "Aparência, capacidade, datas e portabilidade do estado dos estudos."))
        panel, lay = card(); form = QFormLayout(); lay.addLayout(form)
        self.profile = QLineEdit(db.get_setting("profile_name", "Felipe"))
        self.theme = QComboBox(); self.theme.addItem("Escuro", "dark"); self.theme.addItem("Claro", "light")
        self.theme.setCurrentIndex(max(0, self.theme.findData(db.get_setting("theme", "dark"))))
        self.accent = QComboBox();
        for key in ACCENTS: self.accent.addItem(key.capitalize(), key)
        self.accent.setCurrentIndex(max(0, self.accent.findData(db.get_setting("accent", "violet"))))
        self.density = QComboBox(); self.density.addItem("Confortável", "comfortable"); self.density.addItem("Normal", "normal"); self.density.addItem("Compacta", "compact")
        self.density.setCurrentIndex(max(0, self.density.findData(db.get_setting("density", "comfortable"))))
        self.start = QDateEdit(); self.start.setCalendarPopup(True)
        start_txt = db.get_setting("study_start_date", ""); self.start.setDate(QDate.fromString(start_txt, "yyyy-MM-dd") if start_txt else QDate.currentDate())
        self.exam = QDateEdit(); self.exam.setCalendarPopup(True)
        exam_txt = db.get_setting("exam_date", ""); self.exam.setDate(QDate.fromString(exam_txt, "yyyy-MM-dd") if exam_txt else QDate.currentDate().addDays(140))
        self.daily = QSpinBox(); self.daily.setRange(30, 720); self.daily.setSuffix(" min"); self.daily.setValue(int(db.get_setting("daily_minutes", "180")))
        self.retention = QSpinBox(); self.retention.setRange(3, 90); self.retention.setSuffix(" dias"); self.retention.setValue(int(db.get_setting("backup_retention", "14")))
        self.auto_backup = QCheckBox("Criar backup automático diário"); self.auto_backup.setChecked(db.get_setting("auto_backup", "1") == "1")
        for label, widget in [("Nome do perfil", self.profile), ("Tema", self.theme), ("Cor de destaque", self.accent), ("Densidade", self.density), ("Início do ciclo", self.start), ("Data da prova", self.exam), ("Capacidade diária", self.daily), ("Retenção de backups", self.retention), ("Backup automático", self.auto_backup)]: form.addRow(label, widget)
        save_btn = QPushButton("Salvar configurações"); save_btn.setObjectName("primary"); save_btn.clicked.connect(self._save); lay.addWidget(save_btn)
        outer.addWidget(panel)

        backup_panel, backup_lay = card(); t=QLabel("Backup e migração"); t.setObjectName("sectionTitle"); backup_lay.addWidget(t)
        info=QLabel(f"Dados locais: {app_home()}"); info.setObjectName("muted"); info.setWordWrap(True); backup_lay.addWidget(info)
        row=QHBoxLayout(); export=QPushButton("Exportar .amrigs-save"); export.clicked.connect(self._export); import_btn=QPushButton("Importar save"); import_btn.clicked.connect(self._import); row.addWidget(export); row.addWidget(import_btn); row.addStretch(); backup_lay.addLayout(row)
        outer.addWidget(backup_panel); outer.addStretch()

    def _save(self) -> None:
        values={"profile_name":self.profile.text().strip(),"theme":self.theme.currentData(),"accent":self.accent.currentData(),"density":self.density.currentData(),"study_start_date":self.start.date().toString("yyyy-MM-dd"),"exam_date":self.exam.date().toString("yyyy-MM-dd"),"daily_minutes":self.daily.value(),"backup_retention":self.retention.value(),"auto_backup":1 if self.auto_backup.isChecked() else 0}
        for k,v in values.items(): self.db.set_setting(k,v)
        self.theme_changed.emit(); QMessageBox.information(self,"Configurações","Configurações salvas.")

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Exportar save", str(Path.home()/f"amrigs_studyos_{date.today():%Y%m%d}.amrigs-save"), "AMRIGS Save (*.amrigs-save)")
        if not path: return
        saved=create_save(self.db,Path(path)); QMessageBox.information(self,"Backup criado",f"Save exportado para:\n{saved}")

    def _import(self) -> None:
        path,_=QFileDialog.getOpenFileName(self,"Importar save",str(Path.home()),"AMRIGS Save (*.amrigs-save)")
        if not path: return
        ok,message,manifest=validate_save(Path(path))
        if not ok: QMessageBox.critical(self,"Save inválido",message); return
        text=f"Save válido, criado em {manifest.get('created_at','data desconhecida')}. O estado atual será salvo automaticamente antes da restauração. Continuar?"
        if QMessageBox.question(self,"Confirmar importação",text)!=QMessageBox.Yes: return
        restore_save(self.db,Path(path)); QMessageBox.information(self,"Importação preparada","O save será aplicado na próxima inicialização. Feche e abra o aplicativo.")


class MainWindow(QMainWindow):
    def __init__(self, db: Database) -> None:
        super().__init__(); self.db=db
        self.setWindowTitle(f"AMRIGS StudyOS {__version__}"); self.resize(1440,900); self.setMinimumSize(1100,700)
        root=QWidget(); self.setCentralWidget(root); layout=QHBoxLayout(root); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        sidebar=QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(225); side=QVBoxLayout(sidebar); side.setContentsMargins(12,18,12,14)
        brand=QLabel("AMRIGS\nStudyOS"); bf=brand.font(); bf.setPointSize(18); bf.setBold(True); brand.setFont(bf); side.addWidget(brand)
        version=QLabel(f"v{__version__} · local e offline"); version.setObjectName("muted"); side.addWidget(version); side.addSpacing(14)
        self.stack=QStackedWidget(); self.pages: list[BasePage]=[]; self.nav_buttons=[]
        page_defs=[("Dashboard",DashboardPage), ("Hoje",TodayPage), ("Cronograma",SchedulePage), ("Revisões",ReviewsPage), ("Conteúdos",ContentPage), ("Banco de erros",ErrorsPage), ("Telemetria",TelemetryPage), ("Configurações",SettingsPage)]
        for idx,(name,cls) in enumerate(page_defs):
            btn=QPushButton(name); btn.setObjectName("nav"); btn.setCheckable(True); btn.clicked.connect(lambda _=False,i=idx:self._navigate(i)); side.addWidget(btn); self.nav_buttons.append(btn)
            page=cls(db); self.pages.append(page); self.stack.addWidget(page)
        side.addStretch(); quick=QPushButton("+ Registrar sessão"); quick.setObjectName("primary"); quick.clicked.connect(self._quick_session); side.addWidget(quick)
        layout.addWidget(sidebar); layout.addWidget(self.stack,1)
        today_page=self.pages[1]
        if isinstance(today_page,TodayPage): today_page.changed.connect(self.refresh_all)
        schedule_page=self.pages[2]
        if isinstance(schedule_page,SchedulePage): schedule_page.changed.connect(self.refresh_all)
        settings_page=self.pages[-1]
        if isinstance(settings_page,SettingsPage): settings_page.theme_changed.connect(self.apply_theme)
        self._navigate(0); self.apply_theme()

    def apply_theme(self) -> None:
        QApplication.instance().setStyleSheet(stylesheet(self.db.get_setting("theme","dark"),self.db.get_setting("accent","violet"),self.db.get_setting("density","comfortable")))

    def _navigate(self,index:int) -> None:
        self.stack.setCurrentIndex(index)
        for i,b in enumerate(self.nav_buttons): b.setChecked(i==index)
        self.pages[index].refresh()

    def _quick_session(self) -> None:
        dlg=SessionDialog(self.db,None,self); dlg.saved.connect(self.refresh_all); dlg.exec()

    def refresh_all(self) -> None:
        for page in self.pages: page.refresh()

    def closeEvent(self,event) -> None:
        try: automatic_backup(self.db)
        finally: self.db.close()
        event.accept()


def main() -> int:
    apply_pending_restore()
    app=QApplication(sys.argv); app.setApplicationName("AMRIGS StudyOS"); app.setOrganizationName("Felipe Somavila")
    db=Database(); seed_catalog(db); ensure_default_schedule(db); automatic_backup(db)
    window=MainWindow(db); window.show()
    return app.exec()
