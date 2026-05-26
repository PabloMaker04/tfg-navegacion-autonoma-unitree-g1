"""
unitree_sdk2py.robot.g1.common.channel
Mirrors: unitree::robot::ChannelFactory::Instance()->Init(domain_id, interface)
"""
from __future__ import annotations
from unitree_sdk2py.core.channel import ChannelFactoryInitialize as _Init
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelPublisher


class ChannelFactory:
    """
    Mirrors: unitree::robot::ChannelFactory::Instance()

    Usage:
        ChannelFactory.Instance().Init(0, "enp2s0")
    """
    _instance = None

    @classmethod
    def Instance(cls) -> "ChannelFactory":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def Init(self, domain_id: int = 0, network_interface: str = "lo") -> None:
        """Mirrors: ChannelFactory::Instance()->Init(0, argv[1])"""
        _Init(domain_id, network_interface)
