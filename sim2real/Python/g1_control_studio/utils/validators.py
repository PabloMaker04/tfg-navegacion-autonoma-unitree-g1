"""Utility validators shared across services and UI layers."""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Simple existence checks
# ---------------------------------------------------------------------------

def file_exists(path: str) -> bool:
    return bool(path) and Path(path).is_file()


def dir_exists(path: str) -> bool:
    return bool(path) and Path(path).is_dir()


def ros_distro() -> str:
    return os.environ.get("ROS_DISTRO", "")


def ros_sourced() -> bool:
    return bool(ros_distro())


def rviz2_binary_path(ros_distro_name: str = "") -> str:
    """Return path to rviz2 binary, searching PATH and known locations."""
    found = shutil.which("rviz2")
    if found:
        return found
    distro = ros_distro_name or ros_distro()
    if distro:
        candidate = f"/opt/ros/{distro}/bin/rviz2"
        if Path(candidate).exists():
            return candidate
    return ""


# ---------------------------------------------------------------------------
# Network diagnostics
# ---------------------------------------------------------------------------

@dataclass
class InterfaceStatus:
    name: str
    exists: bool
    is_up: bool
    addresses: List[str]           # all IPv4 addresses on this interface
    has_robot_subnet_ip: bool      # True if any address is in 192.168.123.x/24
    robot_subnet_ip: str           # the 192.168.123.x address, or ""

    @property
    def ready_for_dds(self) -> bool:
        """CycloneDDS needs the interface to exist, be up, and have an IP."""
        return self.exists and self.is_up and bool(self.addresses)

    @property
    def ready_for_robot(self) -> bool:
        """To communicate with the robot, we specifically need 192.168.123.x."""
        return self.ready_for_dds and self.has_robot_subnet_ip

    def status_summary(self) -> str:
        if not self.exists:
            return "Interface not found"
        if not self.is_up:
            return "Interface is DOWN"
        if not self.addresses:
            return "No IP address assigned"
        if not self.has_robot_subnet_ip:
            return f"Has IP but not in robot subnet (192.168.123.x) — found: {', '.join(self.addresses)}"
        return f"Ready — {self.robot_subnet_ip}"


def get_interface_status(iface: str) -> InterfaceStatus:
    """Query the current state of a network interface."""
    net_dir = Path("/sys/class/net")
    exists = (net_dir / iface).exists()

    if not exists:
        return InterfaceStatus(
            name=iface, exists=False, is_up=False,
            addresses=[], has_robot_subnet_ip=False, robot_subnet_ip=""
        )

    # Check UP state via operstate
    operstate_file = net_dir / iface / "operstate"
    try:
        operstate = operstate_file.read_text().strip()
        is_up = operstate in ("up", "unknown")  # "unknown" = loopback always up
    except OSError:
        is_up = False

    # Get IPv4 addresses via `ip addr show`
    addresses: List[str] = []
    try:
        result = subprocess.run(
            ["ip", "-4", "addr", "show", iface],
            capture_output=True, text=True, timeout=3
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                parts = line.split()
                if len(parts) >= 2:
                    ip = parts[1].split("/")[0]
                    addresses.append(ip)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    robot_subnet_ip = next(
        (ip for ip in addresses if ip.startswith("192.168.123.")), ""
    )

    return InterfaceStatus(
        name=iface,
        exists=True,
        is_up=is_up,
        addresses=addresses,
        has_robot_subnet_ip=bool(robot_subnet_ip),
        robot_subnet_ip=robot_subnet_ip,
    )


def ping_host(ip: str, timeout: float = 1.0) -> bool:
    """Quick single-packet ping. Returns True if host responds."""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(int(timeout)), ip],
            capture_output=True, timeout=timeout + 2
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def available_interfaces() -> List[str]:
    """Return all network interface names visible to the OS."""
    try:
        return sorted(os.listdir("/sys/class/net/"))
    except OSError:
        return []
