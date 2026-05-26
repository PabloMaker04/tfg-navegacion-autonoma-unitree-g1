"""
Navigation page — Phase 8.
Locked until localization is active; unlocks automatically via SlamService signal.
"""
from __future__ import annotations

from enum import Enum, auto
from typing import List

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QPushButton, QSizePolicy, QStackedWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from config.app_config import AppConfig
from core.rviz_manager import RVizManager, RVizConfig
from services.slam_service import SlamService
from ui.pages.base_page import BasePage
from ui.styles.theme import PALETTE


class _State(Enum):
    READY      = auto()
    NAVIGATING = auto()
    PAUSED     = auto()
    DONE       = auto()


_STATE_LABEL: dict[_State, tuple[str, str]] = {
    _State.READY:      ("READY",      PALETTE["SUCCESS"]),
    _State.NAVIGATING: ("NAVIGATING", PALETTE["ACCENT"]),
    _State.PAUSED:     ("PAUSED",     PALETTE["WARNING"]),
    _State.DONE:       ("DONE",       PALETTE["SUCCESS"]),
}

_STATUS_TEXT: dict[_State, str] = {
    _State.READY:      "Ready — add waypoints from the robot's current pose and execute",
    _State.NAVIGATING: "Navigating — robot moving between waypoints",
    _State.PAUSED:     "Paused — navigation suspended",
    _State.DONE:       "Navigation loop finished — ready for next run",
}


