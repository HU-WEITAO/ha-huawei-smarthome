"""User-contributed protocol for Huawei product X0A0 (华为 AI 音箱 FLMG-10).

设备类型: 华为 AI 音箱（FLMG-10；实测 2 台，左/右声道 stereo 配对）
制造商: 华为
Profile（profiles/X0A0.json）:
   smartspeaker.playControl enum RW  0=停止播放 1=启动播放 2=上一首/下一首
   audioplayer.playState  enum RW    0=暂停 1=播放中 2=停止
   speakerState.State     enum R     0=待机中 1=拾音中 2=等待响应 3=语音播报

本适配器暴露一个 media_player：播放 / 暂停 / 停止。
注: playControl=2 在资料里上一首与下一首**共用同一枚举值**，无法可靠区分 → 不暴露跳曲，
    避免误操作（同上游 X0A2 的处理）。音量字段在 X0A0 的 Profile 与真机上报里都不明确
    （`speaker` 只报 equalizer，`sleepHelp.volume` 是睡眠辅助音量）→ 不暴露音量。
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_STATE_PLAYING = "playing"
_STATE_PAUSED = "paused"
_STATE_IDLE = "idle"


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


async def _play(device: DeviceContext, _data: Mapping[str, Any]) -> None:
    await device.async_send_service("smartspeaker", {"playControl": 1})


async def _pause(device: DeviceContext, _data: Mapping[str, Any]) -> None:
    await device.async_send_service("audioplayer", {"playState": 0})


async def _stop(device: DeviceContext, _data: Mapping[str, Any]) -> None:
    await device.async_send_service("smartspeaker", {"playControl": 0})


class ProductX0A0Adapter:
    """X0A0 华为 AI 音箱：一个 media_player。"""

    prod_id = "X0A0"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("audioplayer"):
            return ()

        def player_state(device: DeviceContext) -> Mapping[str, Any]:
            code = _as_int(device.value("audioplayer", "playState"))
            if code == 1:
                state = _STATE_PLAYING
            elif code == 0:
                state = _STATE_PAUSED
            else:
                state = _STATE_IDLE
            return {"state": state}

        return (
            EntitySpec(
                platform="media_player",
                key="speaker",
                name=None,
                state=player_state,
                actions={"play": _play, "pause": _pause, "stop": _stop},
            ),
        )


ADAPTER = ProductX0A0Adapter()
