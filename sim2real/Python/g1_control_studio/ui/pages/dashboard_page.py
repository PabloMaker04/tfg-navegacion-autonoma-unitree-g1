from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QGridLayout, QWidget, QFrame, QScrollArea, QMessageBox,
    QDialog, QLineEdit, QDialogButtonBox,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot

from utils.validators import get_interface_status, ping_host, InterfaceStatus

from config.app_config import AppConfig
from core.process_manager import ProcessManager
from core.rviz_manager import RVizManager
from services.slam_service import SlamService
from ui.pages.base_page import BasePage
from ui.components.metric_card import MetricCard
from ui.components.status_badge import StatusBadge
from ui.styles.theme import PALETTE


@dataclass
class _HistoryEntry:
    name: str
    started_at: Optional[datetime]
    stopped_at: datetime
    exit_code: Optional[int]

    def duration_str(self) -> str:
        if self.started_at:
            secs = int((self.stopped_at - self.started_at).total_seconds())
            return f"{secs // 60:02d}:{secs % 60:02d}"
        return "—"

    def start_str(self) -> str:
        if self.started_at:
            return self.started_at.strftime("%H:%M:%S")
        return "—"

    def stop_str(self) -> str:
        return self.stopped_at.strftime("%H:%M:%S")


class DashboardPage(BasePage):
    PAGE_KEY = "dashboard"
    PAGE_TITLE = "Dashboard"
    PAGE_DESCRIPTION = "System overview and quick actions."

    # Emitted when user clicks a quick-action button
    navigate_to = Signal(str)

    def __init__(
        self,
        config: AppConfig,
        process_manager: ProcessManager,
        rviz_manager: RVizManager,
        slam_service: SlamService,
        parent=None,
    ) -> None:
        self._config = config
        self._pm = process_manager
        self._rviz = rviz_manager
        self._slam = slam_service
        self._history: List[_HistoryEntry] = []
        self._slam_started_at: Optional[datetime] = None
        super().__init__(parent)
        self._connect_history_signals()
        self._populate()
        self._start_refresh_timer()

    def _connect_history_signals(self) -> None:
        self._pm.process_stopped.connect(self._on_pm_stopped)
        self._slam.bridge_ready.connect(self._on_bridge_ready_for_history)
        self._slam.bridge_stopped.connect(self._on_bridge_stopped_for_history)

    @Slot(str, int)
    def _on_pm_stopped(self, key: str, exit_code: int) -> None:
        info = self._pm.get_info(key)
        entry = _HistoryEntry(
            name=key.replace("_", " ").title(),
            started_at=info.started_at if info else None,
            stopped_at=datetime.now(),
            exit_code=exit_code,
        )
        self._history.insert(0, entry)
        if len(self._history) > 20:
            self._history.pop()
        self._refresh_history()

    @Slot()
    def _on_bridge_ready_for_history(self) -> None:
        self._slam_started_at = datetime.now()

    @Slot()
    def _on_bridge_stopped_for_history(self) -> None:
        entry = _HistoryEntry(
            name="SLAM Bridge",
            started_at=self._slam_started_at,
            stopped_at=datetime.now(),
            exit_code=None,
        )
        self._slam_started_at = None
        self._history.insert(0, entry)
        if len(self._history) > 20:
            self._history.pop()
        self._refresh_history()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _populate(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(24)
        inner_layout.setContentsMargins(0, 0, 0, 0)

        inner_layout.addWidget(self._build_status_section())
        inner_layout.addWidget(self._build_network_panel())
        inner_layout.addWidget(self._build_quick_actions())
        inner_layout.addWidget(self._build_active_processes())
        inner_layout.addWidget(self._build_process_history())
        inner_layout.addStretch()

        scroll.setWidget(inner)
        self._content_layout.addWidget(scroll)

    # ── System status cards ────────────────────────────────────────────
    def _build_status_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel("SYSTEM STATUS")
        header.setObjectName("section-header")
        layout.addWidget(header)

        grid = QGridLayout()
        grid.setSpacing(12)

        self._card_sdk = MetricCard("Active Processes", "0", status="inactive")
        self._card_ros = MetricCard("ROS2 Setup", "—", status="inactive")
        self._card_rviz2 = MetricCard("RViz2 Binary", "—", status="inactive")
        self._card_net = MetricCard(
            "Network Interface",
            self._config.network.network_interface,
            status="info",
        )
        self._card_keydemo = MetricCard("keyDemo Binary", "—", status="inactive")

        grid.addWidget(self._card_sdk,     0, 0)
        grid.addWidget(self._card_ros,     0, 1)
        grid.addWidget(self._card_rviz2,   0, 2)
        grid.addWidget(self._card_net,     0, 3)
        grid.addWidget(self._card_keydemo, 1, 0)

        layout.addLayout(grid)
        return section

    # ── Network diagnostic panel ───────────────────────────────────────
    def _build_network_panel(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        header_row = QHBoxLayout()
        header_lbl = QLabel("ROBOT NETWORK")
        header_lbl.setObjectName("section-header")
        header_row.addWidget(header_lbl)
        header_row.addStretch()

        self._net_check_btn = QPushButton("Check now")
        self._net_check_btn.setProperty("class", "ghost")
        self._net_check_btn.setFixedHeight(24)
        self._net_check_btn.clicked.connect(self._refresh_network_panel)
        header_row.addWidget(self._net_check_btn)

        layout.addLayout(header_row)

        # Card container
        card = QWidget()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(8)

        # Interface row
        self._net_iface_row = _StatusRow("Ethernet Interface")
        card_layout.addWidget(self._net_iface_row)

        # IP assignment row
        self._net_ip_row = _StatusRow("Robot Subnet IP (192.168.123.x)")
        card_layout.addWidget(self._net_ip_row)

        # Assign IP button (shown only when IP is missing)
        self._net_assign_btn = QPushButton(
            "Assign IP  ( sudo ip addr add 192.168.123.100/24 dev enp2s0 )"
        )
        self._net_assign_btn.setProperty("class", "primary")
        self._net_assign_btn.setVisible(False)
        self._net_assign_btn.clicked.connect(self._assign_ip)
        card_layout.addWidget(self._net_assign_btn)

        # Robot reachability rows
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(
            f"background-color: {PALETTE['BORDER']}; max-height:1px; margin: 4px 0;"
        )
        card_layout.addWidget(sep)

        self._net_pc1_row = _StatusRow("PC1 — slam_operate  (192.168.123.161)")
        self._net_pc2_row = _StatusRow("Jetson NX — SSH     (192.168.123.164)")
        self._net_lidar_row = _StatusRow("LiDAR Mid360        (192.168.123.120)")
        card_layout.addWidget(self._net_pc1_row)
        card_layout.addWidget(self._net_pc2_row)
        card_layout.addWidget(self._net_lidar_row)

        note = QLabel(
            "Robot pings run in background — may take a few seconds. "
            "Robot must be powered on and cable connected."
        )
        note.setStyleSheet(f"color: {PALETTE['TEXT_MUTED']}; font-size: 11px;")
        note.setWordWrap(True)
        card_layout.addWidget(note)

        layout.addWidget(card)
        return section

    # ── Quick actions ──────────────────────────────────────────────────
    def _build_quick_actions(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel("QUICK ACTIONS")
        header.setObjectName("section-header")
        layout.addWidget(header)

        row = QHBoxLayout()
        row.setSpacing(10)

        actions = [
            ("◈  Start Mapping",       "mapping",       "primary"),
            ("◎  Start Localization",  "localization",  ""),
            ("▶  Start Navigation",    "navigation",    ""),
        ]
        for label, key, css_class in actions:
            btn = QPushButton(label)
            if css_class:
                btn.setProperty("class", css_class)
            btn.setMinimumHeight(42)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _c, k=key: self.navigate_to.emit(k))
            row.addWidget(btn)

        layout.addLayout(row)
        return section

    # ── Process history ────────────────────────────────────────────────
    def _build_process_history(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        hdr_row = QHBoxLayout()
        hdr_lbl = QLabel("PROCESS HISTORY")
        hdr_lbl.setObjectName("section-header")
        hdr_row.addWidget(hdr_lbl)
        hdr_row.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setProperty("class", "ghost")
        clear_btn.setFixedHeight(24)
        clear_btn.clicked.connect(self._clear_history)
        hdr_row.addWidget(clear_btn)
        layout.addLayout(hdr_row)

        self._hist_container = QWidget()
        self._hist_container.setObjectName("card")
        self._hist_inner = QVBoxLayout(self._hist_container)
        self._hist_inner.setContentsMargins(16, 12, 16, 12)
        self._hist_inner.setSpacing(6)
        layout.addWidget(self._hist_container)

        self._refresh_history()
        return section

    def _refresh_history(self) -> None:
        while self._hist_inner.count():
            item = self._hist_inner.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._history:
            lbl = QLabel("No processes stopped yet this session.")
            lbl.setStyleSheet(f"color: {PALETTE['TEXT_MUTED']}; font-size: 12px;")
            self._hist_inner.addWidget(lbl)
            return

        for entry in self._history:
            row = QHBoxLayout()
            row.setSpacing(8)

            dot = QLabel("●")
            dot.setFixedWidth(16)
            dot.setStyleSheet(f"color: {PALETTE['TEXT_MUTED']}; font-size: 10px;")
            row.addWidget(dot)

            name_lbl = QLabel(entry.name)
            name_lbl.setStyleSheet(
                f"color: {PALETTE['TEXT_SEC']}; font-size: 12px;"
            )
            name_lbl.setFixedWidth(160)
            row.addWidget(name_lbl)

            times = QLabel(
                f"started {entry.start_str()}   "
                f"stopped {entry.stop_str()}   "
                f"duration {entry.duration_str()}"
            )
            times.setStyleSheet(
                f"color: {PALETTE['TEXT_MUTED']}; font-size: 11px; font-family: monospace;"
            )
            row.addWidget(times, 1)

            if entry.exit_code is not None:
                code_color = PALETTE["SUCCESS"] if entry.exit_code == 0 else PALETTE["WARNING"]
                code_lbl = QLabel(f"exit {entry.exit_code}")
                code_lbl.setStyleSheet(
                    f"color: {code_color}; font-size: 11px; font-family: monospace;"
                )
                row.addWidget(code_lbl)

            wrapper = QWidget()
            wrapper.setLayout(row)
            self._hist_inner.addWidget(wrapper)

    def _clear_history(self) -> None:
        self._history.clear()
        self._refresh_history()

    # ── Active processes ───────────────────────────────────────────────
    def _build_active_processes(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel("ACTIVE PROCESSES")
        header.setObjectName("section-header")
        layout.addWidget(header)

        self._proc_container = QWidget()
        self._proc_container.setObjectName("card")
        self._proc_inner = QVBoxLayout(self._proc_container)
        self._proc_inner.setContentsMargins(16, 12, 16, 12)
        self._proc_inner.setSpacing(8)

        layout.addWidget(self._proc_container)
        self._refresh_processes()
        return section

    # ------------------------------------------------------------------
    # Runtime refresh
    # ------------------------------------------------------------------

    def _start_refresh_timer(self) -> None:
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._refresh_all)
        self._timer.start()

    def _refresh_all(self) -> None:
        self._refresh_status_cards()
        self._refresh_processes()
        self._refresh_network_panel()

    def _refresh_status_cards(self) -> None:
        import os

        # RViz2 binary — check via PATH or known locations
        ros_distro = os.environ.get("ROS_DISTRO", self._config.ros.distro)
        rviz2_found = (
            shutil.which("rviz2") is not None
            or (ros_distro and Path(f"/opt/ros/{ros_distro}/bin/rviz2").exists())
        )
        if rviz2_found:
            self._card_rviz2.set_value("Found")
            self._card_rviz2.set_status("ok")
        else:
            self._card_rviz2.set_value("Not found")
            self._card_rviz2.set_status("error")

        # ROS2 environment — check env OR configured setup.bash
        setup_path = self._config.ros_setup_path
        if ros_distro or setup_path:
            label = ros_distro.capitalize() if ros_distro else "setup.bash"
            self._card_ros.set_value(label)
            self._card_ros.set_status("ok")
        else:
            self._card_ros.set_value("Not configured")
            self._card_ros.set_status("warning")

        # Network interface
        self._card_net.set_value(self._config.network.network_interface)

        # keyDemo binary
        keydemo = self._config.slam.binary
        if keydemo and Path(keydemo).exists():
            self._card_keydemo.set_value("Found")
            self._card_keydemo.set_status("ok")
        else:
            self._card_keydemo.set_value("Not found")
            self._card_keydemo.set_status("warning")

        # Active processes (PM + SLAM bridge)
        count = len(self._pm.running_keys()) + (1 if self._slam.is_running else 0)
        if count > 0:
            self._card_sdk.set_value(str(count))
            self._card_sdk.set_status("running")
        else:
            self._card_sdk.set_value("0")
            self._card_sdk.set_status("inactive")

    def _refresh_processes(self) -> None:
        while self._proc_inner.count():
            item = self._proc_inner.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        pm_running = self._pm.running_keys()
        slam_running = self._slam.is_running

        if not pm_running and not slam_running:
            lbl = QLabel("No active processes.")
            lbl.setStyleSheet(f"color: {PALETTE['TEXT_MUTED']}; font-size: 12px;")
            self._proc_inner.addWidget(lbl)
            return

        # SLAM bridge row
        if slam_running:
            started = self._slam_started_at
            self._proc_inner.addWidget(
                self._make_proc_row(
                    "SLAM Bridge",
                    started,
                    "slam_bridge.py  (SDK subprocess)",
                    PALETTE["ACCENT"],
                )
            )

        # ProcessManager rows
        for key in pm_running:
            info = self._pm.get_info(key)
            cmd = info.display_command()[:60] if info else key
            started = info.started_at if info else None
            self._proc_inner.addWidget(
                self._make_proc_row(
                    key.replace("_", " ").title(),
                    started,
                    cmd,
                    PALETTE["SUCCESS"],
                )
            )

    def _make_proc_row(
        self,
        name: str,
        started_at: Optional[datetime],
        cmd: str,
        dot_color: str,
    ) -> QWidget:
        row = QHBoxLayout()
        row.setSpacing(8)

        dot = QLabel("●")
        dot.setStyleSheet(f"color: {dot_color}; font-size: 10px;")
        dot.setFixedWidth(16)
        row.addWidget(dot)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"color: {PALETTE['TEXT_PRIMARY']}; font-size: 13px;")
        name_lbl.setFixedWidth(160)
        row.addWidget(name_lbl)

        if started_at:
            elapsed = datetime.now() - started_at
            mins, secs = divmod(int(elapsed.total_seconds()), 60)
            time_lbl = QLabel(f"{started_at.strftime('%H:%M')}  +{mins:02d}:{secs:02d}")
            time_lbl.setStyleSheet(
                f"color: {PALETTE['TEXT_SEC']}; font-size: 11px; font-family: monospace;"
            )
            time_lbl.setFixedWidth(130)
            row.addWidget(time_lbl)

        cmd_lbl = QLabel(cmd)
        cmd_lbl.setStyleSheet(
            f"color: {PALETTE['TEXT_MUTED']}; font-size: 11px; font-family: monospace;"
        )
        cmd_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(cmd_lbl, 1)

        wrapper = QWidget()
        wrapper.setLayout(row)
        return wrapper

    # ------------------------------------------------------------------
    # Network panel refresh
    # ------------------------------------------------------------------

    def _refresh_network_panel(self) -> None:
        iface = self._config.network.network_interface
        status = get_interface_status(iface)

        # Interface existence + up state
        if not status.exists:
            self._net_iface_row.set("error", iface, "Not found in /sys/class/net")
        elif not status.is_up:
            self._net_iface_row.set("warning", iface, "Interface DOWN")
        else:
            self._net_iface_row.set("ok", iface, "UP")

        # IP assignment
        if status.has_robot_subnet_ip:
            self._net_ip_row.set("ok", status.robot_subnet_ip, "Assigned")
            self._net_assign_btn.setVisible(False)
        elif status.addresses:
            self._net_ip_row.set(
                "warning",
                ", ".join(status.addresses),
                "Wrong subnet — need 192.168.123.x",
            )
            self._net_assign_btn.setText(
                f"Assign 192.168.123.100/24 to {iface}  "
                f"(sudo ip addr add 192.168.123.100/24 dev {iface})"
            )
            self._net_assign_btn.setVisible(True)
        else:
            self._net_ip_row.set("error", "No IP", "Run: sudo ip addr add 192.168.123.100/24 dev " + iface)
            self._net_assign_btn.setText(
                f"Assign 192.168.123.100/24 to {iface}  "
                f"(runs: sudo ip addr add 192.168.123.100/24 dev {iface})"
            )
            self._net_assign_btn.setVisible(True)

        # Ping robot components in background (non-blocking via QTimer single-shot)
        # Reset to pending first
        self._net_pc1_row.set("info", "192.168.123.161", "Checking…")
        self._net_pc2_row.set("info", "192.168.123.164", "Checking…")
        self._net_lidar_row.set("info", "192.168.123.120", "Checking…")

        if status.ready_for_dds:
            QTimer.singleShot(0, self._ping_robot_components)

    def _ping_robot_components(self) -> None:
        pings = [
            (self._net_pc1_row,   "192.168.123.161", "slam_operate"),
            (self._net_pc2_row,   "192.168.123.164", "Jetson NX"),
            (self._net_lidar_row, "192.168.123.120", "LiDAR"),
        ]
        for row, ip, label in pings:
            reachable = ping_host(ip, timeout=0.8)
            if reachable:
                row.set("ok", ip, f"{label} — reachable")
            else:
                row.set("error", ip, f"{label} — no response")

    def _assign_ip(self) -> None:
        iface = self._config.network.network_interface
        ip = self._config.network.pc_ip

        import subprocess

        # First try without password (sudoers already configured)
        cmd = f"sudo -n ip addr add {ip}/24 dev {iface} && sudo -n ip link set {iface} up"
        try:
            result = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                QMessageBox.information(
                    self, "Conexión configurada ✓",
                    f"La dirección IP {ip} se ha asignado correctamente a {iface}.\n"
                    f"El robot ya debería ser accesible."
                )
                self._refresh_network_panel()
                return
        except Exception:
            pass

        # sudo needs a password — show a friendly dialog
        password = self._ask_sudo_password()
        if password is None:
            return  # user cancelled

        cmd_with_pass = (
            f"echo {repr(password)} | sudo -S ip addr add {ip}/24 dev {iface} && "
            f"echo {repr(password)} | sudo -S ip link set {iface} up"
        )
        try:
            result = subprocess.run(
                ["bash", "-c", cmd_with_pass],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                QMessageBox.information(
                    self, "Conexión configurada ✓",
                    f"La dirección IP {ip} se ha asignado correctamente a {iface}.\n"
                    f"El robot ya debería ser accesible."
                )
            else:
                err = (result.stderr or result.stdout).strip()
                if "incorrect password" in err.lower() or "wrong password" in err.lower() or "try again" in err.lower():
                    QMessageBox.critical(
                        self, "Contraseña incorrecta",
                        "La contraseña introducida no es correcta.\nVuelve a intentarlo."
                    )
                else:
                    QMessageBox.critical(
                        self, "No se pudo configurar la red",
                        f"Ha ocurrido un error al asignar la IP:\n\n{err}"
                    )
        except subprocess.TimeoutExpired:
            QMessageBox.critical(self, "Tiempo agotado", "La operación tardó demasiado. Comprueba la conexión.")
        except Exception as e:
            QMessageBox.critical(self, "Error inesperado", str(e))

        self._refresh_network_panel()

    def _ask_sudo_password(self) -> "str | None":
        """Show a friendly dialog asking for the sudo password."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Se necesita tu contraseña")
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet(
            f"background: {PALETTE['BG_SURFACE']}; color: {PALETTE['TEXT_PRIMARY']};"
        )

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 20)

        # Icon + title row
        title_row = QHBoxLayout()
        icon_lbl = QLabel("🔒")
        icon_lbl.setStyleSheet("font-size: 28px;")
        title_lbl = QLabel("Permiso de administrador necesario")
        title_lbl.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {PALETTE['TEXT_PRIMARY']};"
        )
        title_row.addWidget(icon_lbl)
        title_row.addWidget(title_lbl, 1)
        layout.addLayout(title_row)

        # Explanation
        explanation = QLabel(
            "Para conectar el ordenador con el robot, necesito asignarle "
            "una dirección de red. Esto requiere permisos de administrador.\n\n"
            "Introduce tu contraseña de usuario para continuar. "
            "No se guardará en ningún sitio."
        )
        explanation.setStyleSheet(
            f"color: {PALETTE['TEXT_SEC']}; font-size: 12px; line-height: 1.5;"
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        # Password field
        pwd_lbl = QLabel("Contraseña:")
        pwd_lbl.setStyleSheet(f"color: {PALETTE['TEXT_MUTED']}; font-size: 11px;")
        layout.addWidget(pwd_lbl)

        pwd_input = QLineEdit()
        pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        pwd_input.setPlaceholderText("Escribe tu contraseña aquí…")
        pwd_input.setStyleSheet(
            f"QLineEdit {{ background: {PALETTE['BG_ELEVATED']};"
            f" border: 1px solid {PALETTE['BORDER']}; border-radius: 6px;"
            f" padding: 8px 12px; font-size: 13px; color: {PALETTE['TEXT_PRIMARY']}; }}"
            f"QLineEdit:focus {{ border-color: {PALETTE['ACCENT']}; }}"
        )
        layout.addWidget(pwd_input)

        # Note
        note = QLabel("💡 Si no quieres introducir la contraseña cada vez, puedes configurarlo en Ajustes para que no se pida en el futuro.")
        note.setStyleSheet(
            f"color: {PALETTE['TEXT_MUTED']}; font-size: 10px;"
            f" background: {PALETTE['BG_ELEVATED']}; border-radius: 4px; padding: 8px;"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Configurar red")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setStyleSheet(
            f"background: {PALETTE['ACCENT']}; color: white; border-radius: 6px;"
            f" padding: 6px 16px; font-weight: bold;"
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        pwd_input.returnPressed.connect(dlg.accept)
        layout.addWidget(buttons)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            return pwd_input.text()
        return None


class _StatusRow(QWidget):
    """A label + status dot + value + detail in a horizontal row."""

    _COLORS = {
        "ok":      PALETTE["SUCCESS"],
        "warning": PALETTE["WARNING"],
        "error":   PALETTE["DANGER"],
        "info":    PALETTE["ACCENT"],
        "inactive": PALETTE["TEXT_MUTED"],
    }

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self._dot = QLabel("●")
        self._dot.setFixedWidth(14)
        self._dot.setStyleSheet(f"color: {PALETTE['TEXT_MUTED']}; font-size: 10px;")
        layout.addWidget(self._dot)

        lbl = QLabel(label)
        lbl.setFixedWidth(280)
        lbl.setStyleSheet(f"color: {PALETTE['TEXT_SEC']}; font-size: 12px;")
        layout.addWidget(lbl)

        self._value = QLabel("—")
        self._value.setFixedWidth(160)
        self._value.setStyleSheet(
            f"color: {PALETTE['TEXT_PRIMARY']}; font-size: 12px; font-family: monospace;"
        )
        layout.addWidget(self._value)

        self._detail = QLabel("")
        self._detail.setStyleSheet(f"color: {PALETTE['TEXT_MUTED']}; font-size: 12px;")
        layout.addWidget(self._detail)
        layout.addStretch()

    def set(self, state: str, value: str, detail: str = "") -> None:
        color = self._COLORS.get(state, PALETTE["TEXT_MUTED"])
        self._dot.setStyleSheet(
            f"color: {color}; font-size: 10px; background: transparent;"
        )
        self._value.setText(value)
        self._detail.setText(detail)
