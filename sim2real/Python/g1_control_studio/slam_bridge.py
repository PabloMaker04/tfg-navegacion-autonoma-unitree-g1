#!/usr/bin/env python3
"""
SLAM Bridge — subprocess used by G1 Control Studio.

Launch via:
    LD_LIBRARY_PATH=/usr/local/lib python3 slam_bridge.py <network_interface>

stdin  → newline-terminated JSON commands
stdout → newline-terminated JSON events (flushed immediately)
stderr → raw SDK/DDS internal logs (not parsed by the UI)

This file intentionally has NO PySide6 or Qt imports.
All communication is plain stdin/stdout so the DDS environment is clean.
"""
import json
import sys
import threading
import time
from copy import copy
from typing import List, Optional


# ---------------------------------------------------------------------------
# Output protocol helpers
# ---------------------------------------------------------------------------

def emit(event_type: str, **kwargs) -> None:
    print(json.dumps({"type": event_type, **kwargs}), flush=True)


def emit_status(message: str, level: str = "info") -> None:
    emit("status", level=level, message=message)


# ---------------------------------------------------------------------------
# SLAM API constants — exact mirrors of keyDemo.py
# ---------------------------------------------------------------------------

SLAM_INFO_TOPIC     = "rt/slam_info"
SLAM_KEY_INFO_TOPIC = "rt/slam_key_info"
TEST_SERVICE_NAME   = "slam_operate"
TEST_API_VERSION    = "1.0.0.1"

API_STOP_NODE        = 1901
API_START_MAPPING    = 1801
API_END_MAPPING      = 1802
API_START_RELOCATION = 1804
API_POSE_NAV         = 1102
API_PAUSE_NAV        = 1201
API_RESUME_NAV       = 1202


