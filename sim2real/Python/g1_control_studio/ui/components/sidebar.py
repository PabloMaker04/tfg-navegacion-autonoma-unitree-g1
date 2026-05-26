from __future__ import annotations

from dataclasses import dataclass
from typing import List, Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PySide6.QtCore import Signal, Qt

from ui.styles.theme import PALETTE


@dataclass
class NavItem:
    key: str
    label: str
    icon: str          # Unicode character used as icon
    section: str = ""  # Optional section header above this item


_NAV_ITEMS: List[NavItem] = [
    NavItem("dashboard",     "Dashboard",     "⬡",  section="OVERVIEW"),
    NavItem("mapping",       "Mapping",       "◈",  section="WORKFLOWS"),
    NavItem("localization",  "Localization",  "◎"),
    NavItem("navigation",    "Navigation",    "▶"),
    NavItem("rviz",          "RViz2",         "⬛", section="TOOLS"),
    NavItem("logs",          "Logs",          "≡"),
    NavItem("settings",      "Settings",      "⚙",  section="SYSTEM"),
]


class Sidebar(QWidget):
    """
    Left navigation sidebar.

    Signals
    -------
    page_requested(key: str)  — emitted when the user clicks a nav item
    """

    page_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self._buttons: dict[str, QPushButton] = {}
        self._active_key: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 16)
        layout.setSpacing(0)

        # ── Logo ──────────────────────────────────────────────────
        logo_widget = QWidget()
        logo_layout = QVBoxLayout(logo_widget)
        logo_layout.setContentsMargins(4, 0, 0, 0)
        logo_layout.setSpacing(2)

        logo = QLabel("G1 Control Studio")
        logo.setObjectName("sidebar-logo")
        logo_layout.addWidget(logo)

        sub = QLabel("UNITREE G1 SDK")
        sub.setObjectName("sidebar-subtitle")
        logo_layout.addWidget(sub)

        layout.addWidget(logo_widget)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {PALETTE['BORDER']}; max-height: 1px; margin: 14px 0 10px 0;")
        layout.addWidget(sep)

        # ── Navigation items ───────────────────────────────────────
        last_section = ""
        for item in _NAV_ITEMS:
            if item.section and item.section != last_section:
                sec_lbl = QLabel(item.section)
                sec_lbl.setObjectName("sidebar-section-label")
                sec_lbl.setContentsMargins(4, 10, 0, 2)
                layout.addWidget(sec_lbl)
                last_section = item.section

            btn = self._make_nav_button(item)
            layout.addWidget(btn)
            self._buttons[item.key] = btn

        layout.addStretch()

        # ── Version footer ─────────────────────────────────────────
        ver = QLabel("v1.0.0")
        ver.setObjectName("sidebar-section-label")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setContentsMargins(0, 0, 0, 4)
        layout.addWidget(ver)

    def _make_nav_button(self, item: NavItem) -> QPushButton:
        btn = QPushButton(f"  {item.icon}   {item.label}")
        btn.setObjectName("sidebar-nav-btn")
        btn.setProperty("active", "false")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _checked, k=item.key: self._on_click(k))
        return btn

    def _on_click(self, key: str) -> None:
        self.set_active(key)
        self.page_requested.emit(key)

    def set_active(self, key: str) -> None:
        if self._active_key:
            prev = self._buttons.get(self._active_key)
            if prev:
                prev.setProperty("active", "false")
                prev.style().unpolish(prev)
                prev.style().polish(prev)

        self._active_key = key
        btn = self._buttons.get(key)
        if btn:
            btn.setProperty("active", "true")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
