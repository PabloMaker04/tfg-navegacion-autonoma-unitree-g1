#!/usr/bin/env python3
"""
g1_audio_client_example.py
Mirrors: example/g1/audio/g1_audio_client_example.cpp

Uso:
    python3 g1_audio_client_example.py enp2s0
"""

import sys
import time

sys.path.insert(0, "../../..")

from unitree_sdk2py.robot.g1.common.channel import ChannelFactory
from unitree_sdk2py.robot.g1.audio.g1_audio_client import AudioClient


def main():
    if len(sys.argv) < 2:
        print(f"Usage: audio_client_example [NetWorkInterface(eth0)]")
        sys.exit(0)

    ChannelFactory.Instance().Init(0, sys.argv[1])

    client = AudioClient()
    client.Init()
    client.SetTimeout(10.0)

    # Volume Example
    ret, volume = client.GetVolume()
    print(f"GetVolume API ret:{ret}  volume = {volume}")

    ret = client.SetVolume(100)
    print(f"SetVolume to 100% , API ret:{ret}")

    # TTS Example
    ret = client.TtsMaker("你好。我是宇树科技的机器人。例程启动成功", 0)
    print(f"TtsMaker API ret:{ret}")
    time.sleep(5)

    ret = client.TtsMaker(
        "Hello. I'm a robot from Unitree Robotics. The example has started successfully. ",
        1
    )
    print(f"TtsMaker API ret:{ret}")
    time.sleep(8)

    # LED Control Example
    client.LedControl(0, 255, 0)
    time.sleep(1)
    client.LedControl(0, 0, 0)
    time.sleep(1)
    client.LedControl(0, 0, 255)

    print("AudioClient api test finish")


if __name__ == "__main__":
    main()
