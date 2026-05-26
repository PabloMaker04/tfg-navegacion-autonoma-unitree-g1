"""
unitree_sdk2py.robot.g1.audio.g1_audio_client
Mirrors: include/unitree/robot/g1/audio/g1_audio_client.hpp
"""
from __future__ import annotations

import json

from ..common.client_base import Client
from .g1_audio_api import (
    AUDIO_SERVICE_NAME, AUDIO_API_VERSION,
    ROBOT_API_ID_AUDIO_TTS,        ROBOT_API_ID_AUDIO_ASR,
    ROBOT_API_ID_AUDIO_START_PLAY, ROBOT_API_ID_AUDIO_STOP_PLAY,
    ROBOT_API_ID_AUDIO_GET_VOLUME, ROBOT_API_ID_AUDIO_SET_VOLUME,
    ROBOT_API_ID_AUDIO_SET_RGB_LED,
)


class AudioClient(Client):
    """
    Python mirror of unitree::robot::g1::AudioClient.

    Usage (identical to C++):
        client = AudioClient()
        client.Init()
        client.SetTimeout(10.0)
        client.TtsMaker("你好", 0)
        client.SetVolume(80)
        client.LedControl(0, 255, 0)
    """

    def __init__(self):
        super().__init__(AUDIO_SERVICE_NAME)
        self._tts_index = 0   # mirrors tts_index++

    def Init(self) -> None:
        """Mirrors: void Init()"""
        self.SetApiVersion(AUDIO_API_VERSION)
        for api_id in [
            ROBOT_API_ID_AUDIO_TTS,
            ROBOT_API_ID_AUDIO_ASR,
            ROBOT_API_ID_AUDIO_START_PLAY,
            ROBOT_API_ID_AUDIO_STOP_PLAY,
            ROBOT_API_ID_AUDIO_GET_VOLUME,
            ROBOT_API_ID_AUDIO_SET_VOLUME,
            ROBOT_API_ID_AUDIO_SET_RGB_LED,
        ]:
            self.RegisterApi(api_id)

    def TtsMaker(self, text: str, speaker_id: int) -> int:
        """
        Mirrors: int32_t TtsMaker(const std::string& text, int32_t speaker_id)
        speaker_id: 0=auto/Chinese, 1=English
        """
        param = json.dumps({
            "index":      self._tts_index,
            "text":       text,
            "speaker_id": speaker_id,
        })
        self._tts_index += 1
        ret, _ = self.Call(ROBOT_API_ID_AUDIO_TTS, param)
        return ret

    def GetVolume(self) -> tuple[int, int]:
        """
        Mirrors: int32_t GetVolume(uint8_t& volume)
        Returns: (ret, volume)
        """
        ret, data = self.Call(ROBOT_API_ID_AUDIO_GET_VOLUME)
        volume = 0
        if ret == 0:
            try:
                volume = int(json.loads(data).get("value", 0))
            except Exception:
                pass
        return ret, volume

    def SetVolume(self, volume: int) -> int:
        """Mirrors: int32_t SetVolume(uint8_t volume)"""
        param = json.dumps({"name": "volume", "value": int(volume)})
        ret, _ = self.Call(ROBOT_API_ID_AUDIO_SET_VOLUME, param)
        return ret

    def PlayStream(self, app_name: str, stream_id: str,
                   pcm_data: bytes) -> int:
        """
        Mirrors: int32_t PlayStream(string app_name, string stream_id, vector<uint8_t> pcm_data)
        """
        param = json.dumps({"app_name": app_name, "stream_id": stream_id})
        ret, _ = self.Call(ROBOT_API_ID_AUDIO_START_PLAY, param, binary=pcm_data)
        return ret

    def PlayStop(self, app_name: str) -> int:
        """Mirrors: int32_t PlayStop(string app_name)"""
        param = json.dumps({"app_name": app_name})
        ret, _ = self.Call(ROBOT_API_ID_AUDIO_STOP_PLAY, param)
        return ret

    def LedControl(self, r: int, g: int, b: int) -> int:
        """Mirrors: int32_t LedControl(uint8_t R, uint8_t G, uint8_t B)"""
        param = json.dumps({"R": int(r), "G": int(g), "B": int(b)})
        ret, _ = self.Call(ROBOT_API_ID_AUDIO_SET_RGB_LED, param)
        return ret
