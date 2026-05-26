import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SLAM_ROOT = _PROJECT_ROOT / "unitree_slam_example_python"
_DEFAULT_RVIZ_MAPPING = str(_SLAM_ROOT / "rviz2" / "mapping.rviz")
_DEFAULT_RVIZ_RELOCATION = str(_SLAM_ROOT / "rviz2" / "relocation.rviz")
_CONFIG_FILE = Path.home() / ".config" / "g1_control_studio" / "settings.json"

# Typical locations for the compiled keyDemo binary
_DEFAULT_KEYDEMO = str(
    Path.home() / "Practicas" / "unitree_services_example" / "example" / "build" / "keyDemo"
)
# Default unitree.sh script path
_DEFAULT_UNITREE_SH = str(Path.home() / "Practicas" / "unitree.sh")


@dataclass
class NetworkConfig:
    # Network interface connecting the PC to the robot (192.168.123.x subnet)
    network_interface: str = "enp2s0"
    # IP assigned to this PC on the robot subnet
    pc_ip: str = "192.168.123.100"

    # Robot component IPs (read-only reference; not configurable from the robot side)
    robot_pc1_ip: str = "192.168.123.161"   # Control PC — slam_operate service
    robot_pc2_ip: str = "192.168.123.164"   # Jetson NX  — SSH accessible
    lidar_ip: str = "192.168.123.120"        # Livox Mid360 LiDAR


@dataclass
class SlamConfig:
    # Path to the compiled C++ keyDemo binary
    binary: str = _DEFAULT_KEYDEMO
    # LD_LIBRARY_PATH required to avoid CycloneDDS conflict with ROS2
    # Must prepend /usr/local/lib so the SDK's DDS is loaded, not ROS2's
    ld_library_path: str = "/usr/local/lib"


@dataclass
class RosConfig:
    # Auto-detected from current shell environment; user can override
    distro: str = field(default_factory=lambda: os.environ.get("ROS_DISTRO", "humble"))
    workspace_setup: str = ""
    # Path to unitree.sh — sources ROS2 and sets CYCLONEDDS_URI + RMW_IMPLEMENTATION
    unitree_sh: str = _DEFAULT_UNITREE_SH
    # Network interface name used inside CYCLONEDDS_URI (usually same as network_interface)
    cyclone_interface: str = "enp2s0"


@dataclass
class RVizConfig:
    mapping_config: str = _DEFAULT_RVIZ_MAPPING
    relocation_config: str = _DEFAULT_RVIZ_RELOCATION
    # Navigation reuses relocation config unless a dedicated file is set
    navigation_config: str = _DEFAULT_RVIZ_RELOCATION
    debug_config: str = ""


@dataclass
class UIConfig:
    theme: str = "dark"
    log_max_lines: int = 2000
    show_command_echo: bool = True


@dataclass
class AppConfig:
    network: NetworkConfig = field(default_factory=NetworkConfig)
    slam: SlamConfig = field(default_factory=SlamConfig)
    ros: RosConfig = field(default_factory=RosConfig)
    rviz: RVizConfig = field(default_factory=RVizConfig)
    ui: UIConfig = field(default_factory=UIConfig)

    def save(self) -> None:
        _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_CONFIG_FILE, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls) -> "AppConfig":
        if not _CONFIG_FILE.exists():
            return cls()
        try:
            with open(_CONFIG_FILE) as f:
                data = json.load(f)
            cfg = cls()
            if "network" in data:
                cfg.network = NetworkConfig(**data["network"])
            if "slam" in data:
                cfg.slam = SlamConfig(**data["slam"])
            if "ros" in data:
                # Handle old config keys gracefully
                ros_data = data["ros"]
                ros_data.pop("domain_id", None)
                cfg.ros = RosConfig(**ros_data)
            if "rviz" in data:
                cfg.rviz = RVizConfig(**data["rviz"])
            if "ui" in data:
                cfg.ui = UIConfig(**data["ui"])
            return cfg
        except Exception:
            return cls()

    @property
    def cyclonedds_uri(self) -> str:
        """
        Single-line CYCLONEDDS_URI required for ROS2 to communicate with the robot.
        Must be one line — the XML parser silently rejects multi-line values.
        """
        iface = self.ros.cyclone_interface or self.network.network_interface
        return (
            f'<CycloneDDS><Domain><General><Interfaces>'
            f'<NetworkInterface name="{iface}" priority="default" multicast="default" />'
            f'</Interfaces></General></Domain></CycloneDDS>'
        )

    @property
    def ros_setup_path(self) -> str:
        """Return the best available ROS2 setup.bash path."""
        # Prefer explicit workspace setup if set
        if self.ros.workspace_setup and Path(self.ros.workspace_setup).exists():
            return self.ros.workspace_setup
        # Fall back to base ROS2 install
        distro = self.ros.distro or os.environ.get("ROS_DISTRO", "humble")
        base = Path(f"/opt/ros/{distro}/setup.bash")
        if base.exists():
            return str(base)
        return ""
