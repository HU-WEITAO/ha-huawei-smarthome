"""User-contributed protocol for Huawei product A002 (美的 挂机空调).

证据（2026-09-16 实测）：集成状态文件 `.storage/huawei_smarthome.<entry>.state`
（实测 5 台）+ 产品 Profile `profiles/A002.json`。

字段（Profile 声明 / 真机上报值）：
  switch.on            bool RW  1=开 0=关
  mode.mode            enum RW  1=自动 2=制冷 3=制热 4=送风 5=抽湿      （Profile enumList）
  temperature.current  int  R   -20~50 室温（真机 29.4 ℃）
  temperature.target   int  RW  **读 0.1 ℃ 标度**（上报 240 = 24.0 ℃），**写 ℃ 整数**（发 25 = 25 ℃）
  fan.direction        enum RW  1=固定 2=左右扫风 3=上下扫风 4=左右+上下 （Profile enumList）

⚠️ 未暴露的字段（真机上报与 Profile 对不上，等真机证据再补）：
  - Profile 的 `fan.speed`(0~100) / `fan.mode`(0=手动风/1=自动风)：真机 **不报** 这两个字段
  - 真机上报的 `fan.gear`：Profile 里没有，枚举含义未知（a3rc 的 gear 是 0/2/3/4/5，未验证）
  → 风速档位暂不暴露，避免发没有证据的写命令。

暴露一个 climate：开关 / 模式 / 目标温度 / 摆风（+ 只读当前温度）。
关机状态（switch.on=0）在 HA 里报 `off`；切模式会连开机一起发（设备没有独立的开机）。
⚠️ 这些美的空调是**第三方云对接**：命令秒级到达设备（App/实物立即可见），但
   `service_states` 的状态回写可能滞后 **5~15 分钟** —— 判断命令是否生效要看实物/App，
   别用「云端没变」下结论（2026-09-16 真机实测：App 已显示 26 ℃ 而云端还停在 25 ℃）。
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

# 真机温度是 0.1 ℃ 标度（240 = 24.0 ℃）；HA 侧用常用设定区间
_TEMP_SCALE = 10.0
_TEMP_MIN = 16.0
_TEMP_MAX = 32.0

# 设备 mode(1-5) <-> HA HVAC（Profile enumList）
_DEV_TO_HVAC = {1: "auto", 2: "cool", 3: "heat", 4: "fan_only", 5: "dry"}
_HVAC_TO_DEV = {v: k for k, v in _DEV_TO_HVAC.items()}

# 设备 fan.direction(1-4) <-> HA swing（Profile enumList）
_DEV_TO_SWING = {1: "stop", 2: "horizontal", 3: "vertical", 4: "both"}
_SWING_TO_DEV = {v: k for k, v in _DEV_TO_SWING.items()}


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


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _as_temp(value: Any) -> float | None:
    """target 是 0.1 ℃ 标度（真机 240 = 24.0 ℃）→ ℃。"""
    raw = _as_int(value)
    return round(raw / _TEMP_SCALE, 1) if raw is not None else None


def _as_celsius(value: Any) -> float | None:
    """current 直接上报 ℃（真机 29.4）。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


async def _turn_on(device: DeviceContext, _data: Mapping[str, Any]) -> None:
    """开机：设备**没有独立的开机**（2026-09-16 真机实测），开机=切模式，所以和模式一起发。"""
    mode = _as_int(device.value("mode", "mode"))
    if mode not in _DEV_TO_HVAC:
        mode = _HVAC_TO_DEV["cool"]
    await device.async_send_service("switch", {"on": 1})
    await device.async_send_service("mode", {"mode": mode})


async def _turn_off(device: DeviceContext, _data: Mapping[str, Any]) -> None:
    await device.async_send_service("switch", {"on": 0})


async def _set_hvac_mode(device: DeviceContext, data: Mapping[str, Any]) -> None:
    """切模式；切到非 off 时总是先发开机（设备没有独立开机，见 _turn_on）。"""
    hvac = str(data.get("hvac_mode"))
    if hvac == "off":
        await device.async_send_service("switch", {"on": 0})
        return
    dev = _HVAC_TO_DEV.get(hvac)
    if dev is None:
        raise ValueError(f"unsupported hvac_mode: {data.get('hvac_mode')}")
    await device.async_send_service("switch", {"on": 1})
    await device.async_send_service("mode", {"mode": dev})


async def _set_temperature(device: DeviceContext, data: Mapping[str, Any]) -> None:
    """写入用 **℃ 整数**（Profile: target int RW 0~40）；读取才是 0.1 ℃ 标度。"""
    raw = data.get("temperature")
    if raw is None:
        return
    try:
        temp = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"bad temperature: {raw!r}") from None
    temp = max(_TEMP_MIN, min(_TEMP_MAX, temp))
    await device.async_send_service("temperature", {"target": int(round(temp))})


async def _set_swing_mode(device: DeviceContext, data: Mapping[str, Any]) -> None:
    direction = _SWING_TO_DEV.get(str(data.get("swing_mode")))
    if direction is None:
        raise ValueError(f"unsupported swing_mode: {data.get('swing_mode')}")
    await device.async_send_service("fan", {"direction": direction})


class ProductA002Adapter:
    """美的挂机空调：一个 climate 实体。"""

    prod_id = "A002"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("mode"):
            return ()

        def climate_state(device: DeviceContext) -> Mapping[str, Any]:
            return {
                # 关机(switch.on=0) → HA 的 off，否则报设备模式
                "hvac_mode": (
                    "off"
                    if _flag(device.value("switch", "on")) is False
                    else _DEV_TO_HVAC.get(_as_int(device.value("mode", "mode")))
                ),
                "current_temperature": _as_celsius(
                    device.value("temperature", "current")
                ),
                "target_temperature": _as_temp(device.value("temperature", "target")),
                "swing_mode": _DEV_TO_SWING.get(
                    _as_int(device.value("fan", "direction"))
                ),
            }

        actions = {
            "turn_on": _turn_on,
            "turn_off": _turn_off,
            "set_hvac_mode": _set_hvac_mode,
            "set_temperature": _set_temperature,
        }
        if context.has_service("fan"):
            actions["set_swing_mode"] = _set_swing_mode

        return (
            EntitySpec(
                platform="climate",
                key="air_conditioner",
                name=None,
                state=climate_state,
                metadata={
                    "hvac_modes": ["off", "auto", "cool", "heat", "fan_only", "dry"],
                    "swing_modes": ["stop", "horizontal", "vertical", "both"],
                    "min_temp": _TEMP_MIN,
                    "max_temp": _TEMP_MAX,
                    "target_temperature_step": 1,
                    "temperature_unit": "°C",
                },
                actions=actions,
            ),
        )


ADAPTER = ProductA002Adapter()
