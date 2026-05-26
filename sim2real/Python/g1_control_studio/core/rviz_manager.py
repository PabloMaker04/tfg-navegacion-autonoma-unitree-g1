"""
Manages RViz2 instances launched by the application.

Each named configuration (mapping, relocation, navigation, debug) is tracked
independently. RViz2 is always launched with the correct ROS2+DDS environment
via RosEnvironment, which is the only way to guarantee topic visibility.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QObject, Signal, Slot

from core.process_manager import ProcessManager
from core.ros_environment import RosEnvironment
from utils.validators import get_interface_status


class RVizConfig:
    MAPPING = "rviz_mapping"
    RELOCATION = "rviz_relocation"
    NAVIGATION = "rviz_navigation"
    DEBUG = "rviz_debug"

    LABELS: Dict[str, str] = {
        MAPPING: "Mapping",
        RELOCATION: "Relocation",
        NAVIGATION: "Navigation",
        DEBUG: "Debug",
    }


class RVizManager(QObject):
    """
    Wraps ProcessManager to handle RViz2 lifecycle.

    RViz2 is launched via `bash -c 'source <ros_setup> && export CYCLONEDDS_URI=... && rviz2 -d ...'`
    so it always gets the correct DDS environment regardless of how the UI was started.

    Signals
    -------
    rviz_started(config_key)
    rviz_stopped(config_key)
    rviz_error(config_key, message)
    rviz_not_found()
    """

    rviz_started = Signal(str)
    rviz_stopped = Signal(str)
    rviz_error = Signal(str, str)
    rviz_not_found = Signal()

    def __init__(
        self,
        process_manager: ProcessManager,
        ros_env: RosEnvironment,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._pm = process_manager
        self._ros_env = ros_env
        self._config_paths: Dict[str, str] = {}

        self._pm.process_started.connect(self._on_proc_started)
        self._pm.process_stopped.connect(self._on_proc_stopped)
        self._pm.error_occurred.connect(self._on_proc_error)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_config_path(self, config_key: str, path: str) -> None:
        self._config_paths[config_key] = path

    def config_path(self, config_key: str) -> str:
        return self._config_paths.get(config_key, "")

    def config_exists(self, config_key: str) -> bool:
        path = self.config_path(config_key)
        return bool(path) and Path(path).exists()

    def update_ros_env(self, ros_env: RosEnvironment) -> None:
        """Replace the RosEnvironment instance (called after settings save)."""
        self._ros_env = ros_env

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self, config_key: str) -> bool:
        """
        Launch RViz2 for the given configuration key.

        The process is started via bash with ROS2 sourced and CYCLONEDDS_URI
        set to the configured network interface. This is the only reliable way
        to ensure RViz2 sees the robot's topics.

        Returns False if configuration is missing or instance already open.
        """
        config_path = self.config_path(config_key)
        if not config_path:
            self.rviz_error.emit(config_key, "No .rviz configuration path configured.")
            return False

        if not Path(config_path).exists():
            self.rviz_error.emit(
                config_key,
                f"Configuration file not found:\n{config_path}",
            )
            return False

        if self.is_open(config_key):
            self.rviz_error.emit(
                config_key, "An RViz2 instance for this configuration is already running."
            )
            return False

        if not self._ros_env.is_ros2_available():
            self.rviz_error.emit(
                config_key,
                "ROS2 setup.bash not found.\n\n"
                "Set the correct ROS2 setup script path in Settings → ROS2.",
            )
            self.rviz_not_found.emit()
            return False

        # Validate network interface has an IP — CycloneDDS requires it
        iface = self._ros_env._interface
        net_status = get_interface_status(iface)
        if not net_status.ready_for_dds:
            self.rviz_error.emit(
                config_key,
                f"Network interface '{iface}' is not ready for DDS:\n"
                f"{net_status.status_summary()}\n\n"
                f"Fix: sudo ip addr add 192.168.123.100/24 dev {iface}\n\n"
                f"CycloneDDS requires the interface to have an IP address.",
            )
            return False

        cmd, args = self._ros_env.rviz2_launch_args(config_path)
        return self._pm.start(config_key, cmd, args)

    def close(self, config_key: str) -> None:
        self._pm.stop(config_key)

    def close_all(self) -> None:
        for key in RVizConfig.LABELS:
            self.close(key)

    def is_open(self, config_key: str) -> bool:
        return self._pm.is_running(config_key)

    def open_instances(self) -> Dict[str, str]:
        return {
            k: self._config_paths.get(k, "")
            for k in RVizConfig.LABELS
            if self.is_open(k)
        }

    # ------------------------------------------------------------------
    # Forwarded signals
    # ------------------------------------------------------------------

    @Slot(str)
    def _on_proc_started(self, key: str) -> None:
        if key in RVizConfig.LABELS:
            self.rviz_started.emit(key)

    @Slot(str, int)
    def _on_proc_stopped(self, key: str, _exit_code: int) -> None:
        if key in RVizConfig.LABELS:
            self.rviz_stopped.emit(key)

    @Slot(str, str)
    def _on_proc_error(self, key: str, message: str) -> None:
        if key in RVizConfig.LABELS:
            self.rviz_error.emit(key, message)
