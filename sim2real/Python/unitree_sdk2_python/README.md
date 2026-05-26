# unitree_sdk2_python — G1

Espejo Python exacto del SDK C++ `unitree_sdk2`, solo para el G1.

## Estructura (idéntica al C++)

```
unitree_sdk2py/
└── robot/g1/
    ├── loco/
    │   ├── g1_loco_api.py       ← g1_loco_api.hpp
    │   └── g1_loco_client.py    ← g1_loco_client.hpp
    ├── audio/
    │   ├── g1_audio_api.py      ← g1_audio_api.hpp
    │   └── g1_audio_client.py   ← g1_audio_client.hpp
    └── common/
        ├── channel.py           ← ChannelFactory::Instance()->Init()
        └── client_base.py       ← unitree::robot::Client

example/g1/
    ├── high_level/
    │   └── g1_loco_client_example.py   ← g1_loco_client_example.cpp
    └── audio/
        └── g1_audio_client_example.py  ← g1_audio_client_example.cpp
```

## Instalación

```bash
pip install -e .
```

## Uso — idéntico al C++

### C++
```cpp
ChannelFactory::Instance()->Init(0, argv[1]);
LocoClient client;
client.Init();
client.SetTimeout(10.f);
client.Start();
client.StandUp();
client.Move(0.3f, 0.f, 0.f);
```

### Python
```python
from unitree_sdk2py.robot.g1.common.channel import ChannelFactory
from unitree_sdk2py.robot.g1.loco.g1_loco_client import LocoClient

ChannelFactory.Instance().Init(0, "enp2s0")
client = LocoClient()
client.Init()
client.SetTimeout(10.0)
client.Start()
client.StandUp()
client.Move(0.3, 0.0, 0.0)
```

## Ejemplo (igual que el binario C++)

```bash
python3 example/g1/high_level/g1_loco_client_example.py \
    --network_interface=enp2s0 --start

python3 example/g1/high_level/g1_loco_client_example.py \
    --network_interface=enp2s0 --stand_up

python3 example/g1/high_level/g1_loco_client_example.py \
    --network_interface=enp2s0 --move="0.3 0 0"

python3 example/g1/high_level/g1_loco_client_example.py \
    --network_interface=enp2s0 --get_fsm_id
```

## Métodos LocoClient

| Python | C++ |
|--------|-----|
| `GetFsmId()` → `(ret, fsm_id)` | `GetFsmId(int& fsm_id)` |
| `GetBalanceMode()` → `(ret, mode)` | `GetBalanceMode(int& mode)` |
| `SetFsmId(n)` | `SetFsmId(int fsm_id)` |
| `SetVelocity(vx, vy, omega, dur)` | `SetVelocity(...)` |
| `Damp()` | `Damp()` |
| `Start()` | `Start()` |
| `StandUp()` | `StandUp()` |
| `Sit()` | `Sit()` |
| `Squat()` | `Squat()` |
| `ZeroTorque()` | `ZeroTorque()` |
| `StopMove()` | `StopMove()` |
| `HighStand()` | `HighStand()` |
| `LowStand()` | `LowStand()` |
| `Move(vx, vy, vyaw)` | `Move(vx, vy, vyaw)` |
| `BalanceStand()` | `BalanceStand()` |
| `ContinuousGait(flag)` | `ContinuousGait(bool)` |
| `SwitchMoveMode(flag)` | `SwitchMoveMode(bool)` |
| `WaveHand(turn=False)` | `WaveHand(bool)` |
| `ShakeHand(stage=-1)` | `ShakeHand(int)` |
| `SetSpeedMode(n)` | `SetSpeedMode(int)` |
| `SwitchToUserCtrl()` | `SwitchToUserCtrl()` |
| `SwitchToInternalCtrl(mode)` | `SwitchToInternalCtrl(InternalFsmMode)` |
