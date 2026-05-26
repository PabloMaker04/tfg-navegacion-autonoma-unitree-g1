"""
Mapping page — Phase 6.
Guided SLAM mapping workflow: connect bridge → start mapping → save map.
"""
from __future__ import annotations

from enum import Enum, auto

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from config.app_config import AppConfig
from core.rviz_manager import RVizManager, RVizConfig
from services.slam_service import SlamService
from ui.pages.base_page import BasePage
from ui.styles.theme import PALETTE


class _State(Enum):
    IDLE       = auto()
    CONNECTING = auto()
    READY      = auto()
    MAPPING    = auto()
    SAVING     = auto()
    DONE       = auto()


_STATE_LABEL: dict[_State, tuple[str, str]] = {
    _State.IDLE:       ("IDLE",       PALETTE["TEXT_MUTED"]),
    _State.CONNECTING: ("CONNECTING", PALETTE["WARNING"]),
    _State.READY:      ("READY",      PALETTE["SUCCESS"]),
    _State.MAPPING:    ("MAPPING",    PALETTE["ACCENT"]),
    _State.SAVING:     ("SAVING",     PALETTE["WARNING"]),
    _State.DONE:       ("DONE",       PALETTE["SUCCESS"]),
}

_STEPS = [
    "1. Connect SDK bridge",
    "2. Start SLAM mapping (indoor)",
    "3. Walk the robot around to build the map",
    "4. Save map to robot  (/home/unitree/test.pcd)",
]

_STATUS_TEXT: dict[_State, str] = {
    _State.IDLE:       "Bridge not connected — use the SLAM button in the header",
    _State.CONNECTING: "Connecting to SDK bridge…",
    _State.READY:      "Bridge ready — start mapping when ready",
    _State.MAPPING:    "Mapping active — drive the robot to explore the space",
    _State.SAVING:     "Saving map to robot…",
    _State.DONE:       "Map saved — proceed to Localization",
}


