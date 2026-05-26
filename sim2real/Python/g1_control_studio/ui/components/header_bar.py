from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal

from ui.components.status_badge import StatusBadge
from ui.styles.theme import PALETTE

# Bridge states → (dot color, label, tooltip, button enabled)
_BRIDGE_STATES = {
    "idle":       (PALETTE["TEXT_MUTED"], "IDLE",        "Click to connect the SLAM bridge",    True),
    "connecting": (PALETTE["WARNING"],    "CONNECTING…", "Bridge is starting…",                 False),
    "ready":      (PALETTE["SUCCESS"],    "READY",       "Bridge connected — click to disconnect", True),
    "error":      (PALETTE["DANGER"],     "ERROR",       "Bridge error — click to retry",       True),
}


class HeaderBar(QWidget):
    """
    Top status bar. The SLAM Bridge button lives here so it is always
    reachable regardless of which page is active.
    """

    bridge_clicked = Signal()   # MainWindow connects this to the toggle logic

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("header-bar")
        self.setFixedHeight(52)
        self._bridge_state = "idle"
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(12)

        # Page title (left side)
        self._page_title = QLabel("Dashboard")
        self._page_title.setObjectName("header-title")
        layout.addWidget(self._page_title)

        layout.addStretch()

        # ── Status indicators ──────────────────────────────────────
        ros_lbl = QLabel("ROS2")
        ros_lbl.setStyleSheet(f"color: {PALETTE['TEXT_MUTED']}; font-size: 11px;")
        layout.addWidget(ros_lbl)
        self._ros_badge = StatusBadge("—", "inactive")
        layout.addWidget(self._ros_badge)

        self._separator(layout)

        net_lbl = QLabel("NET")
        net_lbl.setStyleSheet(f"color: {PALETTE['TEXT_MUTED']}; font-size: 11px;")
        layout.addWidget(net_lbl)
        self._net_label = QLabel("—")
        self._net_label.setStyleSheet(
            f"color: {PALETTE['TEXT_SEC']}; font-size: 12px;"
            f" font-family: 'JetBrains Mono', monospace;"
        )
        layout.addWidget(self._net_label)

        self._separator(layout)

        # ── SLAM Bridge button ─────────────────────────────────────
        bridge_lbl = QLabel("SLAM")
        bridge_lbl.setStyleSheet(f"color: {PALETTE['TEXT_MUTED']}; font-size: 11px;")
        layout.addWidget(bridge_lbl)

        self._bridge_btn = QPushButton("●  IDLE")
        self._bridge_btn.setFixedHeight(30)
        self._bridge_btn.setMinimumWidth(110)
        self._bridge_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bridge_btn.clicked.connect(self.bridge_clicked)
        layout.addWidget(self._bridge_btn)

        self._apply_bridge_style()

    # ------------------------------------------------------------------
    # Public update methods
    # ------------------------------------------------------------------

    def set_page_title(self, title: str) -> None:
        self._page_title.setText(title)

    def set_ros_status(self, state: str, text: str) -> None:
        self._ros_badge.set_state(state, text)

    def set_network_interface(self, iface: str) -> None:
        self._net_label.setText(iface or "—")

    def set_bridge_state(self, state: str) -> None:
        """state: 'idle' | 'connecting' | 'ready' | 'error'"""
        self._bridge_state = state
        self._apply_bridge_style()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_bridge_style(self) -> None:
        color, label, tip, enabled = _BRIDGE_STATES.get(
            self._bridge_state, _BRIDGE_STATES["idle"]
        )
        self._bridge_btn.setText(f"●  {label}")
        self._bridge_btn.setEnabled(enabled)
        self._bridge_btn.setToolTip(tip)
        self._bridge_btn.setStyleSheet(
            f"QPushButton {{ background: {color}22; color: {color};"
            f" border: 1px solid {color}55; border-radius: 6px;"
            f" padding: 0 12px; font-weight: bold; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {color}44; }}"
            f"QPushButton:disabled {{ color: {PALETTE['TEXT_MUTED']};"
            f" background: {PALETTE['BG_ELEVATED']};"
            f" border-color: {PALETTE['BORDER']}; }}"
        )

    @staticmethod
    def _separator(layout: QHBoxLayout) -> None:
        sep = QLabel("|")
        sep.setStyleSheet(f"color: {PALETTE['BORDER_LIGHT']}; font-size: 16px; padding: 0 4px;")
        layout.addWidget(sep)
