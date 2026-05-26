"""
unitree_sdk2py.robot.g1.loco.g1_loco_client
Mirrors: include/unitree/robot/g1/loco/g1_loco_client.hpp

Every method name, signature and behaviour is identical to the C++ version.
"""
from __future__ import annotations

import json
import sys

from ..common.client_base import Client
from .g1_loco_api import (
    LOCO_SERVICE_NAME, LOCO_API_VERSION, InternalFsmMode,
    ROBOT_API_ID_LOCO_GET_FSM_ID,       ROBOT_API_ID_LOCO_GET_FSM_MODE,
    ROBOT_API_ID_LOCO_GET_BALANCE_MODE,  ROBOT_API_ID_LOCO_GET_SWING_HEIGHT,
    ROBOT_API_ID_LOCO_GET_STAND_HEIGHT,  ROBOT_API_ID_LOCO_GET_PHASE,
    ROBOT_API_ID_LOCO_SET_FSM_ID,        ROBOT_API_ID_LOCO_SET_BALANCE_MODE,
    ROBOT_API_ID_LOCO_SET_SWING_HEIGHT,  ROBOT_API_ID_LOCO_SET_STAND_HEIGHT,
    ROBOT_API_ID_LOCO_SET_VELOCITY,      ROBOT_API_ID_LOCO_SET_ARM_TASK,
    ROBOT_API_ID_LOCO_SET_SPEED_MODE,
    ROBOT_API_ID_LOCO_SWITCH_TO_USER_CTRL,
    ROBOT_API_ID_LOCO_SWITCH_TO_INTERNAL_CTRL,
)

# UINT32_MAX — same value used in HighStand() / LowStand()
_UINT32_MAX = 4294967295
_UINT32_MIN = 0


