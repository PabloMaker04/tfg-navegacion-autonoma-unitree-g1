from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QGroupBox, QFileDialog, QScrollArea,
    QFrame, QCheckBox, QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from config.app_config import AppConfig
from ui.pages.base_page import BasePage
from ui.styles.theme import PALETTE


class _FieldRow(QWidget):
    """Label + input + optional browse button in a horizontal row."""

    def __init__(
        self,
        label: str,
        placeholder: str = "",
        browse_dir: bool = False,
        browse_file: bool = False,
        read_only: bool = False,
        tooltip: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._browse_dir = browse_dir
        self._browse_file = browse_file
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        lbl = QLabel(label)
        lbl.setFixedWidth(220)
        lbl.setStyleSheet(f"color: {PALETTE['TEXT_SEC']}; font-size: 13px;")
        layout.addWidget(lbl)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText(placeholder)
        self._edit.setReadOnly(read_only)
        if tooltip:
            self._edit.setToolTip(tooltip)
        layout.addWidget(self._edit, 1)

        if browse_dir or browse_file:
            browse_btn = QPushButton("Browse…")
            browse_btn.setProperty("class", "ghost")
            browse_btn.setFixedWidth(80)
            browse_btn.clicked.connect(self._browse)
            layout.addWidget(browse_btn)

    def _browse(self) -> None:
        if self._browse_dir:
            path = QFileDialog.getExistingDirectory(self, "Select Directory", self._edit.text())
            if path:
                self._edit.setText(path)
        elif self._browse_file:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select File", self._edit.text(), "All Files (*)"
            )
            if path:
                self._edit.setText(path)

    @property
    def value(self) -> str:
        return self._edit.text().strip()

    @value.setter
    def value(self, v: str) -> None:
        self._edit.setText(v)


class _SpinRow(QWidget):
    def __init__(self, label: str, minimum: int, maximum: int, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        lbl = QLabel(label)
        lbl.setFixedWidth(220)
        lbl.setStyleSheet(f"color: {PALETTE['TEXT_SEC']}; font-size: 13px;")
        layout.addWidget(lbl)

        self._spin = QSpinBox()
        self._spin.setMinimum(minimum)
        self._spin.setMaximum(maximum)
        self._spin.setFixedWidth(120)
        layout.addWidget(self._spin)
        layout.addStretch()

    @property
    def value(self) -> int:
        return self._spin.value()

    @value.setter
    def value(self, v: int) -> None:
        self._spin.setValue(v)


def _note(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color: {PALETTE['TEXT_MUTED']}; font-size: 12px; "
        f"padding: 4px 0 0 0; line-height: 1.5;"
    )
    return lbl


def _warn(text: str) -> QLabel:
    lbl = QLabel(f"⚠  {text}")
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color: {PALETTE['WARNING']}; font-size: 12px; padding: 4px 0 0 0;"
    )
    return lbl


