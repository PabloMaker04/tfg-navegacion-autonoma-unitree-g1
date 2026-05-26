from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QMessageBox,
)
from PySide6.QtCore import Qt, Slot

from config.app_config import AppConfig
from core.process_manager import ProcessManager
from core.ros_environment import RosEnvironment
from core.rviz_manager import RVizManager, RVizConfig
from services.slam_service import SlamService
from ui.components.header_bar import HeaderBar
from ui.components.sidebar import Sidebar
from ui.pages.dashboard_page import DashboardPage
from ui.pages.mapping_page import MappingPage
from ui.pages.localization_page import LocalizationPage
from ui.pages.navigation_page import NavigationPage
from ui.pages.rviz_page import RVizPage
from ui.pages.logs_page import LogsPage
from ui.pages.settings_page import SettingsPage
from ui.styles.theme import build_stylesheet

_PAGE_TITLES = {
    "dashboard":    "Dashboard",
    "mapping":      "Mapping",
    "localization": "Localization",
    "navigation":   "Navigation",
    "rviz":         "RViz2",
    "logs":         "Logs",
    "settings":     "Settings",
}


class MainWindow(QMainWindow):

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config

        # Core services
        self._pm = ProcessManager(self)
        ros_env = self._build_ros_env()
        self._rm = RVizManager(self._pm, ros_env, self)
        self._slam = SlamService(self._config, ros_env, self)

        self._setup_window()
        self._apply_theme()
        self._build_ui()
        self._navigate_to("dashboard")

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowTitle("G1 Control Studio")
        self.resize(1400, 860)
        self.setMinimumSize(1100, 700)

    def _apply_theme(self) -> None:
        self.setStyleSheet(build_stylesheet())

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("page-container")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self._header = HeaderBar()
        self._header.set_network_interface(self._config.network.network_interface)
        root.addWidget(self._header)

        # Body: sidebar + page stack
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._sidebar = Sidebar()
        self._sidebar.page_requested.connect(self._navigate_to)
        body.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        self._stack.setObjectName("page-container")
        body.addWidget(self._stack, 1)

        root.addLayout(body, 1)

        self._build_pages()
        self._connect_process_signals()
        self._connect_bridge_header()
        self._detect_ros_env()

    def _build_pages(self) -> None:
        self._pages: dict[str, QWidget] = {}

        dashboard = DashboardPage(self._config, self._pm, self._rm, self._slam)
        dashboard.navigate_to.connect(self._navigate_to)

        mapping      = MappingPage(self._config, self._rm, self._slam)
        localization = LocalizationPage(self._config, self._rm, self._slam)
        localization.navigate_to.connect(self._navigate_to)
        navigation   = NavigationPage(self._config, self._rm, self._slam)
        navigation.navigate_to.connect(self._navigate_to)
        rviz        = RVizPage(self._config, self._rm)
        logs        = LogsPage(self._pm)
        settings    = SettingsPage(self._config)
        settings.settings_saved.connect(self._on_settings_saved)

        for page in [dashboard, mapping, localization, navigation, rviz, logs, settings]:
            self._pages[page.PAGE_KEY] = page
            self._stack.addWidget(page)

    def _connect_process_signals(self) -> None:
        self._pm.error_occurred.connect(self._on_proc_error)

    def _connect_bridge_header(self) -> None:
        self._header.bridge_clicked.connect(self._on_bridge_toggle)
        self._slam.bridge_ready.connect(
            lambda: self._header.set_bridge_state("ready")
        )
        self._slam.bridge_stopped.connect(
            lambda: self._header.set_bridge_state("idle")
        )
        self._slam.bridge_error.connect(
            lambda _msg: self._header.set_bridge_state("error")
        )

    @Slot()
    def _on_bridge_toggle(self) -> None:
        if self._slam.is_running:
            self._slam.disconnect()
        else:
            self._header.set_bridge_state("connecting")
            self._slam.connect()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    @Slot(str)
    def _navigate_to(self, key: str) -> None:
        page = self._pages.get(key)
        if page is None:
            return
        self._stack.setCurrentWidget(page)
        self._sidebar.set_active(key)
        self._header.set_page_title(_PAGE_TITLES.get(key, key.title()))

    # ------------------------------------------------------------------
    # Environment
    # ------------------------------------------------------------------

    def _build_ros_env(self) -> RosEnvironment:
        return RosEnvironment(
            ros_setup=self._config.ros_setup_path,
            cyclone_uri=self._config.cyclonedds_uri,
            slam_binary=self._config.slam.binary,
            sdk_ld_path=self._config.slam.ld_library_path,
            interface=self._config.network.network_interface,
        )

    def _detect_ros_env(self) -> None:
        import os
        ros_distro = os.environ.get("ROS_DISTRO", self._config.ros.distro)
        setup_exists = bool(self._config.ros_setup_path)

        if setup_exists:
            label = ros_distro.capitalize() if ros_distro else "Found"
            self._header.set_ros_status("ok", label)
        else:
            self._header.set_ros_status("warning", "No setup.bash")

        self._sync_rviz_paths()

    def _sync_rviz_paths(self) -> None:
        self._rm.set_config_path(RVizConfig.MAPPING,    self._config.rviz.mapping_config)
        self._rm.set_config_path(RVizConfig.RELOCATION, self._config.rviz.relocation_config)
        self._rm.set_config_path(RVizConfig.NAVIGATION, self._config.rviz.navigation_config)
        self._rm.set_config_path(RVizConfig.DEBUG,      self._config.rviz.debug_config)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    @Slot()
    def _on_settings_saved(self) -> None:
        self._header.set_network_interface(self._config.network.network_interface)
        new_env = self._build_ros_env()
        self._rm.update_ros_env(new_env)
        self._slam.update_ros_env(new_env)
        self._sync_rviz_paths()
        self._detect_ros_env()

    @Slot(str, str)
    def _on_proc_error(self, key: str, message: str) -> None:
        # Only surface non-RViz errors as dialog; RViz errors go to RVizPage log
        if not key.startswith("rviz_"):
            QMessageBox.critical(
                self,
                f"Process Error — {key}",
                message,
            )

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        running = self._pm.running_keys()
        slam_running = self._slam.is_running
        if running or slam_running:
            names = [f"  • {k}" for k in running]
            if slam_running:
                names.insert(0, "  • slam_bridge")
            reply = QMessageBox.question(
                self,
                "Active Processes",
                f"{len(names)} process(es) still running:\n"
                + "\n".join(names)
                + "\n\nClose all and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._slam.force_stop()
            self._pm.stop_all()
        event.accept()
