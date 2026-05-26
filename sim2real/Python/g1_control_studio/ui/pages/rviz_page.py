from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QMessageBox,
)
from PySide6.QtCore import Qt, Slot, Signal

from config.app_config import AppConfig
from core.rviz_manager import RVizManager, RVizConfig
from ui.pages.base_page import BasePage
from ui.components.status_badge import StatusBadge
from ui.components.log_widget import LogWidget
from ui.styles.theme import PALETTE


class RVizPage(BasePage):
    PAGE_KEY = "rviz"
    PAGE_TITLE = "RViz2"
    PAGE_DESCRIPTION = (
        "Launch and manage RViz2 visualization instances. "
        "Each configuration is linked to a specific workflow."
    )

    def __init__(self, config: AppConfig, rviz_manager: RVizManager, parent=None) -> None:
        self._config = config
        self._rm = rviz_manager
        super().__init__(parent)
        self._entries: dict[str, _RVizEntry] = {}
        self._populate()
        self._connect_signals()
        self._sync_config_paths()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _populate(self) -> None:
        main_row = QHBoxLayout()
        main_row.setSpacing(20)

        # Left: config list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        hdr = QLabel("CONFIGURATIONS")
        hdr.setObjectName("section-header")
        left_layout.addWidget(hdr)

        configs = [
            (RVizConfig.MAPPING,    "Mapping",      "◈", "For SLAM mapping — shows point cloud build-up"),
            (RVizConfig.RELOCATION, "Localization",  "◎", "For relocation — shows localized point cloud"),
            (RVizConfig.NAVIGATION, "Navigation",    "▶", "For navigation — shows robot pose and path"),
            (RVizConfig.DEBUG,      "Debug",         "⬡", "General debug view (optional config)"),
        ]

        for key, label, icon, desc in configs:
            entry = _RVizEntry(key, label, icon, desc, self._rm)
            entry.launch_requested.connect(lambda k=key: self._launch(k))
            entry.close_requested.connect(lambda k=key: self._close(k))
            left_layout.addWidget(entry)
            self._entries[key] = entry

        left_layout.addStretch()
        main_row.addWidget(left, 3)

        # Right: log output
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        self._log = LogWidget("RViz2 OUTPUT")
        right_layout.addWidget(self._log)
        main_row.addWidget(right, 2)

        wrapper = QWidget()
        wrapper.setLayout(main_row)
        self._content_layout.addWidget(wrapper)

    def _connect_signals(self) -> None:
        self._rm.rviz_started.connect(self._on_started)
        self._rm.rviz_stopped.connect(self._on_stopped)
        self._rm.rviz_error.connect(self._on_error)
        self._rm.rviz_not_found.connect(self._on_not_found)

        self._rm._pm.stdout_line.connect(self._on_proc_output)
        self._rm._pm.stderr_line.connect(self._on_proc_output)

    def _sync_config_paths(self) -> None:
        self._rm.set_config_path(RVizConfig.MAPPING,    self._config.rviz.mapping_config)
        self._rm.set_config_path(RVizConfig.RELOCATION, self._config.rviz.relocation_config)
        self._rm.set_config_path(RVizConfig.NAVIGATION, self._config.rviz.navigation_config)
        self._rm.set_config_path(RVizConfig.DEBUG,      self._config.rviz.debug_config)
        for key, entry in self._entries.items():
            entry.set_path(self._rm.config_path(key))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _launch(self, key: str) -> None:
        self._sync_config_paths()

        if not self._rm.config_exists(key) and key != RVizConfig.DEBUG:
            path = self._rm.config_path(key)
            QMessageBox.warning(
                self, "Config Not Found",
                f"RViz2 configuration file not found:\n{path or '(not set)'}\n\n"
                "Please update the path in Settings.",
            )
            return

        ros_env = self._rm._ros_env
        self._log.append("SYSTEM", f"Launching RViz2 [{RVizConfig.LABELS[key]}]")
        self._log.append("INFO",   f"  Setup:  {ros_env._ros_setup or '(not set)'}")
        self._log.append("INFO",   f"  DDS IF: {ros_env._interface}")
        self._log.append("INFO",   f"  RMW:    rmw_cyclonedds_cpp")

        if self._rm.open(key):
            pass  # success is confirmed via rviz_started signal

    def _close(self, key: str) -> None:
        self._rm.close(key)
        self._log.append("SYSTEM", f"Closing RViz2 [{RVizConfig.LABELS[key]}]")

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    @Slot(str)
    def _on_started(self, key: str) -> None:
        entry = self._entries.get(key)
        if entry:
            entry.set_running(True)
        self._log.append("OK", f"RViz2 [{RVizConfig.LABELS.get(key, key)}] started.")

    @Slot(str)
    def _on_stopped(self, key: str) -> None:
        entry = self._entries.get(key)
        if entry:
            entry.set_running(False)
        self._log.append("WARN", f"RViz2 [{RVizConfig.LABELS.get(key, key)}] stopped.")

    @Slot(str, str)
    def _on_error(self, key: str, message: str) -> None:
        entry = self._entries.get(key)
        if entry:
            entry.set_running(False)
        self._log.append("ERROR", f"[{RVizConfig.LABELS.get(key, key)}] {message}")

    @Slot()
    def _on_not_found(self) -> None:
        self._log.append("ERROR", "rviz2 binary not found in PATH. Is ROS2 sourced?")

    @Slot(str, str)
    def _on_proc_output(self, key: str, line: str) -> None:
        if key in RVizConfig.LABELS:
            self._log.append_line(line)


