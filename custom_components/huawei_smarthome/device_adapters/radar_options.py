"""ZG0F advanced flags verified against Huawei's product H5 client.

basicFence.advancedPara bit 0: anti-interference; bit 5: pet filtering.
Bit 25 advertises pet filtering support. Preserve all other bits.
"""

import asyncio

from .api import EntitySpec


def flags(ctx):
    value = ctx.value("basicFence", "advancedPara")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if str(result) == str(value) and 0 <= result <= 0xFFFFFFFF else None


def entities(ctx):
    if (ctx.prod_id or "").upper() != "ZG0F" or flags(ctx) is None:
        return ()

    def make(bit, name):
        def state(c):
            raw = flags(c)
            return {"is_on": None if raw is None else bool(raw & (1 << bit))}

        async def set_flag(c, enabled):
            if not hasattr(c, "_radar_options_lock"):
                c._radar_options_lock = asyncio.Lock()
            async with c._radar_options_lock:
                raw = flags(c)
                if raw is None:
                    raise ValueError("Advanced settings have not been reported")
                pending = getattr(c, "_radar_options_pending", None)
                if pending is not None:
                    old, mask, wanted = pending
                    if (raw & mask) != wanted:
                        raise ValueError(
                            "Waiting for previous advanced setting to be reported"
                        )
                    c._radar_options_pending = None
                if bit == 5 and not raw & (1 << 25):
                    raise ValueError("Pet filtering is not supported")
                mask = 1 << bit
                value = raw | mask if enabled else raw & ~mask
                if value == raw:
                    return
                await c.async_send_service("basicFence", {"advancedPara": value})
                c._radar_options_pending = (raw, mask, value & mask)

        async def on(c, data):
            await set_flag(c, True)

        async def off(c, data):
            await set_flag(c, False)

        return EntitySpec(
            "switch",
            f"advanced_para_bit_{bit}",
            name,
            state,
            actions={"turn_on": on, "turn_off": off},
        )

    result = [make(0, "抗干扰增强")]
    if flags(ctx) & (1 << 25):
        result.append(make(5, "防宠检测"))
    return tuple(result)
