"""User-contributed protocol for Huawei product A0OP (酷宅科技 智能墙开关).

设备类型: 智能墙壁开关（单路）
制造商: 酷宅科技（易微联 eWeLink 系）, 型号 Smart wall switch
Profile（profiles/A0OP.json）: `switch.on` bool RW（1=开 0=关）

⚠️ 该产品常被用于**边沿触发**场景（例：接 PCIe 开机卡，模拟"按一下机箱电源键"）——
   触发靠的是 **0→1 的上升沿**，不是保持电平。做成 `switch` 会踩两个坑：
   1. 只发 `on=1` 后云端状态**一直停在 on**，之后不再有新的上升沿 → 再点也不触发；
   2. HA 的 `switch` 在"目标状态 == 当前状态"时**直接跳过、根本不下发命令**。

   所以这里**不用 switch 而用 button**（button 每次按下必调、无同值短路）。
   按下**只发一次 `on=1`**（2026-09-17 真机纠正）：这类卡自带开机脉冲（实测 500ms），
   再补 `on=0` 等于又按一下电源键，会把刚上电的设备拍回去。

暴露 1 个 button 实体。同厂插座 `A0NN` 已有上游适配器，字段结构一致。
"""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

async def _press(device: DeviceContext, _data: Mapping[str, Any]) -> None:
    """按一次开机卡：只发 `on=1`。

    ⚠️ 2026-09-17 真机纠正：**绝对不能**再补发 `on=0`。
    设备自带脉冲参数（pulse_powerOn_width / pulse_shutdown_width 各 500ms）——
    `on=1` 就是「按一下电源键」，紧接着的 `on=0` 等于**又按一下**（设备刚上电就被拍回去），
    症状是「点了没反应」。
    """
    await device.async_send_service("switch", {"on": 1})


def _empty_state(_device: DeviceContext) -> Mapping[str, Any]:
    return {}


class ProductA0OPAdapter:
    """A0OP（接 PCIe 开机卡）：一个 button，按一下 = 发一次脉冲。"""

    prod_id = "A0OP"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("switch"):
            return ()

        return (
            EntitySpec(
                platform="button",
                key="power",
                name="开机",
                state=_empty_state,
                actions={"press": _press},
            ),
        )


ADAPTER = ProductA0OPAdapter()
