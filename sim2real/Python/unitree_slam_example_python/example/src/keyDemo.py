#!/usr/bin/env python3
"""
keyDemo.py — Clon Python exacto de example/src/keyDemo.cpp

Uso:
    python3 keyDemo.py enp2s0
"""

import json
import sys
import termios
import threading
import time
import tty
from copy import copy
from typing import List

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.std_msgs.msg.dds_._String_ import String_
from unitree_sdk2py.rpc.client import Client as RpcClient

# Mirrors: #define SlamInfoTopic / SlamKeyInfoTopic
SLAM_INFO_TOPIC     = "rt/slam_info"
SLAM_KEY_INFO_TOPIC = "rt/slam_key_info"

# Mirrors: namespace unitree::robot::slam constants
TEST_SERVICE_NAME = "slam_operate"
TEST_API_VERSION  = "1.0.0.1"

ROBOT_API_ID_STOP_NODE         = 1901
ROBOT_API_ID_START_MAPPING_PL  = 1801
ROBOT_API_ID_END_MAPPING_PL    = 1802
ROBOT_API_ID_START_RELOCATION_PL = 1804
ROBOT_API_ID_POSE_NAV_PL       = 1102
ROBOT_API_ID_PAUSE_NAV         = 1201
ROBOT_API_ID_RESUME_NAV        = 1202


# Mirrors: class poseDate
class PoseDate:
    def __init__(self):
        self.x   = 0.0
        self.y   = 0.0
        self.z   = 0.0
        self.q_x = 0.0
        self.q_y = 0.0
        self.q_z = 0.0
        self.q_w = 1.0
        self.mode = 1

    def toJsonStr(self) -> str:
        return json.dumps({
            "data": {
                "targetPose": {
                    "x":   self.x,   "y": self.y,   "z": self.z,
                    "q_x": self.q_x, "q_y": self.q_y,
                    "q_z": self.q_z, "q_w": self.q_w,
                },
                "mode": self.mode,
            }
        }, indent=4)

    def printInfo(self):
        print(f"x:{self.x} y:{self.y} z:{self.z} "
              f"q_x:{self.q_x} q_y:{self.q_y} q_z:{self.q_z} q_w:{self.q_w}")