class MappingPage(BasePage):
    PAGE_KEY = "mapping"
    PAGE_TITLE = "Mapping"
    PAGE_DESCRIPTION = (
        "Guided SLAM mapping: connect to the SDK bridge, start indoor mapping, "
        "visualize the point cloud in RViz2, and save the map to the robot."
    )

    def __init__(
        self,
        config: AppConfig,
        rviz_manager: RVizManager,
        slam_service: SlamService,
        parent=None,
    ) -> None:
        self._config = config
        self._rm = rviz_manager
        self._slam = slam_service
        self._state = _State.IDLE
        super().__init__(parent)
        self._build_content()
        self._connect_signals()
        self._refresh_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_content(self) -> None:
        cols = QHBoxLayout()
        cols.setSpacing(16)
        self._build_left(cols)
        self._build_log(cols)
        self._content_layout.addLayout(cols)

    def _build_left(self, parent: QHBoxLayout) -> None:
        left = QVBoxLayout()
        left.setSpacing(12)

        # Status row
        sc = self._card("Status")
        row = QHBoxLayout()
        row.setSpacing(8)
        self._dot   = QLabel("●")
        self._dot.setFixedWidth(18)
        self._s_lbl = QLabel()
        row.addWidget(self._dot)
        row.addWidget(self._s_lbl, 1)
        sc.layout().addLayout(row)
        left.addWidget(sc)

        # Workflow steps
        wc = self._card("Workflow Steps")
        self._step_labels: list[QLabel] = []
        for text in _STEPS:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"font-size: 12px;")
            self._step_labels.append(lbl)
            wc.layout().addWidget(lbl)
        left.addWidget(wc)

        # Live pose
        pc = self._card("Current Robot Pose")
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(5)
        self._pose_vals: dict[str, QLabel] = {}
        for col, keys in enumerate([["x", "y", "z"], ["q_x", "q_y", "q_z", "q_w"]]):
            for row, k in enumerate(keys):
                lbl = QLabel(f"{k}:")
                lbl.setStyleSheet(f"color: {PALETTE['TEXT_MUTED']}; font-size: 11px;")
                val = QLabel("—")
                val.setStyleSheet(
                    f"color: {PALETTE['ACCENT']}; font-family: monospace; font-size: 12px;"
                )
                grid.addWidget(lbl, row, col * 2)
                grid.addWidget(val, row, col * 2 + 1)
                self._pose_vals[k] = val
        pc.layout().addLayout(grid)
        left.addWidget(pc)

        # Controls
        cc = self._card("Controls")
        cc.layout().setSpacing(10)
        self._btn_start_map = self._btn("Start Mapping",      PALETTE["SUCCESS"])
        self._btn_rviz      = self._btn("Open RViz2",         PALETTE["ACCENT_MUTED"])
        self._btn_save      = self._btn("Save Map",           PALETTE["WARNING"])
        self._btn_stop      = self._btn("Stop / Disconnect",  PALETTE["DANGER"])
        self._btn_rviz.setVisible(False)
        for b in [self._btn_start_map, self._btn_rviz, self._btn_save, self._btn_stop]:
            cc.layout().addWidget(b)
        self._btn_start_map.clicked.connect(self._on_start_mapping)
        self._btn_rviz.clicked.connect(self._on_open_rviz)
        self._btn_save.clicked.connect(self._on_save_map)
        self._btn_stop.clicked.connect(self._on_stop)
        left.addWidget(cc)

        left.addStretch()
        parent.addLayout(left, 2)

    def _build_log(self, parent: QHBoxLayout) -> None:
        right = QVBoxLayout()
        right.setSpacing(6)
        hdr = QLabel("Activity Log")
        hdr.setStyleSheet(
            f"color: {PALETTE['TEXT_MUTED']}; font-size: 10px; font-weight: bold;"
            f" text-transform: uppercase; letter-spacing: 1px;"
        )
        right.addWidget(hdr)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(
            f"QTextEdit {{ background: {PALETTE['BG_BASE']}; color: {PALETTE['TEXT_SEC']};"
            f" border: 1px solid {PALETTE['BORDER']}; border-radius: 6px;"
            f" font-family: monospace; font-size: 11px; padding: 8px; }}"
        )
        right.addWidget(self._log, 1)
        parent.addLayout(right, 1)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._slam.bridge_ready.connect(self._on_bridge_ready)
        self._slam.bridge_stopped.connect(self._on_bridge_stopped)
        self._slam.bridge_error.connect(self._on_bridge_error)
        self._slam.status_received.connect(self._on_status)
        self._slam.pose_updated.connect(self._on_pose)
        self._slam.api_result.connect(self._on_api_result)
        self._slam.raw_log.connect(self._on_raw_log)

    # ------------------------------------------------------------------
    # Show-event: sync with current bridge state
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._slam.is_ready and self._state == _State.IDLE:
            self._set_state(_State.READY)
        elif self._slam.is_running and self._state == _State.IDLE:
            self._set_state(_State.CONNECTING)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _card(self, title: str) -> QGroupBox:
        box = QGroupBox(title)
        box.setStyleSheet(
            f"QGroupBox {{ background: {PALETTE['BG_SURFACE']};"
            f" border: 1px solid {PALETTE['BORDER']}; border-radius: 8px;"
            f" margin-top: 14px; padding: 12px 12px 8px 12px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px;"
            f" color: {PALETTE['TEXT_MUTED']}; font-size: 10px; font-weight: bold;"
            f" text-transform: uppercase; letter-spacing: 1px; }}"
        )
        lay = QVBoxLayout(box)
        lay.setSpacing(8)
        return box

    def _btn(self, text: str, color: str) -> QPushButton:
        b = QPushButton(text)
        b.setMinimumHeight(36)
        b.setStyleSheet(
            f"QPushButton {{ background: {color}20; color: {color};"
            f" border: 1px solid {color}50; border-radius: 6px;"
            f" padding: 6px 16px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {color}40; }}"
            f"QPushButton:pressed {{ background: {color}60; }}"
            f"QPushButton:disabled {{ color: {PALETTE['TEXT_MUTED']};"
            f" background: {PALETTE['BG_ELEVATED']};"
            f" border-color: {PALETTE['BORDER']}; }}"
        )
        return b

    def _set_state(self, state: _State) -> None:
        self._state = state
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        s = self._state
        label, color = _STATE_LABEL[s]
        self._dot.setStyleSheet(f"color: {color}; font-size: 16px;")
        self._s_lbl.setText(_STATUS_TEXT[s])
        self._s_lbl.setStyleSheet(f"color: {color}; font-size: 12px;")

        # Step highlights
        active = {
            _State.IDLE: -1, _State.CONNECTING: 0, _State.READY: 0,
            _State.MAPPING: 2, _State.SAVING: 3, _State.DONE: 3,
        }.get(s, -1)
        for i, lbl in enumerate(self._step_labels):
            if i < active:
                lbl.setStyleSheet(f"color: {PALETTE['SUCCESS']}; font-size: 12px;")
            elif i == active:
                lbl.setStyleSheet(
                    f"color: {PALETTE['ACCENT']}; font-size: 12px; font-weight: bold;"
                )
            else:
                lbl.setStyleSheet(f"color: {PALETTE['TEXT_MUTED']}; font-size: 12px;")

        # Button enables
        self._btn_start_map.setEnabled(s == _State.READY)
        self._btn_rviz.setEnabled(s in (_State.READY, _State.MAPPING, _State.DONE))
        self._btn_save.setEnabled(s == _State.MAPPING)
        self._btn_stop.setEnabled(s != _State.IDLE)

    def _append_log(self, text: str, color: str = "") -> None:
        c = color or PALETTE["TEXT_SEC"]
        self._log.append(f'<span style="color:{c};">{text}</span>')

    # ------------------------------------------------------------------
    # Button slots
    # ------------------------------------------------------------------

    @Slot()
    def _on_start_mapping(self) -> None:
        self._append_log("Starting SLAM mapping (indoor)…", PALETTE["ACCENT"])
        # Auto-open RViz2 before starting mapping
        if not self._rm.open(RVizConfig.MAPPING):
            self._append_log(
                "Could not open RViz2 — check .rviz config path in Settings.",
                PALETTE["WARNING"],
            )
        self._slam.start_mapping()
        self._set_state(_State.MAPPING)

    @Slot()
    def _on_open_rviz(self) -> None:
        if not self._rm.open(RVizConfig.MAPPING):
            self._append_log(
                "Could not open RViz2 — check .rviz config path in Settings.",
                PALETTE["WARNING"],
            )

    @Slot()
    def _on_save_map(self) -> None:
        self._append_log("Saving map to /home/unitree/test.pcd on robot…", PALETTE["WARNING"])
        self._slam.end_mapping()
        self._set_state(_State.SAVING)

    @Slot()
    def _on_stop(self) -> None:
        self._append_log("Stopping bridge…", PALETTE["DANGER"])
        self._slam.disconnect()

    # ------------------------------------------------------------------
    # SlamService signal slots
    # ------------------------------------------------------------------

    @Slot()
    def _on_bridge_ready(self) -> None:
        self._set_state(_State.READY)
        self._append_log(
            "Bridge ready — SDK DDS initialized. Click 'Start Mapping' to begin.",
            PALETTE["SUCCESS"],
        )

    @Slot()
    def _on_bridge_stopped(self) -> None:
        if self._state != _State.IDLE:
            self._set_state(_State.IDLE)
        self._append_log("Bridge stopped.", PALETTE["TEXT_MUTED"])

    @Slot(str)
    def _on_bridge_error(self, message: str) -> None:
        self._set_state(_State.IDLE)
        self._append_log(f"Bridge error: {message}", PALETTE["DANGER"])

    @Slot(str, str)
    def _on_status(self, message: str, level: str) -> None:
        color_map = {
            "ok": PALETTE["SUCCESS"], "warn": PALETTE["WARNING"],
            "error": PALETTE["DANGER"], "info": PALETTE["TEXT_SEC"],
        }
        self._append_log(message, color_map.get(level, PALETTE["TEXT_SEC"]))

    @Slot(float, float, float, float, float, float, float)
    def _on_pose(self, x, y, z, qx, qy, qz, qw) -> None:
        for k, v in [("x", x), ("y", y), ("z", z),
                     ("q_x", qx), ("q_y", qy), ("q_z", qz), ("q_w", qw)]:
            self._pose_vals[k].setText(f"{v:.4f}")

    @Slot(str, bool, str)
    def _on_api_result(self, cmd: str, succeed: bool, info: str) -> None:
        color = PALETTE["SUCCESS"] if succeed else PALETTE["DANGER"]
        self._append_log(
            f"[{cmd}] {'OK' if succeed else 'FAIL'}: {info}", color
        )
        if cmd == "end_mapping" and succeed and self._state == _State.SAVING:
            self._set_state(_State.DONE)

    @Slot(str)
    def _on_raw_log(self, line: str) -> None:
        self._append_log(line, PALETTE["TEXT_MUTED"])
