from __future__ import annotations

ACCENTS = {
    "violet": "#7C3AED",
    "blue": "#2563EB",
    "emerald": "#059669",
    "rose": "#E11D48",
    "amber": "#D97706",
}


def stylesheet(theme: str = "dark", accent_name: str = "violet", density: str = "comfortable") -> str:
    accent = ACCENTS.get(accent_name, ACCENTS["violet"])
    dark = theme != "light"
    bg = "#0B1020" if dark else "#F4F6FA"
    surface = "#121A2E" if dark else "#FFFFFF"
    surface2 = "#18233C" if dark else "#EEF2F7"
    border = "#263554" if dark else "#D9E0EA"
    text = "#F7F9FC" if dark else "#152033"
    muted = "#9AA9C1" if dark else "#64748B"
    danger = "#EF4444"
    warning = "#F59E0B"
    success = "#10B981"
    pad = 10 if density == "comfortable" else 7 if density == "normal" else 4
    row = 38 if density == "comfortable" else 32 if density == "normal" else 27
    return f"""
    * {{ font-family: 'Segoe UI', 'Inter', Arial; color: {text}; }}
    QMainWindow, QWidget {{ background: {bg}; }}
    QLabel#muted {{ color: {muted}; }}
    QLabel#pageTitle {{ font-size: 24px; font-weight: 700; }}
    QLabel#sectionTitle {{ font-size: 15px; font-weight: 700; }}
    QFrame#card {{ background: {surface}; border: 1px solid {border}; border-radius: 14px; }}
    QFrame#sidebar {{ background: {surface}; border-right: 1px solid {border}; }}
    QPushButton {{
        background: {surface2}; border: 1px solid {border}; border-radius: 9px;
        padding: {pad}px 12px; font-weight: 600;
    }}
    QPushButton:hover {{ border-color: {accent}; }}
    QPushButton:pressed {{ background: {accent}; }}
    QPushButton#primary {{ background: {accent}; border-color: {accent}; color: white; }}
    QPushButton#danger {{ background: {danger}; border-color: {danger}; color: white; }}
    QPushButton#nav {{ text-align: left; border: none; background: transparent; padding: 11px 14px; }}
    QPushButton#nav:hover {{ background: {surface2}; }}
    QPushButton#nav:checked {{ background: {accent}; color: white; }}
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateEdit, QTimeEdit {{
        background: {surface}; border: 1px solid {border}; border-radius: 8px; padding: 8px;
        selection-background-color: {accent};
    }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {{ border-color: {accent}; }}
    QComboBox QAbstractItemView {{ background: {surface}; border: 1px solid {border}; selection-background-color: {accent}; }}
    QTableWidget, QTreeWidget {{
        background: {surface}; alternate-background-color: {surface2}; border: 1px solid {border};
        border-radius: 10px; gridline-color: {border}; selection-background-color: {accent};
    }}
    QHeaderView::section {{ background: {surface2}; border: none; border-right: 1px solid {border}; padding: 8px; font-weight: 700; }}
    QTableView::item {{ min-height: {row}px; padding: 4px; }}
    QProgressBar {{ background: {surface2}; border: none; border-radius: 6px; text-align: center; min-height: 12px; }}
    QProgressBar::chunk {{ background: {accent}; border-radius: 6px; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; }}
    QTabWidget::pane {{ border: 1px solid {border}; border-radius: 10px; }}
    QTabBar::tab {{ background: {surface2}; padding: 9px 14px; margin-right: 2px; }}
    QTabBar::tab:selected {{ background: {accent}; color: white; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; }}
    QScrollBar::handle:vertical {{ background: {border}; border-radius: 5px; min-height: 30px; }}
    QToolTip {{ background: {surface}; color: {text}; border: 1px solid {border}; padding: 6px; }}
    """
