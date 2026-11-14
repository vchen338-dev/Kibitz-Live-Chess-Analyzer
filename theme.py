BG = "#101113"
PANEL = "#16171a"
RULE = "#25272b"
TEXT = "#e7e6e1"
MUTED = "#8b8e94"
FAINT = "#5c5f66"
ACCENT = "#7cc4a4"          
DANGER = "#d9776a"
MONO = '"Cascadia Mono", "Consolas", "Courier New", monospace'
SANS = '"Segoe UI Variable Text", "Segoe UI", "Helvetica Neue", sans-serif'

# 6-digit hex so chess.svg renders them. Best move = accent, others step down.
ARROW_COLORS = ["#4fae88", "#8b9aa6", "#5d6770"]
RANK_COLORS = [ACCENT, "#a9b3bb", "#7d868e"]

BOARD_COLORS = {
    "square light": "#e3dfd2",
    "square dark": "#7b8a79",
    "square light lastmove": "#d9d58b",
    "square dark lastmove": "#aab05f",
}

STYLE = f"""
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: {SANS};
    font-size: 10pt;
}}
QLabel {{ background: transparent; }}
QLabel#Section {{
    color: {FAINT};
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 1.4px;
}}
QLabel#Title {{ font-size: 13pt; font-weight: 600; color: {TEXT}; }}
QLabel#Version {{ font-family: {MONO}; font-size: 8pt; color: {FAINT}; }}
QLabel#Eval {{
    font-family: {MONO};
    font-size: 26pt;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#Muted {{ color: {MUTED}; }}
QLabel#Status {{ color: {MUTED}; font-size: 9pt; }}
QLabel#Turn {{ color: {MUTED}; font-size: 9pt; }}
QLabel#Preview {{
    background-color: {PANEL};
    border: 1px solid {RULE};
    border-radius: 4px;
    color: {FAINT};
}}
QFrame#Rule {{ background-color: {RULE}; max-height: 1px; min-height: 1px; border: none; }}
QFrame#Panel {{
    background-color: {PANEL};
    border: 1px solid {RULE};
    border-radius: 6px;
}}
QFrame#Panel QLabel {{ background: transparent; }}

QPushButton {{
    background-color: transparent;
    border: 1px solid {RULE};
    border-radius: 4px;
    padding: 7px 12px;
    color: {TEXT};
}}
QPushButton:hover {{ background-color: #1d1f23; border-color: #343741; }}
QPushButton:pressed {{ background-color: #131417; }}
QPushButton:disabled {{ color: {FAINT}; border-color: #1b1d20; }}
QPushButton#Primary {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
    color: #0c1511;
    font-weight: 600;
}}
QPushButton#Primary:hover {{ background-color: #92d2b6; border-color: #92d2b6; }}
QPushButton#Primary:disabled {{ background-color: #1b1d20; border-color: #1b1d20; color: {FAINT}; }}
QPushButton#Danger {{
    border: 1px solid {DANGER};
    color: {DANGER};
    font-weight: 600;
}}
QPushButton#Danger:hover {{ background-color: #2a1a18; }}

QComboBox, QDoubleSpinBox {{
    background-color: {PANEL};
    border: 1px solid {RULE};
    border-radius: 4px;
    padding: 4px 8px;
    min-width: 84px;
    color: {TEXT};
    font-family: {MONO};
    font-size: 9pt;
}}
QComboBox:hover, QDoubleSpinBox:hover {{ border-color: #343741; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background-color: {PANEL};
    border: 1px solid {RULE};
    selection-background-color: #23262b;
    selection-color: {TEXT};
    outline: none;
}}
QProgressBar {{
    background-color: {RULE};
    border: none;
    border-radius: 2px;
    max-height: 4px;
    min-height: 4px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background-color: {ACCENT}; border-radius: 2px; }}
"""