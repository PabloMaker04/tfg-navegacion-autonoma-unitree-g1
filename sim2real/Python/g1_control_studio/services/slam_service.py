"""
SlamService — Qt wrapper around the slam_bridge.py subprocess.

Lifecycle
---------
  connect()     → launches slam_bridge.py with the correct LD_LIBRARY_PATH
  disconnect()  → sends {"cmd":"quit"} then terminates the process
  The bridge emits "ready" once DDS is initialized; the service relays this
  as the `bridge_ready` signal so pages know the SDK is usable.

Thread safety
-------------
  All signals are emitted from the Qt main thread via QProcess callbacks.
  The bridge process runs in a subprocess — no shared memory.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QProcess, Signal, Slot, QTimer

from config.app_config import AppConfig
from core.ros_environment import RosEnvironment


class SlamService(QObject):
    """
    Signals emitted
    ---------------
    bridge_ready()                   — DDS initialized, commands accepted
    bridge_stopped()                 — process exited
    bridge_error(message)            — process failed to start or crashed

    status_received(message, level)  — "status" events (info/ok/warn/error)
    pose_updated(x,y,z,qx,qy,qz,qw) — continuous robot pose from slam_info
    arrived(is_arrived, node_name)   — waypoint arrival event

    api_result(cmd, succeed, info)   — response to every SDK API call
    pose_added(pose_dict, count)     — waypoint added to list
    tasks_cleared()
    nav_started(count)
    nav_targeting(index, pose_dict)
    nav_stopped()

    raw_log(line)                    — unstructured lines (SDK internals, stderr)
    """

    # Connection
    bridge_ready   = Signal()
    bridge_stopped = Signal()
    bridge_error   = Signal(str)

    # Localization state — True once start_relocation API succeeds, False when bridge stops
    localization_active = Signal(bool)

    # Data
    status_received = Signal(str, str)          # message, level
    pose_updated    = Signal(float, float, float, float, float, float, float)
    arrived         = Signal(bool, str)         # is_arrived, node_name
    api_result      = Signal(str, bool, str)    # cmd, succeed, info

    # Navigation lifecycle
    pose_added     = Signal(dict, int)          # pose_dict, total_count
    tasks_cleared  = Signal()
    nav_started    = Signal(int)                # waypoint count
    nav_targeting  = Signal(int, dict)          # index, pose_dict
    nav_stopped    = Signal()

    # Debug
    raw_log = Signal(str)

    # ------------------------------------------------------------------

    def __init__(
        self,
        config: AppConfig,
        ros_env: RosEnvironment,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._config              = config
        self._ros_env             = ros_env
        self._process: Optional[QProcess] = None
        self._ready               = False
        self._localization_ready  = False

        # Path to slam_bridge.py — lives alongside this package
        self._bridge_script = str(
            Path(__file__).resolve().parents[1] / "slam_bridge.py"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        return self._ready and self._is_running()

    @property
    def is_running(self) -> bool:
        return self._is_running()

    @property
    def is_localization_active(self) -> bool:
        return self._localization_ready and self._is_running()

    def connect(self) -> bool:
        """Launch slam_bridge.py. Returns False if already running."""
        if self._is_running():
            self.status_received.emit("Bridge already running.", "warn")
            return False

        if not Path(self._bridge_script).exists():
            self.bridge_error.emit(
                f"slam_bridge.py not found at:\n{self._bridge_script}"
            )
            return False

        cmd, args = self._ros_env.slam_bridge_launch_args(self._bridge_script)

        self._process = QProcess(self)
        # Separate channels: stdout = JSON events, stderr = SDK raw logs
        self._process.setProcessChannelMode(
            QProcess.ProcessChannelMode.SeparateChannels
        )
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.started.connect(self._on_proc_started)
        self._process.finished.connect(self._on_proc_finished)
        self._process.errorOccurred.connect(self._on_proc_error)

        self._ready = False
        self.status_received.emit(
            f"Starting SLAM bridge — interface: {self._config.network.network_interface}",
            "info",
        )
        self._process.start(cmd, args)
        return True

    def disconnect(self) -> None:
        if not self._is_running():
            return
        self._send({"cmd": "quit"})
        QTimer.singleShot(1500, self._force_kill)

    def force_stop(self) -> None:
        """Synchronously kill the bridge. Must be called on app shutdown."""
        if not self._is_running():
            return
        self._send({"cmd": "quit"})
        if not self._process.waitForFinished(800):
            self._process.kill()
            self._process.waitForFinished(300)
        self._ready              = False
        self._localization_ready = False

    def update_ros_env(self, ros_env: RosEnvironment) -> None:
        self._ros_env = ros_env

    # ------------------------------------------------------------------
    # Commands — each mirrors a keyDemo.py key action
    # ------------------------------------------------------------------

    def start_mapping(self) -> None:
        self._send({"cmd": "start_mapping"})

    def end_mapping(self) -> None:
        self._send({"cmd": "end_mapping"})

    def start_relocation(
        self,
        x: float = 0.0, y: float = 0.0, z: float = 0.0,
        q_x: float = 0.0, q_y: float = 0.0,
        q_z: float = 0.0, q_w: float = 1.0,
    ) -> None:
        self._send({
            "cmd": "start_relocation",
            "x": x, "y": y, "z": z,
            "q_x": q_x, "q_y": q_y, "q_z": q_z, "q_w": q_w,
        })

    def add_current_pose(self) -> None:
        self._send({"cmd": "add_current_pose"})

    def clear_tasks(self) -> None:
        self._send({"cmd": "clear_tasks"})

    def execute_tasks(self) -> None:
        self._send({"cmd": "execute_tasks"})

    def pause_nav(self) -> None:
        self._send({"cmd": "pause_nav"})

    def resume_nav(self) -> None:
        self._send({"cmd": "resume_nav"})

    def stop(self) -> None:
        self._send({"cmd": "stop"})

    def get_pose(self) -> None:
        self._send({"cmd": "get_pose"})

    # ------------------------------------------------------------------
    # Private: process I/O
    # ------------------------------------------------------------------

    def _send(self, command: dict) -> None:
        if not self._is_running():
            self.status_received.emit(
                f"Cannot send '{command.get('cmd')}' — bridge not running.", "warn"
            )
            return
        line = json.dumps(command) + "\n"
        self._process.write(line.encode("utf-8"))

    @Slot()
    def _on_stdout(self) -> None:
        raw = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in raw.splitlines():
            line = line.strip()
            if line:
                self._parse_event(line)

    @Slot()
    def _on_stderr(self) -> None:
        raw = self._process.readAllStandardError().data().decode("utf-8", errors="replace")
        for line in raw.splitlines():
            if line.strip():
                self.raw_log.emit(line.strip())

    def _parse_event(self, line: str) -> None:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            self.raw_log.emit(line)
            return

        t = event.get("type", "")

        if t == "ready":
            self._ready = True
            self.bridge_ready.emit()

        elif t == "status":
            self.status_received.emit(
                event.get("message", ""), event.get("level", "info")
            )

        elif t == "pose":
            self.pose_updated.emit(
                float(event.get("x",   0.0)),
                float(event.get("y",   0.0)),
                float(event.get("z",   0.0)),
                float(event.get("q_x", 0.0)),
                float(event.get("q_y", 0.0)),
                float(event.get("q_z", 0.0)),
                float(event.get("q_w", 1.0)),
            )

        elif t == "arrived":
            self.arrived.emit(
                bool(event.get("is_arrived", False)),
                str(event.get("node_name", "")),
            )

        elif t == "api_result":
            cmd_val     = str(event.get("cmd", ""))
            succeed_val = bool(event.get("succeed", False))
            info_val    = str(event.get("info", ""))
            self.api_result.emit(cmd_val, succeed_val, info_val)
            if cmd_val == "start_relocation" and succeed_val:
                self._localization_ready = True
                self.localization_active.emit(True)

        elif t == "pose_added":
            self.pose_added.emit(
                dict(event.get("pose", {})),
                int(event.get("count", 0)),
            )

        elif t == "tasks_cleared":
            self.tasks_cleared.emit()

        elif t == "nav_started":
            self.nav_started.emit(int(event.get("count", 0)))

        elif t == "nav_targeting":
            self.nav_targeting.emit(
                int(event.get("index", 0)),
                dict(event.get("pose", {})),
            )

        elif t == "nav_stopped":
            self.nav_stopped.emit()

        else:
            self.raw_log.emit(line)

    # ------------------------------------------------------------------
    # Private: process lifecycle
    # ------------------------------------------------------------------

    @Slot()
    def _on_proc_started(self) -> None:
        self.status_received.emit("SLAM bridge process started.", "info")

    @Slot(int, QProcess.ExitStatus)
    def _on_proc_finished(self, exit_code: int, _status) -> None:
        self._ready = False
        if self._localization_ready:
            self._localization_ready = False
            self.localization_active.emit(False)
        self.status_received.emit(
            f"SLAM bridge stopped (exit code {exit_code}).",
            "ok" if exit_code == 0 else "warn",
        )
        self.bridge_stopped.emit()

    @Slot(QProcess.ProcessError)
    def _on_proc_error(self, error: QProcess.ProcessError) -> None:
        messages = {
            QProcess.ProcessError.FailedToStart: "Failed to start — check path and LD_LIBRARY_PATH.",
            QProcess.ProcessError.Crashed:       "Bridge process crashed.",
            QProcess.ProcessError.Timedout:      "Process timed out.",
        }
        msg = messages.get(error, "Unknown process error.")
        self._ready = False
        self.bridge_error.emit(msg)

    def _is_running(self) -> bool:
        return (
            self._process is not None
            and self._process.state() == QProcess.ProcessState.Running
        )

    def _force_kill(self) -> None:
        if self._is_running():
            self._process.kill()
