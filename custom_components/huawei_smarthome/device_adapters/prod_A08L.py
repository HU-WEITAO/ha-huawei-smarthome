"""User-contributed protocol for Huawei product A08L (美的智能冰箱 BCD-609WKGPZM(E)).

Profile（`device/guide/A08L/A08L.json`，deviceTypeId 08A）+ 真机上报（2026-09-16）：
  refrigerator.target      int  RW  2~8   冷藏设定温度（真机 5 ℃）
  freezer.target           int  RW  -24~0 冷冻设定温度（真机 -18 ℃）
  intelligentSwitch.on     bool RW  智能模式（真机 0）
  switch.on / refrigerateSwitch.on / freezeSwitch.on  bool RW  整机/冷藏/冷冻开关

暴露：number（冷藏温度）+ number（冷冻温度）+ switch（智能模式）。

⚠️ **故意不暴露** `switch.on`（整机电源）与冷藏/冷冻分开关 —— Profile 给了字段，但误触等于给冰箱断电、
   食物会坏；如需整机电源开关，应由使用者明确需要后再加。
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_CHILL_MIN, _CHILL_MAX = 2.0, 8.0
_FREEZE_MIN, _FREEZE_MAX = -24.0, 0.0


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


def _empty_state(_device: DeviceContext) -> Mapping[str, Any]:
    return {}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class ProductA08LAdapter:
    """A08L 冰箱：两个温度设定 + 智能模式。"""

    prod_id = "A08L"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("refrigerator"):
            return ()

        def _temp(device: DeviceContext, float_sid: str, plain_sid: str) -> float | None:
            """优先读 `*Float`：真机实测普通字段的 reported_timestamp 停在 2025-04，Float 才是实时值。"""
            value = _number(device.value(float_sid, "target"))
            return value if value is not None else _number(device.value(plain_sid, "target"))

        def chill_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"native_value": _temp(device, "refrigeratorFloat", "refrigerator")}

        def freeze_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"native_value": _temp(device, "freezerFloat", "freezer")}

        async def set_chill(device: DeviceContext, data: Mapping[str, Any]) -> None:
            value = _number(data.get("value"))
            if value is None:
                return
            value = min(max(value, _CHILL_MIN), _CHILL_MAX)
            await device.async_send_service("refrigerator", {"target": int(round(value))})

        async def set_freeze(device: DeviceContext, data: Mapping[str, Any]) -> None:
            value = _number(data.get("value"))
            if value is None:
                return
            value = min(max(value, _FREEZE_MIN), _FREEZE_MAX)
            await device.async_send_service("freezer", {"target": int(round(value))})

        async def smart_on(device: DeviceContext, _data: Mapping[str, Any]) -> None:
            await device.async_send_service("intelligentSwitch", {"on": 1})

        async def smart_off(device: DeviceContext, _data: Mapping[str, Any]) -> None:
            await device.async_send_service("intelligentSwitch", {"on": 0})

        specs: list[EntitySpec] = [
            EntitySpec(
                platform="number",
                key="chill_temp",
                name="冷藏温度",
                state=chill_state,
                metadata={"min": _CHILL_MIN, "max": _CHILL_MAX, "step": 1, "unit": "°C"},
                actions={"set_value": set_chill},
            ),
            EntitySpec(
                platform="number",
                key="freeze_temp",
                name="冷冻温度",
                state=freeze_state,
                metadata={"min": _FREEZE_MIN, "max": _FREEZE_MAX, "step": 1, "unit": "°C"},
                actions={"set_value": set_freeze},
            ),
        ]
        if context.has_service("intelligentSwitch"):
            # ⚠️ 真机实测：intelligentSwitch 设备基本不上报（ts 停在 2025-04-16），发命令后云端
            # 三分钟纹丝不动 → 做 switch 会永远显示"关"、点完又跳回去。改成两个按钮，不假装知道状态。
            specs.append(EntitySpec(platform="button", key="smart_on", name="开智能模式",
                                    state=_empty_state, actions={"press": smart_on}))
            specs.append(EntitySpec(platform="button", key="smart_off", name="关智能模式",
                                    state=_empty_state, actions={"press": smart_off}))
        return tuple(specs)


ADAPTER = ProductA08LAdapter()