class _RVizEntry(QWidget):
    """One row showing a RViz config with its status, path, and controls."""

    launch_requested = Signal()
    close_requested = Signal()

    def __init__(
        self,
        key: str,
        label: str,
        icon: str,
        description: str,
        rm: RVizManager,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._key = key
        self._rm = rm
        self._build_ui(icon, label, description)

    def _build_ui(self, icon: str, label: str, description: str) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Icon
        icon_lbl = QLabel(icon)
        icon_lbl.setFixedWidth(28)
        icon_lbl.setStyleSheet(f"color: {PALETTE['ACCENT']}; font-size: 18px;")
        layout.addWidget(icon_lbl)

        # Info
        info = QVBoxLayout()
        info.setSpacing(2)

        name_lbl = QLabel(label)
        name_lbl.setStyleSheet(
            f"color: {PALETTE['TEXT_PRIMARY']}; font-size: 14px; font-weight: 600;"
        )
        info.addWidget(name_lbl)

        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet(f"color: {PALETTE['TEXT_SEC']}; font-size: 12px;")
        info.addWidget(desc_lbl)

        self._path_lbl = QLabel("—")
        self._path_lbl.setStyleSheet(
            f"color: {PALETTE['TEXT_MUTED']}; font-size: 11px; font-family: monospace;"
        )
        info.addWidget(self._path_lbl)

        layout.addLayout(info, 1)

        # Status badge
        self._badge = StatusBadge("Closed", "inactive")
        layout.addWidget(self._badge)

        # Buttons
        self._open_btn = QPushButton("Open RViz2")
        self._open_btn.setProperty("class", "primary")
        self._open_btn.setFixedWidth(110)
        self._open_btn.clicked.connect(self.launch_requested)
        layout.addWidget(self._open_btn)

        self._close_btn = QPushButton("Close")
        self._close_btn.setProperty("class", "danger")
        self._close_btn.setFixedWidth(80)
        self._close_btn.setEnabled(False)
        self._close_btn.clicked.connect(self.close_requested)
        layout.addWidget(self._close_btn)

    def set_path(self, path: str) -> None:
        if path:
            p = Path(path)
            self._path_lbl.setText(str(p))
            exists = p.exists()
            self._path_lbl.setStyleSheet(
                f"color: {PALETTE['SUCCESS'] if exists else PALETTE['DANGER']};"
                f" font-size: 11px; font-family: monospace;"
            )
        else:
            self._path_lbl.setText("Not configured")

    def set_running(self, running: bool) -> None:
        if running:
            self._badge.set_state("running", "Open")
            self._open_btn.setEnabled(False)
            self._close_btn.setEnabled(True)
        else:
            self._badge.set_state("inactive", "Closed")
            self._open_btn.setEnabled(True)
            self._close_btn.setEnabled(False)