class PoseDate:
    """Mirrors keyDemo.py::poseDate."""

    def __init__(self):
        self.x = self.y = self.z = 0.0
        self.q_x = self.q_y = self.q_z = 0.0
        self.q_w = 1.0
        self.mode = 1

    def to_nav_param(self) -> str:
        """JSON parameter for API_POSE_NAV — mirrors PoseDate.toJsonStr()."""
        return json.dumps({"data": {"targetPose": {
            "x": self.x, "y": self.y, "z": self.z,
            "q_x": self.q_x, "q_y": self.q_y,
            "q_z": self.q_z, "q_w": self.q_w,
        }, "mode": self.mode}})

    def as_dict(self) -> dict:
        return {
            "x": self.x, "y": self.y, "z": self.z,
            "q_x": self.q_x, "q_y": self.q_y,
            "q_z": self.q_z, "q_w": self.q_w,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PoseDate":
        p = cls()
        p.x   = float(d.get("x",   0.0))
        p.y   = float(d.get("y",   0.0))
        p.z   = float(d.get("z",   0.0))
        p.q_x = float(d.get("q_x", 0.0))
        p.q_y = float(d.get("q_y", 0.0))
        p.q_z = float(d.get("q_z", 0.0))
        p.q_w = float(d.get("q_w", 1.0))
        return p


class SlamBridge:
    """
    Wraps the unitree_sdk2py SLAM client with a stdin/stdout command interface.
    Mirrors the logic of TestClient in keyDemo.py.
    """

    def __init__(self, interface: str) -> None:
        self._interface    = interface
        self._client       = None
        self._cur_pose     = PoseDate()
        self._pose_list: List[PoseDate] = []
        self._pose_lock    = threading.Lock()
        self._task_thread: Optional[threading.Thread] = None
        self._task_running = False
        self._is_arrived   = False

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def init_sdk(self) -> bool:
        try:
            from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
            from unitree_sdk2py.idl.std_msgs.msg.dds_._String_ import String_
            from unitree_sdk2py.rpc.client import Client as RpcClient
        except ImportError as e:
            emit_status(
                f"Cannot import unitree_sdk2py: {e}\n"
                "Ensure it is installed: pip install unitree_sdk2py",
                "error",
            )
            return False

        # Mirrors: ChannelFactory::Instance()->Init(0, argv[1])
        try:
            ChannelFactoryInitialize(0, self._interface)
            emit_status(f"DDS channel initialized on {self._interface}.", "ok")
        except Exception as e:
            emit_status(f"DDS initialization failed: {e}", "error")
            return False

        # Subscribe to SLAM topics
        try:
            sub_info = ChannelSubscriber(SLAM_INFO_TOPIC, String_)
            sub_info.Init(self._slam_info_handler, 1)
            sub_key = ChannelSubscriber(SLAM_KEY_INFO_TOPIC, String_)
            sub_key.Init(self._slam_key_handler, 1)
            emit_status("Subscribed to slam_info and slam_key_info.", "ok")
        except Exception as e:
            emit_status(f"Topic subscription warning: {e}", "warn")

        # RPC client — mirrors: RpcClient(TEST_SERVICE_NAME, false)
        try:
            self._client = RpcClient(TEST_SERVICE_NAME, False)
            self._client._SetApiVerson(TEST_API_VERSION)
            for api_id in [
                API_POSE_NAV, API_PAUSE_NAV, API_RESUME_NAV,
                API_STOP_NODE, API_START_MAPPING, API_END_MAPPING,
                API_START_RELOCATION,
            ]:
                self._client._RegistApi(api_id, 0)
            self._client.SetTimeout(10.0)
            emit_status("SLAM RPC client ready.", "ok")
        except Exception as e:
            emit_status(f"SLAM client init failed: {e}", "error")
            return False

        emit("ready")
        return True

    # ------------------------------------------------------------------
    # DDS topic handlers
    # ------------------------------------------------------------------

    def _slam_info_handler(self, message) -> None:
        try:
            data = json.loads(message.data)
            if data.get("errorCode", -1) != 0:
                emit_status(data.get("info", "SLAM error"), "warn")
                return
            if data.get("type") == "pos_info":
                p = data["data"]["currentPose"]
                with self._pose_lock:
                    self._cur_pose.x   = p["x"]
                    self._cur_pose.y   = p["y"]
                    self._cur_pose.z   = p["z"]
                    self._cur_pose.q_x = p["q_x"]
                    self._cur_pose.q_y = p["q_y"]
                    self._cur_pose.q_z = p["q_z"]
                    self._cur_pose.q_w = p["q_w"]
                emit("pose", **self._cur_pose.as_dict())
        except Exception:
            pass

    def _slam_key_handler(self, message) -> None:
        try:
            data = json.loads(message.data)
            if data.get("errorCode", -1) != 0:
                emit_status(data.get("info", "SLAM key event error"), "warn")
                return
            if data.get("type") == "task_result":
                arrived   = data["data"].get("is_arrived", False)
                node_name = data["data"].get("targetNodeName", "")
                self._is_arrived = arrived
                emit("arrived", is_arrived=arrived, node_name=node_name)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # RPC helpers
    # ------------------------------------------------------------------

    def _call(self, api_id: int, parameter: str = '{"data": {}}') -> tuple:
        try:
            return self._client._Call(api_id, parameter)
        except Exception as e:
            return -1, str(e)

    def _emit_result(self, cmd: str, ret: int, raw_data: str) -> None:
        try:
            parsed = json.loads(raw_data) if raw_data else {}
        except Exception:
            parsed = {}
        succeed = bool(parsed.get("succeed", ret == 0))
        info    = parsed.get("info", raw_data or "No response from robot.")
        emit("api_result", cmd=cmd, ret=ret, succeed=succeed, info=info)

    # ------------------------------------------------------------------
    # Commands — mirrors keyDemo.py key actions
    # ------------------------------------------------------------------

    def start_mapping(self) -> None:
        emit_status("Starting SLAM mapping (indoor)…")
        ret, data = self._call(API_START_MAPPING, '{"data": {"slam_type": "indoor"}}')
        self._emit_result("start_mapping", ret, data)

    def end_mapping(self) -> None:
        emit_status("Saving map to /home/unitree/test.pcd on the robot…")
        ret, data = self._call(
            API_END_MAPPING,
            '{"data": {"address": "/home/unitree/test.pcd"}}',
        )
        self._emit_result("end_mapping", ret, data)

    def start_relocation(
        self,
        x: float = 0.0, y: float = 0.0, z: float = 0.0,
        q_x: float = 0.0, q_y: float = 0.0,
        q_z: float = 0.0, q_w: float = 1.0,
    ) -> None:
        emit_status("Starting relocation from last saved map…")
        param = json.dumps({"data": {
            "x": x, "y": y, "z": z,
            "q_x": q_x, "q_y": q_y, "q_z": q_z, "q_w": q_w,
            "address": "/home/unitree/test.pcd",
        }})
        ret, data = self._call(API_START_RELOCATION, param)
        self._emit_result("start_relocation", ret, data)

    def add_current_pose(self) -> None:
        with self._pose_lock:
            p = copy(self._cur_pose)
        self._pose_list.append(p)
        emit("pose_added", pose=p.as_dict(), count=len(self._pose_list))
        emit_status(
            f"Waypoint {len(self._pose_list)} added — "
            f"x={p.x:.3f} y={p.y:.3f} z={p.z:.3f}"
        )

    def clear_tasks(self) -> None:
        self._stop_task_thread()
        self._pose_list.clear()
        emit("tasks_cleared")
        emit_status("Waypoint list cleared.")

    def execute_tasks(self) -> None:
        if not self._pose_list:
            emit_status("No waypoints defined. Add waypoints first.", "error")
            return
        self._stop_task_thread()
        self._task_running = True
        self._task_thread = threading.Thread(
            target=self._task_loop, daemon=True
        )
        self._task_thread.start()
        emit_status(f"Executing {len(self._pose_list)} waypoints…")
        emit("nav_started", count=len(self._pose_list))

    def _task_loop(self) -> None:
        """Mirrors TestClient::taskLoopFun — navigates pose list, reverses at end."""
        i = 0
        while i < len(self._pose_list) and self._task_running:
            self._is_arrived = False
            pose = self._pose_list[i]
            emit("nav_targeting", index=i, pose=pose.as_dict())
            emit_status(
                f"Navigating to waypoint {i + 1}/{len(self._pose_list)}: "
                f"x={pose.x:.3f} y={pose.y:.3f}"
            )

            ret, data = self._client._Call(API_POSE_NAV, pose.to_nav_param())
            self._emit_result("pose_nav", ret, data)

            # Wait for arrival signal from slam_key_info topic
            while not self._is_arrived and self._task_running:
                time.sleep(0.05)

            if not self._task_running:
                break

            # At the last pose: reverse list and loop from start (mirrors keyDemo.py)
            if i == len(self._pose_list) - 1:
                self._pose_list.reverse()
                i = 0
                emit_status("End of waypoint list — reversing direction.")
            else:
                i += 1

        emit("nav_stopped")
        emit_status("Navigation task finished.")

    def _stop_task_thread(self) -> None:
        self._task_running = False
        if self._task_thread and self._task_thread.is_alive():
            self._task_thread.join(timeout=2.0)

    def pause_nav(self) -> None:
        ret, data = self._call(API_PAUSE_NAV)
        self._emit_result("pause_nav", ret, data)

    def resume_nav(self) -> None:
        ret, data = self._call(API_RESUME_NAV)
        self._emit_result("resume_nav", ret, data)

    def stop(self) -> None:
        self._stop_task_thread()
        ret, data = self._call(API_STOP_NODE)
        self._emit_result("stop", ret, data)

    def get_pose(self) -> None:
        with self._pose_lock:
            p = self._cur_pose
        emit("pose", **p.as_dict())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        emit_status("Usage: slam_bridge.py <network_interface>", "error")
        sys.exit(1)

    bridge = SlamBridge(sys.argv[1])
    if not bridge.init_sdk():
        sys.exit(1)

    try:
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                emit_status(f"Invalid JSON: {line!r}", "error")
                continue

            cmd = msg.get("cmd", "")

            if   cmd == "start_mapping":
                bridge.start_mapping()
            elif cmd == "end_mapping":
                bridge.end_mapping()
            elif cmd == "start_relocation":
                bridge.start_relocation(
                    msg.get("x", 0.0),   msg.get("y", 0.0),   msg.get("z", 0.0),
                    msg.get("q_x", 0.0), msg.get("q_y", 0.0),
                    msg.get("q_z", 0.0), msg.get("q_w", 1.0),
                )
            elif cmd == "add_current_pose":
                bridge.add_current_pose()
            elif cmd == "clear_tasks":
                bridge.clear_tasks()
            elif cmd == "execute_tasks":
                bridge.execute_tasks()
            elif cmd == "pause_nav":
                bridge.pause_nav()
            elif cmd == "resume_nav":
                bridge.resume_nav()
            elif cmd == "stop":
                bridge.stop()
            elif cmd == "get_pose":
                bridge.get_pose()
            elif cmd == "quit":
                emit_status("Bridge shutting down.")
                break
            else:
                emit_status(f"Unknown command: {cmd!r}", "error")

    except KeyboardInterrupt:
        pass

    emit_status("Bridge stopped.")


if __name__ == "__main__":
    main()
