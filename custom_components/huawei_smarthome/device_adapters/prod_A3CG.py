"""User-contributed protocol for Huawei product A3CG (美的 干衣机 TH100-H09WZ).

Profile（profiles/A3CG.json）+ 真机上报（2026-09-16）：
  switch.on            bool RW  1=开 0=关
  mode.mode            enum RW  1=混合 2=棉麻 100=智能
  action.action        enum RW  1=启动 2=暂停   ← 与 switch 语义重叠（两个开关会打架），不暴露
  status.status        enum R   1=预约运行中 2=预约中 3=异常 4=待机 5=运行中 6=运行结束 7=暂停中
  leftTime.time        int  R   剩余时间（秒）
  faultDetection.status/code R  运行正常 / 异常

暴露：switch（开关）+ select（模式）+ sensor（运行状态）+ sensor（剩余分钟）。
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_MODE_LABELS = {1: "混合", 2: "棉麻", 100: "智能"}
_STATUS_LABELS = {
    1: "预约运行中",
    2: "预约中",
    3: "异常状态",
    4: "待机中",
    5: "运行中",
    6: "运行结束",
    7: "暂停中",
}


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        try:
            return int(round(float(value.strip())))
        except (TypeError, ValueError):
            return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _flag(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.casefold() in {"1", "true", "on"}:
            return True
        if value.casefold() in {"0", "false", "off"}:
            return False
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    return None


async def _start(device: DeviceContext, _data: Mapping[str, Any]) -> None:
    """启动程序（Profile: `action.action` 1=启动 2=暂停）。"""
    await device.async_send_service("action", {"action": 1})


async def _pause(device: DeviceContext, _data: Mapping[str, Any]) -> None:
    await device.async_send_service("action", {"action": 2})


async def _turn_on(device: DeviceContext, _data: Mapping[str, Any]) -> None:
    await device.async_send_service("switch", {"on": 1})


async def _turn_off(device: DeviceContext, _data: Mapping[str, Any]) -> None:
    await device.async_send_service("switch", {"on": 0})


async def _set_mode(device: DeviceContext, data: Mapping[str, Any]) -> None:
    label = str(data.get("option"))
    value = next((v for v, l in _MODE_LABELS.items() if l == label), None)
    if value is None:
        raise ValueError(f"unsupported dryer mode: {label}")
    await device.async_send_service("mode", {"mode": value})


class ProductA3CGAdapter:
    """A3CG 干衣机：开关 + 模式 + 状态 + 剩余时间。"""

    prod_id = "A3CG"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("switch"):
            return ()

        def switch_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"is_on": _flag(device.value("switch", "on"))}

        def mode_state(device: DeviceContext) -> Mapping[str, Any]:
            code = _as_int(device.value("mode", "mode"))
            return {"current_option": _MODE_LABELS.get(code) if code is not None else None}

        def status_state(device: DeviceContext) -> Mapping[str, Any]:
            code = _as_int(device.value("status", "status"))
            return {"native_value": _STATUS_LABELS.get(code) if code is not None else None}

        def left_time_state(device: DeviceContext) -> Mapping[str, Any]:
            seconds = _as_int(device.value("leftTime", "time"))
            return {"native_value": None if seconds is None else float(seconds // 60)}

        specs: list[EntitySpec] = [
            EntitySpec(
                platform="switch",
                key="switch",
                name=None,
                state=switch_state,
                actions={"turn_on": _turn_on, "turn_off": _turn_off},
            )
        ]

        if context.has_service("action"):
            specs.append(EntitySpec(platform="button", key="start", name="启动",
                                    state=lambda _device: {}, actions={"press": _start}))
            specs.append(EntitySpec(platform="button", key="pause", name="暂停",
                                    state=lambda _device: {}, actions={"press": _pause}))
        if context.has_service("mode"):
            specs.append(
                EntitySpec(
                    platform="select",
                    key="mode",
                    name="模式",
                    state=mode_state,
                    metadata={"options": list(_MODE_LABELS.values())},
                    actions={"select_option": _set_mode},
                )
            )
        if context.has_service("status"):
            specs.append(
                EntitySpec(platform="sensor", key="status", name="运行状态", state=status_state)
            )
        if context.has_service("leftTime"):
            specs.append(
                EntitySpec(
                    platform="sensor",
                    key="left_time",
                    name="剩余时间",
                    state=left_time_state,
                    metadata={"unit": "min", "state_class": "measurement"},
                )
            )
        return tuple(specs)


ADAPTER = ProductA3CGAdapter()
