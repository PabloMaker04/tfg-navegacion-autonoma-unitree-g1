"""
Manages the two incompatible execution environments required by the Unitree G1 SDK.

─── THE CORE PROBLEM ──────────────────────────────────────────────────────────────
The Unitree SDK uses CycloneDDS from /usr/local/lib.
ROS 2 installs its own CycloneDDS in /opt/ros/<distro>/lib.
These two versions are BINARY INCOMPATIBLE.

When ROS 2 is sourced, it prepends its lib path to LD_LIBRARY_PATH.
keyDemo (the SDK binary) then loads the wrong CycloneDDS and crashes immediately
with "free(): invalid pointer".

─── THE TWO ENVIRONMENTS ──────────────────────────────────────────────────────────

  SLAM environment (for keyDemo):
    - LD_LIBRARY_PATH starts with /usr/local/lib  (SDK's CycloneDDS wins)
    - ROS 2 lib path must NOT appear before /usr/local/lib
    - ROS 2 env vars are irrelevant and can be stripped for safety

  ROS2/DDS environment (for RViz2 and ros2 topic commands):
    - ROS 2 must be sourced (AMENT_PREFIX_PATH, etc.)
    - RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
    - CYCLONEDDS_URI set to the correct network interface (single line XML)
    - Without CYCLONEDDS_URI, ROS2 may try to use the wrong network interface
      (e.g. WiFi instead of Ethernet) and see no topics from the robot.

─── HOW WE SOLVE IT ───────────────────────────────────────────────────────────────
Both types of processes are launched via `bash -c '...'` with explicit env setup
embedded in the shell command string. This guarantees the environment is correct
regardless of how the UI itself was launched.
"""
from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class RosEnvironment:
    """
    Builds launch commands for the two execution environments.

    Parameters
    ----------
    ros_setup    : path to /opt/ros/<distro>/setup.bash or workspace install/setup.bash
    cyclone_uri  : single-line CYCLONEDDS_URI XML string
    slam_binary  : full path to the keyDemo C++ binary
    sdk_ld_path  : value to prepend to LD_LIBRARY_PATH for keyDemo (default /usr/local/lib)
    interface    : Ethernet interface name (e.g. enp2s0)
    """

    def __init__(
        self,
        ros_setup: str,
        cyclone_uri: str,
        slam_binary: str,
        sdk_ld_path: str = "/usr/local/lib",
        interface: str = "enp2s0",
    ) -> None:
        self._ros_setup = ros_setup
        self._cyclone_uri = cyclone_uri
        self._slam_binary = slam_binary
        self._sdk_ld_path = sdk_ld_path
        self._interface = interface

    # ------------------------------------------------------------------
    # RViz2 / ROS2 launch
    # ------------------------------------------------------------------

    def rviz2_launch_args(self, rviz_config: str) -> Tuple[str, List[str]]:
        """
        Return (command, args) to launch rviz2 with the correct DDS environment.

        Launched as: bash -c 'source <ros_setup> && export ... && rviz2 -d <config>'

        The caller passes these directly to ProcessManager.start().
        """
        rviz_config_q = shlex.quote(rviz_config)
        script = self._ros2_preamble() + f" && rviz2 -d {rviz_config_q}"
        return "bash", ["-c", script]

    def ros2_command_args(self, ros2_cmd: str) -> Tuple[str, List[str]]:
        """
        Return (command, args) to run any ros2 CLI command (topic list, hz, etc.)
        with the correct DDS environment.

        Example:
            cmd, args = env.ros2_command_args("ros2 topic hz /utlidar/cloud_livox_mid360")
        """
        script = self._ros2_preamble() + f" && {ros2_cmd}"
        return "bash", ["-c", script]

    # ------------------------------------------------------------------
    # keyDemo / SDK launch
    # ------------------------------------------------------------------

    def slam_bridge_launch_args(self, bridge_script: str) -> Tuple[str, List[str]]:
        """
        Return (command, args) to launch slam_bridge.py with the SDK's CycloneDDS.

        Launched as: bash -c 'LD_LIBRARY_PATH=/usr/local/lib python3 <bridge> <iface>'

        The Python script must use the SDK's /usr/local/lib CycloneDDS, not the
        ROS2 one, so we apply the same LD_LIBRARY_PATH isolation as for keyDemo.
        """
        script_q = shlex.quote(bridge_script)
        iface_q  = shlex.quote(self._interface)
        clean_ld = self._clean_ld_library_path()
        cmd = f"LD_LIBRARY_PATH={shlex.quote(clean_ld)} python3 {script_q} {iface_q}"
        return "bash", ["-c", cmd]

    def slam_launch_args(self, extra_args: List[str] | None = None) -> Tuple[str, List[str]]:
        """
        Return (command, args) to launch keyDemo with the SDK's CycloneDDS.

        Launched as: bash -c 'LD_LIBRARY_PATH=/usr/local/lib <binary> <iface> [args]'

        IMPORTANT: ROS2 lib paths must NOT appear before /usr/local/lib.
        We achieve this by building LD_LIBRARY_PATH from scratch, prepending
        sdk_ld_path and then appending only the non-ROS system libs.
        """
        binary_q = shlex.quote(self._slam_binary)
        iface_q = shlex.quote(self._interface)
        extra = " ".join(shlex.quote(a) for a in (extra_args or []))

        # Build a clean LD_LIBRARY_PATH that starts with the SDK path.
        # Strip any ROS2 lib entries from the parent process's path to be safe.
        clean_ld = self._clean_ld_library_path()

        script = (
            f"LD_LIBRARY_PATH={shlex.quote(clean_ld)} "
            f"{binary_q} {iface_q} {extra}".strip()
        )
        return "bash", ["-c", script]

    # ------------------------------------------------------------------
    # Environment check helpers
    # ------------------------------------------------------------------

    def is_ros2_available(self) -> bool:
        return bool(self._ros_setup) and Path(self._ros_setup).exists()

    def is_slam_binary_available(self) -> bool:
        return bool(self._slam_binary) and Path(self._slam_binary).exists()

    def describe_rviz_env(self) -> str:
        """Human-readable summary of what RViz2 will receive."""
        lines = []
        if self._ros_setup:
            lines.append(f"  source {self._ros_setup}")
        lines.append(f"  RMW_IMPLEMENTATION=rmw_cyclonedds_cpp")
        lines.append(f"  CYCLONEDDS_URI=<...NetworkInterface name=\"{self._interface}\"...>")
        return "\n".join(lines)

    def describe_slam_env(self) -> str:
        """Human-readable summary of what keyDemo will receive."""
        return f"  LD_LIBRARY_PATH={self._sdk_ld_path}:... (SDK CycloneDDS first)"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ros2_preamble(self) -> str:
        """Shell fragment that sets up a full ROS2+DDS environment."""
        parts = []
        if self._ros_setup:
            parts.append(f"source {shlex.quote(self._ros_setup)}")
        parts.append("export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp")
        # CYCLONEDDS_URI must be in single quotes in bash to avoid XML quoting issues
        uri = self._cyclone_uri.replace("'", "'\\''")
        parts.append(f"export CYCLONEDDS_URI='{uri}'")
        return " && ".join(parts)

    def _clean_ld_library_path(self) -> str:
        """
        Build LD_LIBRARY_PATH with sdk_ld_path first, followed by any
        non-ROS entries from the parent process.
        """
        current = os.environ.get("LD_LIBRARY_PATH", "")
        filtered = [
            p for p in current.split(":")
            if p and "/opt/ros" not in p and "/ros2" not in p
        ]
        parts = [self._sdk_ld_path] + filtered
        return ":".join(dict.fromkeys(parts))  # deduplicate while preserving order