class NavigationPage(BasePage):
    PAGE_KEY = "navigation"
    PAGE_TITLE = "Navigation"
    PAGE_DESCRIPTION = (
        "Waypoint-based autonomous navigation. Requires active localization. "
        "The robot navigates the waypoint list and reverses direction at the end."
    )

    navigate_to = Signal(str)   # "Go to Localization" button on lock screen

    def __init__(
        self,
        config: AppConfig,
        rviz_manager: RVizManager,
        slam_service: SlamService,
        parent=None,
    ) -> None:
        self._config    = config
        self._rm        = rviz_manager
        self._slam      = slam_service
        self._state     = _State.READY
        self._waypoints: List[dict] = []
        self._cur_wp    = -1
        super().__init__(parent)
        self._build_content()
        self._connect_signals()
        # Start locked unless localization is already active
        self._set_locked(not self._slam.is_localization_active)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_content(self) -> None:
        self._stack = QStackedWidget()
        self._content_layout.addWidget(self._stack)

        self._stack.addWidget(self._build_lock_view())   # index 0 — locked
        self._stack.addWidget(self._build_nav_view())    # index 1 — active

    # ── Lock view ──────────────────────────────────────────────────────

    def _build_lock_view(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setFixedWidth(460)
        card.setStyleSheet(
            f"QFrame {{ background: {PALETTE['BG_SURFACE']};"
            f" border: 1px solid {PALETTE['BORDER']}; border-radius: 12px; }}"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(36, 32, 36, 32)
        cl.setSpacing(14)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("⊘")
        icon.setStyleSheet(f"color: {PALETTE['WARNING']}; font-size: 52px; border: none;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(icon)

        title = QLabel("Localization Required")
        title.setStyleSheet(
            f"color: {PALETTE['TEXT_PRIMARY']}; font-size: 18px;"
            f" font-weight: bold; border: none;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(title)

        desc = QLabel(
            "Run the Localization workflow first to establish the robot's "
            "position on the map.\n\n"
            "Once relocation starts, this page unlocks automatically."
        )
        desc.setStyleSheet(
            f"color: {PALETTE['TEXT_SEC']}; font-size: 12px; border: none;"
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(desc)

        btn = QPushButton("Go to Localization")
        btn.setMinimumHeight(40)
        btn.setStyleSheet(
            f"QPushButton {{ background: {PALETTE['ACCENT']}20;"
            f" color: {PALETTE['ACCENT']}; border: 1px solid {PALETTE['ACCENT']}50;"
            f" border-radius: 6px; padding: 8px 24px;"
            f" font-weight: bold; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {PALETTE['ACCENT']}40; }}"
        )
        btn.clicked.connect(lambda: self.navigate_to.emit("localization"))
        cl.addWidget(btn)

        outer.addWidget(card)
        return w

    # ── Active navigation view ─────────────────────────────────────────

    def _build_nav_view(self) -> QWidget:
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # Top: status + pose
        top = QHBoxLayout()
        top.setSpacing(16)
        self._build_status_row(top)
        self._build_pose_card(top)
        root.addLayout(top)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {PALETTE['BORDER']}; max-height: 1px; margin: 2px 0;")
        root.addWidget(sep)

        # Bottom: waypoints + controls + log
        bottom = QHBoxLayout()
        bottom.setSpacing(16)
        self._build_waypoints(bottom)
        self._build_controls(bottom)
        self._build_log(bottom)
        root.addLayout(bottom, 1)

        return w

    def _build_status_row(self, parent: QHBoxLayout) -> None:
        sc = self._card("Status")
        row = QHBoxLayout()
        row.setSpacing(8)
        self._dot   = QLabel("●")
        self._dot.setFixedWidth(18)
        self._s_lbl = QLabel()
        row.addWidget(self._dot)
        row.addWidget(self._s_lbl, 1)
        sc.layout().addLayout(row)
        self._cur_wp_lbl = QLabel("Current waypoint: —")
        self._cur_wp_lbl.setStyleSheet(
            f"color: {PALETTE['TEXT_MUTED']}; font-size: 11px;"
        )
        sc.layout().addWidget(self._cur_wp_lbl)
        parent.addWidget(sc, 2)

    def _build_pose_card(self, parent: QHBoxLayout) -> None:
        pc = self._card("Current Robot Pose")
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(5)
        self._pose_vals: dict[str, QLabel] = {}
        for col, keys in enumerate([["x", "y", "z"], ["q_x", "q_y", "q_z", "q_w"]]):
            for row_i, k in enumerate(keys):
                lbl = QLabel(f"{k}:")
                lbl.setStyleSheet(f"color: {PALETTE['TEXT_MUTED']}; font-size: 11px;")
                val = QLabel("—")
                val.setStyleSheet(
                    f"color: {PALETTE['ACCENT']}; font-family: monospace; font-size: 12px;"
                )
                grid.addWidget(lbl, row_i, col * 2)
                grid.addWidget(val, row_i, col * 2 + 1)
                self._pose_vals[k] = val
        pc.layout().addLayout(grid)
        parent.addWidget(pc, 1)

    def _build_waypoints(self, parent: QHBoxLayout) -> None:
        wc = self._card("Waypoints")
        wc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["#", "x", "y", "z", "q_w"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().hide()
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            f"QTableWidget {{ background: {PALETTE['BG_BASE']};"
            f" color: {PALETTE['TEXT_PRIMARY']}; gridline-color: {PALETTE['BORDER']};"
            f" border: 1px solid {PALETTE['BORDER']}; border-radius: 4px; }}"
            f"QTableWidget::item:selected {{ background: {PALETTE['ACCENT']}30; }}"
            f"QHeaderView::section {{ background: {PALETTE['BG_ELEVATED']};"
            f" color: {PALETTE['TEXT_MUTED']}; border: none;"
            f" font-size: 10px; font-weight: bold; padding: 4px; }}"
            f"QTableWidget::item:alternate {{ background: {PALETTE['BG_SURFACE']}; }}"
        )
        wc.layout().addWidget(self._table, 1)

        self._wp_count_lbl = QLabel("0 waypoints")
        self._wp_count_lbl.setStyleSheet(
            f"color: {PALETTE['TEXT_MUTED']}; font-size: 11px;"
        )
        wc.layout().addWidget(self._wp_count_lbl)
        parent.addWidget(wc, 2)

    def _build_controls(self, parent: QHBoxLayout) -> None:
        cc = self._card("Controls")
        cc.setFixedWidth(200)
        cc.layout().setSpacing(10)

        self._btn_add_wp     = self._btn("Add Waypoint",    PALETTE["SUCCESS"])
        self._btn_clear_wps  = self._btn("Clear Waypoints", PALETTE["WARNING"])
        self._btn_rviz       = self._btn("Open RViz2",      PALETTE["ACCENT_MUTED"])
        self._btn_execute    = self._btn("Execute Tasks",   PALETTE["SUCCESS"])
        self._btn_pause      = self._btn("Pause",           PALETTE["WARNING"])
        self._btn_resume     = self._btn("Resume",          PALETTE["ACCENT"])
        self._btn_stop_nav   = self._btn("Stop Navigation", PALETTE["DANGER"])
        self._btn_disconnect = self._btn("Disconnect",      PALETTE["DANGER"])

        for b in [
            self._btn_add_wp, self._btn_clear_wps, self._btn_rviz,
            self._btn_execute, self._btn_pause, self._btn_resume,
            self._btn_stop_nav, self._btn_disconnect,
        ]:
            cc.layout().addWidget(b)

        self._btn_add_wp.clicked.connect(lambda: self._slam.add_current_pose())
        self._btn_clear_wps.clicked.connect(lambda: self._slam.clear_tasks())
        self._btn_rviz.clicked.connect(self._on_open_rviz)
        self._btn_execute.clicked.connect(lambda: self._slam.execute_tasks())
        self._btn_pause.clicked.connect(self._on_pause)
        self._btn_resume.clicked.connect(self._on_resume)
        self._btn_stop_nav.clicked.connect(self._on_stop_nav)
        self._btn_disconnect.clicked.connect(lambda: self._slam.disconnect())

        cc.layout().addStretch()
        parent.addWidget(cc)

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
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._slam.localization_active.connect(self._on_localization_active)
        self._slam.bridge_stopped.connect(lambda: self._set_locked(True))
        self._slam.status_received.connect(self._on_status)
        self._slam.pose_updated.connect(self._on_pose)
        self._slam.api_result.connect(self._on_api_result)
        self._slam.pose_added.connect(self._on_pose_added)
        self._slam.tasks_cleared.connect(self._on_tasks_cleared)
        self._slam.nav_started.connect(self._on_nav_started)
        self._slam.nav_targeting.connect(self._on_nav_targeting)
        self._slam.nav_stopped.connect(self._on_nav_stopped)
        self._slam.arrived.connect(self._on_arrived)
        self._slam.raw_log.connect(self._on_raw_log)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._set_locked(not self._slam.is_localization_active)

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
        b.setMinimumHeight(34)
        b.setStyleSheet(
            f"QPushButton {{ background: {color}20; color: {color};"
            f" border: 1px solid {color}50; border-radius: 6px;"
            f" padding: 5px 12px; font-weight: bold; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {color}40; }}"
            f"QPushButton:pressed {{ background: {color}60; }}"
            f"QPushButton:disabled {{ color: {PALETTE['TEXT_MUTED']};"
            f" background: {PALETTE['BG_ELEVATED']};"
            f" border-color: {PALETTE['BORDER']}; }}"
        )
        return b

    def _set_locked(self, locked: bool) -> None:
        self._stack.setCurrentIndex(0 if locked else 1)
        if not locked and self._state == _State.DONE:
            # Keep DONE state visible — don't reset just because we re-show the page
            pass

    def _set_state(self, state: _State) -> None:
        self._state = state
        self._refresh_nav_ui()

    def _refresh_nav_ui(self) -> None:
        s = self._state
        label, color = _STATE_LABEL[s]
        self._dot.setStyleSheet(f"color: {color}; font-size: 16px;")
        self._s_lbl.setText(_STATUS_TEXT[s])
        self._s_lbl.setStyleSheet(f"color: {color}; font-size: 12px;")

        navigating = s == _State.NAVIGATING
        paused     = s == _State.PAUSED
        ready      = s == _State.READY
        n          = len(self._waypoints)

        self._btn_add_wp.setEnabled(ready)
        self._btn_clear_wps.setEnabled(ready and n > 0)
        self._btn_rviz.setEnabled(True)
        self._btn_execute.setEnabled(ready and n > 0)
        self._btn_pause.setEnabled(navigating)
        self._btn_resume.setEnabled(paused)
        self._btn_stop_nav.setEnabled(navigating or paused)
        self._btn_disconnect.setEnabled(True)

    def _update_wp_count(self) -> None:
        n = len(self._waypoints)
        self._wp_count_lbl.setText(f"{n} waypoint{'s' if n != 1 else ''}")

    def _highlight_row(self, index: int) -> None:
        from PySide6.QtGui import QColor
        for row in range(self._table.rowCount()):
            for col in range(self._table.columnCount()):
                item = self._table.item(row, col)
                if item is None:
                    continue
                if row == index:
                    item.setBackground(QColor(PALETTE["ACCENT"] + "30"))
                    item.setForeground(QColor(PALETTE["ACCENT"]))
                else:
                    item.setBackground(QColor(0, 0, 0, 0))
                    item.setForeground(QColor(PALETTE["TEXT_PRIMARY"]))

    def _append_log(self, text: str, color: str = "") -> None:
        c = color or PALETTE["TEXT_SEC"]
        self._log.append(f'<span style="color:{c};">{text}</span>')

    # ------------------------------------------------------------------
    # Button slots
    # ------------------------------------------------------------------

    @Slot()
    def _on_open_rviz(self) -> None:
        if not self._rm.open(RVizConfig.NAVIGATION):
            self._append_log(
                "Could not open RViz2 — check .rviz config path in Settings.",
                PALETTE["WARNING"],
            )

    @Slot()
    def _on_pause(self) -> None:
        self._slam.pause_nav()
        self._set_state(_State.PAUSED)
        self._append_log("Navigation paused.", PALETTE["WARNING"])

    @Slot()
    def _on_resume(self) -> None:
        self._slam.resume_nav()
        self._set_state(_State.NAVIGATING)
        self._append_log("Navigation resumed.", PALETTE["ACCENT"])

    @Slot()
    def _on_stop_nav(self) -> None:
        self._slam.stop()
        self._set_state(_State.READY)
        self._append_log("Navigation stopped.", PALETTE["DANGER"])

    # ------------------------------------------------------------------
    # SlamService signal slots
    # ------------------------------------------------------------------

    @Slot(bool)
    def _on_localization_active(self, active: bool) -> None:
        self._set_locked(not active)
        if active:
            self._set_state(_State.READY)
            self._append_log("Localization active — navigation unlocked.", PALETTE["SUCCESS"])
        else:
            self._waypoints.clear()
            self._table.setRowCount(0)
            self._cur_wp = -1
            self._cur_wp_lbl.setText("Current waypoint: —")
            self._update_wp_count()
            self._append_log("Localization lost — navigation locked.", PALETTE["WARNING"])

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
        self._append_log(f"[{cmd}] {'OK' if succeed else 'FAIL'}: {info}", color)

    @Slot(dict, int)
    def _on_pose_added(self, pose: dict, count: int) -> None:
        idx = count - 1
        self._waypoints.append(pose)
        self._table.insertRow(idx)
        for col, (key, fmt) in enumerate([
            (None, None), ("x", ".3f"), ("y", ".3f"), ("z", ".3f"), ("q_w", ".4f"),
        ]):
            text = str(idx + 1) if col == 0 else format(pose.get(key, 0.0), fmt)
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(idx, col, item)
        self._update_wp_count()
        self._refresh_nav_ui()
        self._append_log(
            f"Waypoint {count} — x={pose.get('x', 0):.3f} y={pose.get('y', 0):.3f}",
            PALETTE["SUCCESS"],
        )

    @Slot()
    def _on_tasks_cleared(self) -> None:
        self._waypoints.clear()
        self._table.setRowCount(0)
        self._cur_wp = -1
        self._cur_wp_lbl.setText("Current waypoint: —")
        self._update_wp_count()
        self._refresh_nav_ui()
        self._append_log("Waypoints cleared.", PALETTE["WARNING"])

    @Slot(int)
    def _on_nav_started(self, count: int) -> None:
        self._set_state(_State.NAVIGATING)
        self._append_log(f"Navigation started — {count} waypoint(s).", PALETTE["ACCENT"])

    @Slot(int, dict)
    def _on_nav_targeting(self, index: int, pose: dict) -> None:
        self._cur_wp = index
        self._cur_wp_lbl.setText(
            f"Waypoint {index + 1}  (x={pose.get('x', 0):.3f} y={pose.get('y', 0):.3f})"
        )
        self._highlight_row(index)
        self._append_log(f"Targeting waypoint {index + 1}…", PALETTE["ACCENT"])

    @Slot()
    def _on_nav_stopped(self) -> None:
        self._set_state(_State.DONE)
        self._cur_wp = -1
        self._cur_wp_lbl.setText("Current waypoint: —")
        self._append_log("Navigation loop finished.", PALETTE["SUCCESS"])

    @Slot(bool, str)
    def _on_arrived(self, is_arrived: bool, node_name: str) -> None:
        if is_arrived:
            label = f"Arrived at '{node_name}'" if node_name else "Arrived at waypoint"
            self._append_log(label, PALETTE["SUCCESS"])

    @Slot(str)
    def _on_raw_log(self, line: str) -> None:
        self._append_log(line, PALETTE["TEXT_MUTED"])
