"""User-contributed protocol for Huawei product A3D3 (美的洗碗机 S65Pro).

Profile（`device/guide/A3D3/A3D3.json`，deviceTypeId 078）+ 真机上报（2026-09-16）：
  switch.on            bool RW  1=开 0=关
  status.status        enum R   0待机 1工作中 3已暂停 100故障 101烘干中 102保管中 103预约中
                                104关机 105预约暂停 106烘干暂停 107保管暂停（真机 104）
  statusDoor.status    enum R   0=关闭 1=打开（真机 1）
  filterElement1/2     alarm bool R（有无告警）+ status（0缺少 1充足）+ name（真机：软水盐 / 光亮剂）
  washLeftTime.time    int  R   洗涤剩余（min）

暴露：switch + sensor（运行状态）+ binary_sensor（门）+ binary_sensor×2（耗材告警）+ sensor（洗涤剩余）。
耗材告警的名字取设备上报的 `name`，所以换机型也不会串。
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_STATUS_SID = "status"
_DOOR_SID = "statusDoor"
_FILTER_SIDS = ("filterElement1", "filterElement2")
_WASH_TIME_SID = "washLeftTime"


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


def _enum_map(profile: Any, sid: str, field: str) -> dict[str, str]:
    for service in (profile.get("services") or ()) if isinstance(profile, Mapping) else ():
        if not isinstance(service, Mapping) or service.get("serviceId") != sid:
            continue
        for ch in service.get("characteristics") or ():
            if isinstance(ch, Mapping) and ch.get("characteristicName") == field:
                return {
                    str(o.get("enumVal")): str(o.get("descCh") or o.get("enumVal"))
                    for o in (ch.get("enumList") or ())
                    if isinstance(o, Mapping)
                }
    return {}


class ProductA3D3Adapter:
    """A3D3 洗碗机：开关 / 状态 / 门 / 耗材 / 剩余时间。"""

    prod_id = "A3D3"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("switch"):
            return ()

        status_labels = _enum_map(context.profile, _STATUS_SID, "status")

        def switch_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"is_on": _flag(device.value("switch", "on"))}

        def status_state(device: DeviceContext) -> Mapping[str, Any]:
            code = _as_int(device.value(_STATUS_SID, "status"))
            if code is None:
                return {"native_value": None}
            return {"native_value": status_labels.get(str(code), str(code))}

        def door_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"is_on": _as_int(device.value(_DOOR_SID, "status")) == 1}

        def wash_time_state(device: DeviceContext) -> Mapping[str, Any]:
            minutes = _as_int(device.value(_WASH_TIME_SID, "time"))
            return {"native_value": None if minutes is None else float(minutes)}

        async def start(device: DeviceContext, _data: Mapping[str, Any]) -> None:
            """启动程序（`action.action` 1=启用）。

            2026-09-16 真机实测：**开机和启动分开是没问题的**；之前“启动没反应”是因为
            **没有先选程序**。而华为云这套 Profile **不含** 模式 / 温度 / 上下层 / 烘干 /
            存碗时间这些设置项（只有 switch + action + 各类只读状态），所以程序必须在
            智慧生活 App 里选好，之后这里的「启动」才有效。
            """
            await device.async_send_service("action", {"action": 1})


        async def pause(device: DeviceContext, _data: Mapping[str, Any]) -> None:
            await device.async_send_service("action", {"action": 2})


        async def cancel(device: DeviceContext, _data: Mapping[str, Any]) -> None:
            await device.async_send_service("action", {"action": 0})


        async def turn_on(device: DeviceContext, _data: Mapping[str, Any]) -> None:
            await device.async_send_service("switch", {"on": 1})

        async def turn_off(device: DeviceContext, _data: Mapping[str, Any]) -> None:
            await device.async_send_service("switch", {"on": 0})

        specs: list[EntitySpec] = [
            EntitySpec(
                platform="switch",
                key="switch",
                name=None,
                state=switch_state,
                actions={"turn_on": turn_on, "turn_off": turn_off},
            )
        ]

        if context.has_service("action"):
            specs.append(EntitySpec(platform="button", key="start", name="启动",
                                    state=lambda _device: {}, actions={"press": start}))
            specs.append(EntitySpec(platform="button", key="pause", name="暂停",
                                    state=lambda _device: {}, actions={"press": pause}))
            specs.append(EntitySpec(platform="button", key="cancel", name="取消",
                                    state=lambda _device: {}, actions={"press": cancel}))
        if context.has_service(_STATUS_SID):
            specs.append(
                EntitySpec(platform="sensor", key="status", name="运行状态", state=status_state)
            )
        if context.has_service(_DOOR_SID):
            specs.append(
                EntitySpec(platform="binary_sensor", key="door", name="门", state=door_state)
            )
        for sid in _FILTER_SIDS:
            if not context.has_service(sid):
                continue
            label = context.value(sid, "name")

            def alarm_state(device: DeviceContext, _sid: str = sid) -> Mapping[str, Any]:
                return {"is_on": _flag(device.value(_sid, "alarm"))}

            specs.append(
                EntitySpec(
                    platform="binary_sensor",
                    key=f"{sid}_alarm",
                    name=f"{label}告警" if label else sid.replace("filterElement", "耗材") + "告警",
                    state=alarm_state,
                )
            )
        if context.has_service(_WASH_TIME_SID):
            specs.append(
                EntitySpec(
                    platform="sensor",
                    key="wash_left",
                    name="洗涤剩余",
                    state=wash_time_state,
                    metadata={"unit": "min", "state_class": "measurement"},
                )
            )
        return tuple(specs)


ADAPTER = ProductA3D3Adapter()