# Mirrors: class TestClient : public Client
class TestClient:

    def __init__(self):
        self.curPose       = PoseDate()
        self.poseList: List[PoseDate] = []
        self.is_arrived    = False
        self.threadControl = False
        self._task_thread: threading.Thread = None

        # Mirrors: subSlamInfo / subSlamKeyInfo InitChannel
        self._sub_info = ChannelSubscriber(SLAM_INFO_TOPIC, String_)
        self._sub_info.Init(self.slamInfoHandler, 1)

        self._sub_key = ChannelSubscriber(SLAM_KEY_INFO_TOPIC, String_)
        self._sub_key.Init(self.slamKeyInfoHandler, 1)

        # Mirrors: Client(TEST_SERVICE_NAME, false)
        self._client = RpcClient(TEST_SERVICE_NAME, False)

        print("***********************  Unitree SLAM Demo ***********************")
        print("---------------            q    w                -----------------")
        print("---------------            a    s   d   f        -----------------")
        print("---------------            z    x                -----------------")
        print("------------------------------------------------------------------")
        print("------------------ q: Start mapping            -------------------")
        print("------------------ w: End mapping              -------------------")
        print("------------------ a: Start relocation         -------------------")
        print("------------------ s: Add pose to task list    -------------------")
        print("------------------ d: Execute task list        -------------------")
        print("------------------ f: Clear task list          -------------------")
        print("------------------ z: Pause navigation         -------------------")
        print("------------------ x: Resume navigation        -------------------")
        print("---------------- Press any other key to stop SLAM ----------------")
        print("------------------------------------------------------------------")
        print("------------------------------------------------------------------")
        print("--------------- Press 'Ctrl + C' to exit the program -------------")
        print("------------------------------------------------------------------")
        print("------------------------------------------------------------------")

    def __del__(self):
        self.stopNodeFun()

    # Mirrors: void Init()
    def Init(self):
        self._client._SetApiVerson(TEST_API_VERSION)
        for api_id in [
            ROBOT_API_ID_POSE_NAV_PL,
            ROBOT_API_ID_PAUSE_NAV,
            ROBOT_API_ID_RESUME_NAV,
            ROBOT_API_ID_STOP_NODE,
            ROBOT_API_ID_START_MAPPING_PL,
            ROBOT_API_ID_END_MAPPING_PL,
            ROBOT_API_ID_START_RELOCATION_PL,
        ]:
            self._client._RegistApi(api_id, 0)

    # Mirrors: SetTimeout
    def SetTimeout(self, timeout: float):
        self._client.SetTimeout(timeout)

    # Mirrors: int32_t Call(api_id, parameter, data)
    def _Call(self, api_id: int, parameter: str) -> tuple:
        ret, data = self._client._Call(api_id, parameter)
        print(f"statusCode:{ret}")
        print(f"data:{data}")
        return ret, data

    # Mirrors: void slamInfoHandler(const void *message)
    def slamInfoHandler(self, message) -> None:
        try:
            jsonData = json.loads(message.data)

            if jsonData["errorCode"] != 0:
                print(f"\033[33m{jsonData['info']}\033[0m")
                return

            if jsonData.get("type") == "pos_info":
                p = jsonData["data"]["currentPose"]
                self.curPose.x   = p["x"]
                self.curPose.y   = p["y"]
                self.curPose.z   = p["z"]
                self.curPose.q_x = p["q_x"]
                self.curPose.q_y = p["q_y"]
                self.curPose.q_z = p["q_z"]
                self.curPose.q_w = p["q_w"]
        except Exception:
            pass

    # Mirrors: void slamKeyInfoHandler(const void *message)
    def slamKeyInfoHandler(self, message) -> None:
        try:
            jsonData = json.loads(message.data)

            if jsonData["errorCode"] != 0:
                print(f"\033[33m{jsonData['info']}\033[0m")
                return

            if jsonData.get("type") == "task_result":
                self.is_arrived = jsonData["data"]["is_arrived"]
                if self.is_arrived:
                    print(f"I arrived {jsonData['data']['targetNodeName']}")
                else:
                    print(f"I not arrived {jsonData['data']['targetNodeName']}"
                          f"  Please help me!!  (T_T)   (T_T)   (T_T) ")
        except Exception:
            pass

    # Mirrors: void stopNodeFun()
    def stopNodeFun(self):
        parameter = '{"data": {}}'
        self._Call(ROBOT_API_ID_STOP_NODE, parameter)

    # Mirrors: void startMappingPlFun()
    def startMappingPlFun(self):
        parameter = '{"data": {"slam_type": "indoor"}}'
        self._Call(ROBOT_API_ID_START_MAPPING_PL, parameter)

    # Mirrors: void endMappingPlFun()
    def endMappingPlFun(self):
        parameter = '{"data": {"address": "/home/unitree/test.pcd"}}'
        self._Call(ROBOT_API_ID_END_MAPPING_PL, parameter)

    # Mirrors: void relocationPlFun()
    def relocationPlFun(self):
        parameter = json.dumps({"data": {
            "x": 0.0, "y": 0.0, "z": 0.0,
            "q_x": 0.0, "q_y": 0.0, "q_z": 0.0, "q_w": 1.0,
            "address": "/home/unitree/test.pcd",
        }})
        self._Call(ROBOT_API_ID_START_RELOCATION_PL, parameter)

    # Mirrors: void pauseNavFun()
    def pauseNavFun(self):
        self._Call(ROBOT_API_ID_PAUSE_NAV, '{"data": {}}')

    # Mirrors: void resumeNavFun()
    def resumeNavFun(self):
        self._Call(ROBOT_API_ID_RESUME_NAV, '{"data": {}}')

    # Mirrors: void taskThreadRun()
    def taskThreadRun(self):
        self.taskThreadStop()
        self.threadControl = True
        self._task_thread = threading.Thread(target=self.taskLoopFun, daemon=True)
        self._task_thread.start()

    # Mirrors: void taskLoopFun(std::promise<void> &prom)
    def taskLoopFun(self):
        print(f"task list num:{len(self.poseList)}")
        i = 0
        while i < len(self.poseList):
            self.is_arrived = False
            ret, data = self._client._Call(ROBOT_API_ID_POSE_NAV_PL,
                                           self.poseList[i].toJsonStr())
            print(f"parameter:{self.poseList[i].toJsonStr()}")
            print(f"statusCode:{ret}")
            print(f"data:{data}")

            while not self.is_arrived:
                time.sleep(0.005)
                if not self.threadControl:
                    break

            if i == len(self.poseList) - 1:
                i = 0
                self.poseList.reverse()
            else:
                i += 1

            if not self.threadControl:
                break

    # Mirrors: void taskThreadStop()
    def taskThreadStop(self):
        self.threadControl = False
        if self._task_thread and self._task_thread.is_alive():
            self._task_thread.join(timeout=2.0)

    # Mirrors: unsigned char keyDetection()
    def keyDetection(self) -> str:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print(f"\033[1;32mKey {ch} pressed.\033[0m")
        return ch

    # Mirrors: unsigned char keyExecute()
    def keyExecute(self):
        while True:
            currentKey = self.keyDetection()

            if currentKey == 'q':
                self.startMappingPlFun()
            elif currentKey == 'w':
                self.endMappingPlFun()
            elif currentKey == 'a':
                self.relocationPlFun()
            elif currentKey == 's':
                self.poseList.append(copy(self.curPose))
                self.curPose.printInfo()
            elif currentKey == 'd':
                self.taskThreadRun()
            elif currentKey == 'f':
                self.poseList.clear()
                print("Clear task list")
            elif currentKey == 'z':
                self.pauseNavFun()
            elif currentKey == 'x':
                self.resumeNavFun()
            elif currentKey == '\x03':  # Ctrl+C
                raise KeyboardInterrupt
            else:
                self.taskThreadStop()
                self.stopNodeFun()


# Mirrors: int main(int argc, const char **argv)
def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} networkInterface")
        sys.exit(-1)

    # Mirrors: ChannelFactory::Instance()->Init(0, argv[1])
    ChannelFactoryInitialize(0, sys.argv[1])

    tc = TestClient()
    tc.Init()
    tc.SetTimeout(10.0)

    try:
        tc.keyExecute()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
