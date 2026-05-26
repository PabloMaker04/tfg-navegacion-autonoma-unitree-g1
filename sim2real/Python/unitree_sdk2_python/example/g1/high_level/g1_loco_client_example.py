#!/usr/bin/env python3
"""
g1_loco_client_example.py
Mirrors: example/g1/high_level/g1_loco_client_example.cpp

Uso:
    python3 g1_loco_client_example.py --network_interface=enp2s0 --start
    python3 g1_loco_client_example.py --network_interface=enp2s0 --stand_up
    python3 g1_loco_client_example.py --network_interface=enp2s0 --move="0.3 0 0"
    python3 g1_loco_client_example.py --network_interface=enp2s0 --get_fsm_id

Comandos disponibles (igual que el C++):
    --get_fsm_id
    --get_fsm_mode
    --get_balance_mode
    --get_swing_height
    --get_stand_height
    --get_phase
    --set_fsm_id=N
    --set_balance_mode=N
    --set_swing_height=F
    --set_stand_height=F
    --set_velocity="vx vy omega [duration]"
    --damp
    --start
    --squat
    --sit
    --stand_up
    --zero_torque
    --stop_move
    --high_stand
    --low_stand
    --balance_stand
    --continous_gait=true|false
    --switch_move_mode=true|false
    --move="vx vy omega"
    --set_task_id=N
    --shake_hand
    --wave_hand
    --wave_hand_with_turn
    --set_speed_mode=N
"""

import sys
import time

sys.path.insert(0, "../../..")  # para importar unitree_sdk2py local si es necesario

from unitree_sdk2py.robot.g1.common.channel import ChannelFactory
from unitree_sdk2py.robot.g1.loco.g1_loco_client import LocoClient
from unitree_sdk2py.robot.g1.loco.g1_loco_api import InternalFsmMode


def string_to_float_vector(s: str) -> list:
    return [float(x) for x in s.split()]


def main():
    # Parsear argumentos — idéntico al C++
    args = {"network_interface": "lo"}

    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            if "=" in arg:
                key, value = arg[2:].split("=", 1)
                value = value.strip('"').strip("'")
            else:
                key  = arg[2:]
                value = ""
            args[key] = value

    ChannelFactory.Instance().Init(0, args["network_interface"])

    client = LocoClient()
    client.Init()
    client.SetTimeout(10.0)

    for key, value in args.items():
        print(f"Processing command: [{key}] with param: [{value}] ...")

        if key == "network_interface":
            continue

        if key == "get_fsm_id":
            ret, fsm_id = client.GetFsmId()
            print(f"current fsm_id: {fsm_id}")

        elif key == "get_fsm_mode":
            ret, fsm_mode = client.GetFsmMode()
            print(f"current fsm_mode: {fsm_mode}")

        elif key == "get_balance_mode":
            ret, balance_mode = client.GetBalanceMode()
            print(f"current balance_mode: {balance_mode}")

        elif key == "get_swing_height":
            ret, swing_height = client.GetSwingHeight()
            print(f"current swing_height: {swing_height}")

        elif key == "get_stand_height":
            ret, stand_height = client.GetStandHeight()
            print(f"current stand_height: {stand_height}")

        elif key == "get_phase":
            ret, phase = client.GetPhase()
            print(f"current phase: ({', '.join(str(p) for p in phase)})")

        elif key == "set_fsm_id":
            client.SetFsmId(int(value))
            print(f"set fsm_id to {value}")

        elif key == "set_balance_mode":
            client.SetBalanceMode(int(value))
            print(f"set balance_mode to {value}")

        elif key == "set_swing_height":
            client.SetSwingHeight(float(value))
            print(f"set swing_height to {value}")

        elif key == "set_stand_height":
            client.SetStandHeight(float(value))
            print(f"set stand_height to {value}")

        elif key == "set_velocity":
            param = string_to_float_vector(value)
            if len(param) == 3:
                vx, vy, omega, duration = param[0], param[1], param[2], 1.0
            elif len(param) == 4:
                vx, vy, omega, duration = param[0], param[1], param[2], param[3]
            else:
                print(f"Invalid param size for method SetVelocity: {len(param)}", file=sys.stderr)
                return 1
            client.SetVelocity(vx, vy, omega, duration)
            print(f"set velocity to {value}")

        elif key == "damp":
            client.Damp()

        elif key == "start":
            client.Start()

        elif key == "squat":
            client.Squat()

        elif key == "sit":
            client.Sit()

        elif key == "stand_up":
            client.StandUp()

        elif key == "zero_torque":
            client.ZeroTorque()

        elif key == "stop_move":
            client.StopMove()

        elif key == "high_stand":
            client.HighStand()

        elif key == "low_stand":
            client.LowStand()

        elif key == "balance_stand":
            client.BalanceStand()

        elif key == "continous_gait":
            if value == "true":
                flag = True
            elif value == "false":
                flag = False
            else:
                print(f"invalid argument: {value}", file=sys.stderr)
                return 1
            client.ContinuousGait(flag)

        elif key == "switch_move_mode":
            if value == "true":
                flag = True
            elif value == "false":
                flag = False
            else:
                print(f"invalid argument: {value}", file=sys.stderr)
                return 1
            client.SwitchMoveMode(flag)

        elif key == "move":
            param = string_to_float_vector(value)
            if len(param) != 3:
                print(f"Invalid param size for method Move: {len(param)}", file=sys.stderr)
                return 1
            client.Move(param[0], param[1], param[2])

        elif key == "set_task_id":
            client.SetTaskId(int(value))
            print(f"set task_id to {value}")

        elif key == "shake_hand":
            client.ShakeHand(0)
            print("Shake hand starts! Waiting for 10 s for ending")
            time.sleep(10)
            print("Shake hand ends!")
            client.ShakeHand(1)

        elif key == "wave_hand":
            client.WaveHand()
            print("wave hand")

        elif key == "wave_hand_with_turn":
            client.WaveHand(True)
            print("wave hand with turn")

        elif key == "set_speed_mode":
            client.SetSpeedMode(int(value))
            print("set speed mode")

        print("Done!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
