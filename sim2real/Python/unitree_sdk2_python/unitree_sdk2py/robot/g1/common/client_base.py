"""
unitree_sdk2py.robot.g1.common.client
Mirrors: unitree::robot::Client (base class)
"""
from __future__ import annotations
from unitree_sdk2py.rpc.client import Client as _RpcClient


class Client:
    """
    Base class mirroring unitree::robot::Client.

    Subclasses call:
        super().__init__(service_name)
        self.Init()   ← registers APIs
        self.SetTimeout(10.0)
    """

    def __init__(self, service_name: str):
        self._client = _RpcClient(service_name, False)
        self._apis_registered = False

    def SetApiVersion(self, version: str) -> None:
        """Mirrors: SetApiVersion(LOCO_API_VERSION)"""
        self._client._SetApiVerson(version)

    def RegisterApi(self, api_id: int) -> None:
        """Mirrors: UT_ROBOT_CLIENT_REG_API_NO_PROI(api_id)"""
        self._client._RegistApi(api_id, 0)

    def SetTimeout(self, timeout: float) -> None:
        """Mirrors: client.SetTimeout(10.f)"""
        self._client.SetTimeout(timeout)

    def Call(self, api_id: int, parameter: str = "", binary: bytes = None) -> tuple[int, str]:
        """
        Mirrors: int32_t ret = Call(api_id, parameter, data)
        Returns: (ret, data)
        """
        if binary is not None:
            ret, data = self._client._CallBinary(api_id, parameter, binary)
        else:
            ret, data = self._client._Call(api_id, parameter)
        return ret, data
