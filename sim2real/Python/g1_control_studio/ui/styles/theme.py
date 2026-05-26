"""
Dark engineering theme for G1 Control Studio.

Palette
-------
  BG_BASE       #080D1A  — app background
  BG_SURFACE    #0F1628  — card / panel
  BG_ELEVATED   #172033  — header / sidebar
  BG_INPUT      #1A2540  — input fields
  BG_HOVER      #1E2D4A  — hover state
  BG_ACTIVE     #0A1E3D  — pressed / active
  BORDER        #1E2D45  — default border
  BORDER_LIGHT  #253555  — lighter border

  ACCENT        #00B4D8  — primary electric blue
  ACCENT_GLOW   #00D4FF  — brighter accent
  ACCENT_MUTED  #0077A3  — dimmed accent

  SUCCESS       #10B981  — green
  WARNING       #F59E0B  — amber
  DANGER        #EF4444  — red
  INFO          #6366F1  — indigo

  TEXT_PRIMARY  #E2E8F0
  TEXT_SEC      #94A3B8
  TEXT_MUTED    #4B5563
  TEXT_ACCENT   #00B4D8
"""


PALETTE = {
    "BG_BASE": "#080D1A",
    "BG_SURFACE": "#0F1628",
    "BG_ELEVATED": "#172033",
    "BG_INPUT": "#1A2540",
    "BG_HOVER": "#1E2D4A",
    "BG_ACTIVE": "#0A1E3D",
    "BORDER": "#1E2D45",
    "BORDER_LIGHT": "#253555",
    "ACCENT": "#00B4D8",
    "ACCENT_GLOW": "#00D4FF",
    "ACCENT_MUTED": "#0077A3",
    "SUCCESS": "#10B981",
    "WARNING": "#F59E0B",
    "DANGER": "#EF4444",
    "INFO": "#6366F1",
    "TEXT_PRIMARY": "#E2E8F0",
    "TEXT_SEC": "#94A3B8",
    "TEXT_MUTED": "#4B5563",
    "TEXT_ACCENT": "#00B4D8",
}

# Status color shortcuts used across components
STATUS_COLORS = {
    "ok": PALETTE["SUCCESS"],
    "warning": PALETTE["WARNING"],
    "error": PALETTE["DANGER"],
    "inactive": PALETTE["TEXT_MUTED"],
    "info": PALETTE["ACCENT"],
}