class SettingsPage(BasePage):
    PAGE_KEY = "settings"
    PAGE_TITLE = "Settings"
    PAGE_DESCRIPTION = (
        "Configure the robot connection, SDK paths, RViz2 environment, and UI preferences. "
        "Saved to ~/.config/g1_control_studio/settings.json"
    )

    settings_saved = Signal()

    def __init__(self, config: AppConfig, parent=None) -> None:
        self._config = config
        super().__init__(parent)
        self._populate()
        self._load_from_config()

    # ------------------------------------------------------------------
    # Header actions
    # ------------------------------------------------------------------

    def _build_header_actions(self, header_layout: QHBoxLayout) -> None:
        save_btn = QPushButton("Save Settings")
        save_btn.setProperty("class", "primary")
        save_btn.setMinimumHeight(36)
        save_btn.clicked.connect(self._save)
        header_layout.addWidget(save_btn)

        reset_btn = QPushButton("Reset Defaults")
        reset_btn.setProperty("class", "ghost")
        reset_btn.setMinimumHeight(36)
        reset_btn.clicked.connect(self._reset_defaults)
        header_layout.addWidget(reset_btn)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _populate(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(20)
        inner_layout.setContentsMargins(0, 0, 24, 0)

        inner_layout.addWidget(self._build_network_group())
        inner_layout.addWidget(self._build_slam_group())
        inner_layout.addWidget(self._build_ros_group())
        inner_layout.addWidget(self._build_rviz_group())
        inner_layout.addWidget(self._build_ui_group())
        inner_layout.addStretch()

        scroll.setWidget(inner)
        self._content_layout.addWidget(scroll)

    # ── Network / Robot connection ─────────────────────────────────────
    def _build_network_group(self) -> QGroupBox:
        group = QGroupBox("Robot Network Connection")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self._f_iface = _FieldRow(
            "Ethernet Interface",
            "e.g. enp2s0",
            tooltip="Network interface connecting this PC to the robot switch.",
        )
        self._f_pc_ip = _FieldRow(
            "PC IP (robot subnet)",
            "192.168.123.100",
            tooltip="IP to assign to this PC on the 192.168.123.x subnet.",
        )

        layout.addWidget(self._f_iface)
        layout.addWidget(self._f_pc_ip)

        layout.addWidget(_note(
            "Robot components:  "
            "PC1 (slam_operate) → 192.168.123.161  |  "
            "Jetson NX → 192.168.123.164  |  "
            "LiDAR Mid360 → 192.168.123.120\n"
            "Assign the PC IP with:  sudo ip addr add 192.168.123.100/24 dev enp2s0"
        ))
        return group

    # ── SLAM / keyDemo ─────────────────────────────────────────────────
    def _build_slam_group(self) -> QGroupBox:
        group = QGroupBox("SLAM — keyDemo Binary")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self._f_keydemo = _FieldRow(
            "keyDemo binary path",
            "~/Practicas/.../build/keyDemo",
            browse_file=True,
            tooltip="Full path to the compiled C++ keyDemo executable.",
        )
        self._f_ld_path = _FieldRow(
            "LD_LIBRARY_PATH prefix",
            "/usr/local/lib",
            tooltip=(
                "Prepended to LD_LIBRARY_PATH when launching keyDemo.\n"
                "Must contain the SDK's CycloneDDS to prevent conflict with ROS2's version."
            ),
        )

        layout.addWidget(self._f_keydemo)
        layout.addWidget(self._f_ld_path)
        layout.addWidget(_warn(
            "keyDemo MUST be launched without ROS2 sourced. "
            "The UI handles this automatically — these two processes must always "
            "run in separate environments."
        ))
        return group

    # ── ROS2 / CycloneDDS ─────────────────────────────────────────────
    def _build_ros_group(self) -> QGroupBox:
        group = QGroupBox("ROS2 & CycloneDDS Environment (for RViz2)")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        ros_distro_env = os.environ.get("ROS_DISTRO", "")

        self._f_ros_distro = _FieldRow(
            "ROS2 Distribution",
            "e.g. humble, jazzy",
            read_only=bool(ros_distro_env),
            tooltip="Used to locate /opt/ros/<distro>/setup.bash if no workspace is set.",
        )
        if ros_distro_env:
            ok_lbl = QLabel(f"Auto-detected: ROS_DISTRO={ros_distro_env}")
            ok_lbl.setStyleSheet(f"color: {PALETTE['SUCCESS']}; font-size: 12px;")
            layout.addWidget(ok_lbl)

        self._f_ros_setup = _FieldRow(
            "setup.bash / workspace",
            "/opt/ros/humble/setup.bash  or  install/setup.bash",
            browse_file=True,
            tooltip=(
                "Sourced before launching RViz2. "
                "Workspace install/setup.bash takes priority. "
                "Falls back to /opt/ros/<distro>/setup.bash."
            ),
        )
        self._f_cyclone_iface = _FieldRow(
            "CycloneDDS Interface",
            "e.g. enp2s0",
            tooltip=(
                "Interface name used inside CYCLONEDDS_URI. "
                "Usually the same as the Ethernet Interface above. "
                "Without this, RViz2 may use WiFi and see no robot topics."
            ),
        )

        # Live preview of the CYCLONEDDS_URI that will be generated
        self._cyclone_preview = QLabel()
        self._cyclone_preview.setWordWrap(True)
        self._cyclone_preview.setStyleSheet(
            f"color: {PALETTE['TEXT_SEC']}; font-size: 11px; "
            f"font-family: monospace; padding: 6px 8px; "
            f"background: {PALETTE['BG_SURFACE']}; border-radius: 4px;"
        )
        self._f_cyclone_iface._edit.textChanged.connect(self._update_cyclone_preview)

        layout.addWidget(self._f_ros_distro)
        layout.addWidget(self._f_ros_setup)
        layout.addWidget(self._f_cyclone_iface)
        layout.addWidget(self._cyclone_preview)
        layout.addWidget(_note(
            "RViz2 is launched as:  "
            "bash -c 'source <setup.bash> && export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp "
            "&& export CYCLONEDDS_URI=<...> && rviz2 -d <config>'"
        ))
        return group

    # ── RViz configs ───────────────────────────────────────────────────
    def _build_rviz_group(self) -> QGroupBox:
        group = QGroupBox("RViz2 Configuration Files (.rviz)")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self._f_rviz_mapping = _FieldRow(
            "Mapping config",
            "Path to mapping.rviz",
            browse_file=True,
        )
        self._f_rviz_reloc = _FieldRow(
            "Relocation config",
            "Path to relocation.rviz",
            browse_file=True,
        )
        self._f_rviz_nav = _FieldRow(
            "Navigation config",
            "Defaults to relocation.rviz if empty",
            browse_file=True,
        )
        self._f_rviz_debug = _FieldRow(
            "Debug config",
            "Optional",
            browse_file=True,
        )

        layout.addWidget(self._f_rviz_mapping)
        layout.addWidget(self._f_rviz_reloc)
        layout.addWidget(self._f_rviz_nav)
        layout.addWidget(self._f_rviz_debug)
        layout.addWidget(_note(
            "The mapping.rviz and relocation.rviz files from the SDK are pre-configured. "
            "They are already detected in the project."
        ))
        return group

    # ── UI ─────────────────────────────────────────────────────────────
    def _build_ui_group(self) -> QGroupBox:
        group = QGroupBox("User Interface")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self._f_log_lines = _SpinRow("Max log lines", 100, 10000)
        self._cb_echo = QCheckBox("Show executed command in log output")
        self._cb_echo.setStyleSheet(f"color: {PALETTE['TEXT_PRIMARY']};")

        layout.addWidget(self._f_log_lines)
        layout.addWidget(self._cb_echo)
        return group

    # ------------------------------------------------------------------
    # Live previews
    # ------------------------------------------------------------------

    def _update_cyclone_preview(self, iface: str) -> None:
        iface = iface.strip() or "enp2s0"
        uri = (
            f'<CycloneDDS><Domain><General><Interfaces>'
            f'<NetworkInterface name="{iface}" priority="default" multicast="default" />'
            f'</Interfaces></General></Domain></CycloneDDS>'
        )
        self._cyclone_preview.setText(f"CYCLONEDDS_URI → {uri}")

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def _load_from_config(self) -> None:
        c = self._config

        self._f_iface.value = c.network.network_interface
        self._f_pc_ip.value = c.network.pc_ip

        self._f_keydemo.value = c.slam.binary
        self._f_ld_path.value = c.slam.ld_library_path

        if not os.environ.get("ROS_DISTRO"):
            self._f_ros_distro.value = c.ros.distro
        self._f_ros_setup.value = c.ros_setup_path
        self._f_cyclone_iface.value = c.ros.cyclone_interface
        self._update_cyclone_preview(c.ros.cyclone_interface)

        self._f_rviz_mapping.value = c.rviz.mapping_config
        self._f_rviz_reloc.value = c.rviz.relocation_config
        self._f_rviz_nav.value = c.rviz.navigation_config
        self._f_rviz_debug.value = c.rviz.debug_config

        self._f_log_lines.value = c.ui.log_max_lines
        self._cb_echo.setChecked(c.ui.show_command_echo)

    def _save(self) -> None:
        c = self._config

        c.network.network_interface = self._f_iface.value or "enp2s0"
        c.network.pc_ip = self._f_pc_ip.value

        c.slam.binary = self._f_keydemo.value
        c.slam.ld_library_path = self._f_ld_path.value or "/usr/local/lib"

        if not os.environ.get("ROS_DISTRO"):
            c.ros.distro = self._f_ros_distro.value
        # If user set an explicit workspace, use that; otherwise store the path they typed
        entered_setup = self._f_ros_setup.value
        if entered_setup and Path(entered_setup).exists():
            c.ros.workspace_setup = entered_setup
        c.ros.cyclone_interface = self._f_cyclone_iface.value or c.network.network_interface

        c.rviz.mapping_config = self._f_rviz_mapping.value
        c.rviz.relocation_config = self._f_rviz_reloc.value
        nav_val = self._f_rviz_nav.value
        c.rviz.navigation_config = nav_val or c.rviz.relocation_config
        c.rviz.debug_config = self._f_rviz_debug.value

        c.ui.log_max_lines = self._f_log_lines.value
        c.ui.show_command_echo = self._cb_echo.isChecked()

        c.save()
        self.settings_saved.emit()

        msg = QMessageBox(self)
        msg.setWindowTitle("Settings Saved")
        msg.setText("Settings saved successfully.")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()

    def _reset_defaults(self) -> None:
        reply = QMessageBox.question(
            self,
            "Reset Defaults",
            "Reset all settings to their default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            fresh = AppConfig()
            self._config.__dict__.update(fresh.__dict__)
            self._load_from_config()