class LocoClient(Client):
    """
    Python mirror of unitree::robot::g1::LocoClient.

    Usage (identical to C++):
        client = LocoClient()
        client.Init()
        client.SetTimeout(10.0)
        client.Start()
        client.StandUp()
        client.Move(0.3, 0.0, 0.0)
    """

    def __init__(self):
        super().__init__(LOCO_SERVICE_NAME)
        self._continous_move = False          # mirrors continous_move_
        self._first_shake_hand_stage = True   # mirrors first_shake_hand_stage_

    # ── Init ──────────────────────────────────────────────────────────────

    def Init(self) -> None:
        """Mirrors: void Init()"""
        self.SetApiVersion(LOCO_API_VERSION)
        for api_id in [
            ROBOT_API_ID_LOCO_GET_FSM_ID,
            ROBOT_API_ID_LOCO_GET_FSM_MODE,
            ROBOT_API_ID_LOCO_GET_BALANCE_MODE,
            ROBOT_API_ID_LOCO_GET_SWING_HEIGHT,
            ROBOT_API_ID_LOCO_GET_STAND_HEIGHT,
            ROBOT_API_ID_LOCO_GET_PHASE,
            ROBOT_API_ID_LOCO_SET_FSM_ID,
            ROBOT_API_ID_LOCO_SET_BALANCE_MODE,
            ROBOT_API_ID_LOCO_SET_SWING_HEIGHT,
            ROBOT_API_ID_LOCO_SET_STAND_HEIGHT,
            ROBOT_API_ID_LOCO_SET_VELOCITY,
            ROBOT_API_ID_LOCO_SET_ARM_TASK,
            ROBOT_API_ID_LOCO_SET_SPEED_MODE,
            ROBOT_API_ID_LOCO_SWITCH_TO_USER_CTRL,
            ROBOT_API_ID_LOCO_SWITCH_TO_INTERNAL_CTRL,
        ]:
            self.RegisterApi(api_id)

    # ── Low Level API — GET ───────────────────────────────────────────────

    def GetFsmId(self) -> tuple[int, int]:
        """
        Mirrors: int32_t GetFsmId(int& fsm_id)
        Returns: (ret, fsm_id)
        """
        ret, data = self.Call(ROBOT_API_ID_LOCO_GET_FSM_ID)
        fsm_id = json.loads(data).get("data", 0) if ret == 0 else 0
        return ret, fsm_id

    def GetFsmMode(self) -> tuple[int, int]:
        """Returns: (ret, fsm_mode)"""
        ret, data = self.Call(ROBOT_API_ID_LOCO_GET_FSM_MODE)
        fsm_mode = json.loads(data).get("data", 0) if ret == 0 else 0
        return ret, fsm_mode

    def GetBalanceMode(self) -> tuple[int, int]:
        """Returns: (ret, balance_mode)"""
        ret, data = self.Call(ROBOT_API_ID_LOCO_GET_BALANCE_MODE)
        balance_mode = json.loads(data).get("data", 0) if ret == 0 else 0
        return ret, balance_mode

    def GetSwingHeight(self) -> tuple[int, float]:
        """Returns: (ret, swing_height)"""
        ret, data = self.Call(ROBOT_API_ID_LOCO_GET_SWING_HEIGHT)
        swing_height = float(json.loads(data).get("data", 0.0)) if ret == 0 else 0.0
        return ret, swing_height

    def GetStandHeight(self) -> tuple[int, float]:
        """Returns: (ret, stand_height)"""
        ret, data = self.Call(ROBOT_API_ID_LOCO_GET_STAND_HEIGHT)
        stand_height = float(json.loads(data).get("data", 0.0)) if ret == 0 else 0.0
        return ret, stand_height

    def GetPhase(self) -> tuple[int, list]:
        """Returns: (ret, phase_list)"""
        ret, data = self.Call(ROBOT_API_ID_LOCO_GET_PHASE)
        phase = json.loads(data).get("data", []) if ret == 0 else []
        return ret, phase

    # ── Low Level API — SET ───────────────────────────────────────────────

    def SetFsmId(self, fsm_id: int) -> int:
        """Mirrors: int32_t SetFsmId(int fsm_id)"""
        ret, _ = self.Call(ROBOT_API_ID_LOCO_SET_FSM_ID,
                           json.dumps({"data": fsm_id}))
        return ret

    def SetBalanceMode(self, balance_mode: int) -> int:
        """Mirrors: int32_t SetBalanceMode(int balance_mode)"""
        ret, _ = self.Call(ROBOT_API_ID_LOCO_SET_BALANCE_MODE,
                           json.dumps({"data": balance_mode}))
        return ret

    def SetSwingHeight(self, swing_height: float) -> int:
        """Mirrors: int32_t SetSwingHeight(float swing_height)"""
        ret, _ = self.Call(ROBOT_API_ID_LOCO_SET_SWING_HEIGHT,
                           json.dumps({"data": swing_height}))
        return ret

    def SetStandHeight(self, stand_height: float) -> int:
        """Mirrors: int32_t SetStandHeight(float stand_height)"""
        ret, _ = self.Call(ROBOT_API_ID_LOCO_SET_STAND_HEIGHT,
                           json.dumps({"data": stand_height}))
        return ret

    def SetVelocity(self, vx: float, vy: float, omega: float,
                    duration: float = 1.0) -> int:
        """Mirrors: int32_t SetVelocity(float vx, float vy, float omega, float duration=1.f)"""
        ret, _ = self.Call(ROBOT_API_ID_LOCO_SET_VELOCITY, json.dumps({
            "velocity": [vx, vy, omega],
            "duration": duration,
        }))
        return ret

    def SetTaskId(self, task_id: int) -> int:
        """Mirrors: int32_t SetTaskId(int task_id)"""
        ret, _ = self.Call(ROBOT_API_ID_LOCO_SET_ARM_TASK,
                           json.dumps({"data": task_id}))
        return ret

    def SetSpeedMode(self, speed_mode: int) -> int:
        """Mirrors: int32_t SetSpeedMode(int speed_mode)"""
        ret, _ = self.Call(ROBOT_API_ID_LOCO_SET_SPEED_MODE,
                           json.dumps({"data": speed_mode}))
        return ret

    def SwitchToUserCtrl(self) -> int:
        """Mirrors: int32_t SwitchToUserCtrl()"""
        ret, _ = self.Call(ROBOT_API_ID_LOCO_SWITCH_TO_USER_CTRL,
                           json.dumps({"data": False}))
        return ret

    def SwitchToInternalCtrl(self, mode: int) -> int:
        """
        Mirrors: int32_t SwitchToInternalCtrl(InternalFsmMode mode)
        mode: InternalFsmMode.LAST | PASSIVE | WALKRUN
        """
        ret, _ = self.Call(ROBOT_API_ID_LOCO_SWITCH_TO_INTERNAL_CTRL,
                           json.dumps({"data": mode}))
        return ret

    # ── High Level API ────────────────────────────────────────────────────

    def Damp(self) -> int:
        """Mirrors: int32_t Damp() { return SetFsmId(1); }"""
        return self.SetFsmId(1)

    def Start(self) -> int:
        """Mirrors: int32_t Start() { return SetFsmId(500); }"""
        return self.SetFsmId(500)

    def Squat(self) -> int:
        """Mirrors: int32_t Squat() { return SetFsmId(2); }"""
        return self.SetFsmId(2)

    def Sit(self) -> int:
        """Mirrors: int32_t Sit() { return SetFsmId(3); }"""
        return self.SetFsmId(3)

    def StandUp(self) -> int:
        """Mirrors: int32_t StandUp() { return SetFsmId(4); }"""
        return self.SetFsmId(4)

    def ZeroTorque(self) -> int:
        """Mirrors: int32_t ZeroTorque() { return SetFsmId(0); }"""
        return self.SetFsmId(0)

    def StopMove(self) -> int:
        """Mirrors: int32_t StopMove() { return SetVelocity(0,0,0); }"""
        return self.SetVelocity(0.0, 0.0, 0.0)

    def HighStand(self) -> int:
        """Mirrors: int32_t HighStand() { return SetStandHeight(UINT32_MAX); }"""
        return self.SetStandHeight(float(_UINT32_MAX))

    def LowStand(self) -> int:
        """Mirrors: int32_t LowStand() { return SetStandHeight(UINT32_MIN); }"""
        return self.SetStandHeight(float(_UINT32_MIN))

    def Move(self, vx: float, vy: float, vyaw: float,
             continous_move: bool = None) -> int:
        """
        Mirrors: int32_t Move(float vx, float vy, float vyaw, bool continous_move)
                          int32_t Move(float vx, float vy, float vyaw)
        """
        if continous_move is None:
            continous_move = self._continous_move
        duration = 864000.0 if continous_move else 1.0
        return self.SetVelocity(vx, vy, vyaw, duration)

    def BalanceStand(self) -> int:
        """Mirrors: int32_t BalanceStand() { return SetBalanceMode(0); }"""
        return self.SetBalanceMode(0)

    def ContinuousGait(self, flag: bool) -> int:
        """Mirrors: int32_t ContinuousGait(bool flag)"""
        return self.SetBalanceMode(1 if flag else 0)

    def SwitchMoveMode(self, flag: bool) -> int:
        """Mirrors: int32_t SwitchMoveMode(bool flag)"""
        self._continous_move = flag
        return 0

    def WaveHand(self, turn_flag: bool = False) -> int:
        """Mirrors: int32_t WaveHand(bool turn_flag=false)"""
        return self.SetTaskId(1 if turn_flag else 0)

    def ShakeHand(self, stage: int = -1) -> int:
        """
        Mirrors: int32_t ShakeHand(int stage=-1)
        stage=0: start, stage=1: end, stage=-1: toggle
        """
        if stage == 0:
            self._first_shake_hand_stage = False
            return self.SetTaskId(2)
        elif stage == 1:
            self._first_shake_hand_stage = True
            return self.SetTaskId(3)
        else:
            self._first_shake_hand_stage = not self._first_shake_hand_stage
            return self.SetTaskId(3 if self._first_shake_hand_stage else 2)