def build_stylesheet() -> str:
    c = PALETTE
    return f"""
/* ─── Global ─────────────────────────────────────────────────── */
QWidget {{
    background-color: {c['BG_BASE']};
    color: {c['TEXT_PRIMARY']};
    font-family: "Inter", "Segoe UI", "Ubuntu", sans-serif;
    font-size: 13px;
    border: none;
    outline: none;
}}

QMainWindow {{
    background-color: {c['BG_BASE']};
}}

/* ─── ScrollArea ──────────────────────────────────────────────── */
QScrollArea {{
    background-color: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}
QScrollBar:vertical {{
    background: {c['BG_SURFACE']};
    width: 6px;
    margin: 0;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {c['BORDER_LIGHT']};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c['ACCENT_MUTED']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {c['BG_SURFACE']};
    height: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: {c['BORDER_LIGHT']};
    border-radius: 3px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {c['ACCENT_MUTED']};
}}

/* ─── Labels ──────────────────────────────────────────────────── */
QLabel {{
    background: transparent;
    color: {c['TEXT_PRIMARY']};
}}
QLabel[class="title"] {{
    font-size: 20px;
    font-weight: 700;
    color: {c['TEXT_PRIMARY']};
}}
QLabel[class="subtitle"] {{
    font-size: 13px;
    color: {c['TEXT_SEC']};
}}
QLabel[class="section-header"] {{
    font-size: 11px;
    font-weight: 600;
    color: {c['TEXT_MUTED']};
    letter-spacing: 1.5px;
    text-transform: uppercase;
}}
QLabel[class="value"] {{
    font-size: 24px;
    font-weight: 700;
    color: {c['ACCENT']};
}}
QLabel[class="mono"] {{
    font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
    font-size: 12px;
    color: {c['TEXT_SEC']};
}}

/* ─── Buttons ─────────────────────────────────────────────────── */
QPushButton {{
    background-color: {c['BG_ELEVATED']};
    color: {c['TEXT_PRIMARY']};
    border: 1px solid {c['BORDER_LIGHT']};
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 500;
    min-height: 34px;
}}
QPushButton:hover {{
    background-color: {c['BG_HOVER']};
    border-color: {c['ACCENT_MUTED']};
    color: {c['ACCENT_GLOW']};
}}
QPushButton:pressed {{
    background-color: {c['BG_ACTIVE']};
    border-color: {c['ACCENT']};
}}
QPushButton:disabled {{
    background-color: {c['BG_SURFACE']};
    color: {c['TEXT_MUTED']};
    border-color: {c['BORDER']};
}}

QPushButton[class="primary"] {{
    background-color: {c['ACCENT']};
    color: #000000;
    border: none;
    font-weight: 600;
}}
QPushButton[class="primary"]:hover {{
    background-color: {c['ACCENT_GLOW']};
    color: #000000;
}}
QPushButton[class="primary"]:pressed {{
    background-color: {c['ACCENT_MUTED']};
}}
QPushButton[class="primary"]:disabled {{
    background-color: {c['BG_ELEVATED']};
    color: {c['TEXT_MUTED']};
}}

QPushButton[class="danger"] {{
    background-color: transparent;
    color: {c['DANGER']};
    border: 1px solid {c['DANGER']};
}}
QPushButton[class="danger"]:hover {{
    background-color: #3D1515;
    border-color: #FF6B6B;
    color: #FF6B6B;
}}
QPushButton[class="danger"]:pressed {{
    background-color: #5A1A1A;
}}

QPushButton[class="success"] {{
    background-color: transparent;
    color: {c['SUCCESS']};
    border: 1px solid {c['SUCCESS']};
}}
QPushButton[class="success"]:hover {{
    background-color: #0D3D2A;
    border-color: #34D399;
    color: #34D399;
}}

QPushButton[class="ghost"] {{
    background-color: transparent;
    color: {c['TEXT_SEC']};
    border: none;
}}
QPushButton[class="ghost"]:hover {{
    color: {c['ACCENT']};
    background-color: {c['BG_HOVER']};
}}

/* ─── Line Edits ──────────────────────────────────────────────── */
QLineEdit {{
    background-color: {c['BG_INPUT']};
    color: {c['TEXT_PRIMARY']};
    border: 1px solid {c['BORDER']};
    border-radius: 6px;
    padding: 7px 12px;
    font-size: 13px;
    selection-background-color: {c['ACCENT_MUTED']};
}}
QLineEdit:focus {{
    border-color: {c['ACCENT']};
}}
QLineEdit:disabled {{
    color: {c['TEXT_MUTED']};
    background-color: {c['BG_SURFACE']};
}}
QLineEdit[readOnly="true"] {{
    color: {c['TEXT_SEC']};
    background-color: {c['BG_SURFACE']};
}}

/* ─── ComboBox ────────────────────────────────────────────────── */
QComboBox {{
    background-color: {c['BG_INPUT']};
    color: {c['TEXT_PRIMARY']};
    border: 1px solid {c['BORDER']};
    border-radius: 6px;
    padding: 7px 12px;
    font-size: 13px;
    min-height: 34px;
}}
QComboBox:focus {{
    border-color: {c['ACCENT']};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {c['TEXT_SEC']};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {c['BG_ELEVATED']};
    color: {c['TEXT_PRIMARY']};
    border: 1px solid {c['BORDER_LIGHT']};
    border-radius: 6px;
    selection-background-color: {c['BG_HOVER']};
    selection-color: {c['ACCENT_GLOW']};
    outline: none;
    padding: 4px;
}}

/* ─── SpinBox ─────────────────────────────────────────────────── */
QSpinBox {{
    background-color: {c['BG_INPUT']};
    color: {c['TEXT_PRIMARY']};
    border: 1px solid {c['BORDER']};
    border-radius: 6px;
    padding: 7px 12px;
    font-size: 13px;
}}
QSpinBox:focus {{
    border-color: {c['ACCENT']};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {c['BG_ELEVATED']};
    border: none;
    width: 20px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background-color: {c['BG_HOVER']};
}}

/* ─── CheckBox ────────────────────────────────────────────────── */
QCheckBox {{
    color: {c['TEXT_PRIMARY']};
    spacing: 8px;
    font-size: 13px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {c['BORDER_LIGHT']};
    background-color: {c['BG_INPUT']};
}}
QCheckBox::indicator:checked {{
    background-color: {c['ACCENT']};
    border-color: {c['ACCENT']};
}}
QCheckBox::indicator:hover {{
    border-color: {c['ACCENT']};
}}

/* ─── GroupBox ────────────────────────────────────────────────── */
QGroupBox {{
    background-color: {c['BG_SURFACE']};
    border: 1px solid {c['BORDER']};
    border-radius: 8px;
    margin-top: 16px;
    padding: 16px 12px 12px 12px;
    font-size: 12px;
    font-weight: 600;
    color: {c['TEXT_SEC']};
    letter-spacing: 1px;
    text-transform: uppercase;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    top: -2px;
    padding: 0 6px;
    background-color: {c['BG_SURFACE']};
    color: {c['TEXT_SEC']};
}}

/* ─── Tab Widget ──────────────────────────────────────────────── */
QTabWidget::pane {{
    background-color: {c['BG_SURFACE']};
    border: 1px solid {c['BORDER']};
    border-radius: 0 8px 8px 8px;
}}
QTabBar::tab {{
    background-color: {c['BG_ELEVATED']};
    color: {c['TEXT_SEC']};
    border: 1px solid {c['BORDER']};
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    padding: 8px 18px;
    font-size: 13px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {c['BG_SURFACE']};
    color: {c['ACCENT']};
    border-bottom-color: {c['BG_SURFACE']};
}}
QTabBar::tab:hover {{
    background-color: {c['BG_HOVER']};
    color: {c['TEXT_PRIMARY']};
}}

/* ─── TextEdit / PlainTextEdit ───────────────────────────────── */
QTextEdit, QPlainTextEdit {{
    background-color: {c['BG_SURFACE']};
    color: {c['TEXT_SEC']};
    border: 1px solid {c['BORDER']};
    border-radius: 6px;
    padding: 8px;
    font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
    font-size: 12px;
    selection-background-color: {c['ACCENT_MUTED']};
}}

/* ─── Splitter ────────────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {c['BORDER']};
}}
QSplitter::handle:horizontal {{
    width: 2px;
}}
QSplitter::handle:vertical {{
    height: 2px;
}}
QSplitter::handle:hover {{
    background-color: {c['ACCENT_MUTED']};
}}

/* ─── ToolTip ─────────────────────────────────────────────────── */
QToolTip {{
    background-color: {c['BG_ELEVATED']};
    color: {c['TEXT_PRIMARY']};
    border: 1px solid {c['BORDER_LIGHT']};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ─── MessageBox ──────────────────────────────────────────────── */
QMessageBox {{
    background-color: {c['BG_ELEVATED']};
    color: {c['TEXT_PRIMARY']};
}}
QMessageBox QLabel {{
    color: {c['TEXT_PRIMARY']};
}}
QMessageBox QPushButton {{
    min-width: 80px;
}}

/* ─── Dialog ──────────────────────────────────────────────────── */
QDialog {{
    background-color: {c['BG_ELEVATED']};
}}

/* ─── Separator ───────────────────────────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    background-color: {c['BORDER']};
    border: none;
    max-height: 1px;
}}

/* ─── Sidebar specific ────────────────────────────────────────── */
#sidebar {{
    background-color: #070C18;
    border-right: 1px solid {c['BORDER']};
    min-width: 220px;
    max-width: 220px;
}}
#sidebar-logo {{
    color: {c['ACCENT']};
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.5px;
    padding: 0;
}}
#sidebar-subtitle {{
    color: {c['TEXT_MUTED']};
    font-size: 10px;
    letter-spacing: 1.5px;
}}
#sidebar-nav-btn {{
    background-color: transparent;
    color: {c['TEXT_SEC']};
    border: none;
    border-radius: 6px;
    text-align: left;
    padding: 10px 14px;
    font-size: 13px;
    font-weight: 400;
    min-height: 38px;
}}
#sidebar-nav-btn:hover {{
    background-color: {c['BG_HOVER']};
    color: {c['TEXT_PRIMARY']};
}}
#sidebar-nav-btn[active="true"] {{
    background-color: {c['BG_ACTIVE']};
    color: {c['ACCENT_GLOW']};
    border-left: 3px solid {c['ACCENT']};
    font-weight: 600;
}}
#sidebar-section-label {{
    color: {c['TEXT_MUTED']};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.5px;
    padding: 6px 14px 2px;
    background: transparent;
}}

/* ─── Header bar ──────────────────────────────────────────────── */
#header-bar {{
    background-color: {c['BG_ELEVATED']};
    border-bottom: 1px solid {c['BORDER']};
    min-height: 52px;
    max-height: 52px;
}}
#header-title {{
    color: {c['TEXT_PRIMARY']};
    font-size: 14px;
    font-weight: 600;
}}

/* ─── Page container ──────────────────────────────────────────── */
#page-container {{
    background-color: {c['BG_BASE']};
}}
#page-title {{
    font-size: 22px;
    font-weight: 700;
    color: {c['TEXT_PRIMARY']};
}}
#page-description {{
    font-size: 13px;
    color: {c['TEXT_SEC']};
}}

/* ─── Cards ───────────────────────────────────────────────────── */
#card {{
    background-color: {c['BG_SURFACE']};
    border: 1px solid {c['BORDER']};
    border-radius: 10px;
}}
#card-title {{
    font-size: 11px;
    font-weight: 600;
    color: {c['TEXT_MUTED']};
    letter-spacing: 1px;
    text-transform: uppercase;
}}
#card-value {{
    font-size: 26px;
    font-weight: 700;
    color: {c['TEXT_PRIMARY']};
}}
#card-unit {{
    font-size: 13px;
    color: {c['TEXT_SEC']};
}}

/* ─── Step indicator ──────────────────────────────────────────── */
#step-item {{
    background-color: {c['BG_SURFACE']};
    border: 1px solid {c['BORDER']};
    border-radius: 8px;
    padding: 12px;
}}
#step-item[state="active"] {{
    border-color: {c['ACCENT']};
    background-color: {c['BG_ACTIVE']};
}}
#step-item[state="done"] {{
    border-color: {c['SUCCESS']};
    background-color: #0B2820;
}}
#step-item[state="error"] {{
    border-color: {c['DANGER']};
    background-color: #2D1010;
}}

/* ─── Log console ─────────────────────────────────────────────── */
#log-console {{
    background-color: #050A14;
    color: #9DBBDD;
    font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
    font-size: 12px;
    border: 1px solid {c['BORDER']};
    border-radius: 6px;
    padding: 8px;
}}

/* ─── Status badge ────────────────────────────────────────────── */
#badge {{
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}
"""
