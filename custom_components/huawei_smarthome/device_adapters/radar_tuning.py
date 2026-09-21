"""ZG0F tuning controls verified against the vendor H5 and device reports."""

import asyncio

from .api import EntitySpec
from .profile_controls import numeric, send, writable


def delay_values(ctx):
    raw = ctx.value("basicFence", "delayTimeList")
    if not isinstance(raw, str):
        return None
    values = raw.split(",")
    if len(values) != 16 or any(v not in ("0", "1", "2") for v in values):
        return None
    return values


def entities(ctx):
    if (ctx.prod_id or "").upper() != "ZG0F":
        return ()
    result = []
    options = {"高": 2, "中": 3, "低": 4}
    if writable(ctx, "basicFence", "sensitivity"):

        async def sensitivity(c, data):
            if data.get("option") not in options:
                raise ValueError("Unsupported sensitivity")
            await send(c, "basicFence", "sensitivity", options[data["option"]])

        result.append(
            EntitySpec(
                "select",
                "radar_sensitivity",
                "检测灵敏度",
                lambda c: {
                    "current_option": next(
                        (
                            label
                            for label, value in options.items()
                            if str(c.value("basicFence", "sensitivity")) == str(value)
                        ),
                        None,
                    )
                },
                {"options": tuple(options)},
                {"select_option": sensitivity},
            )
        )
    if writable(ctx, "basicFence", "filteringHeight"):

        async def height(c, data):
            value = float(data["value"])
            if not 0 <= value <= 70 or value % 5:
                raise ValueError("Height must be 0–70 cm in 5 cm increments")
            await send(c, "basicFence", "filteringHeight", int(value))

        result.append(
            EntitySpec(
                "number",
                "radar_minimum_height",
                "最小感应高度",
                lambda c: {"native_value": numeric(c, "basicFence", "filteringHeight")},
                {"min": 0, "max": 70, "step": 5, "unit": "cm"},
                {"set_value": height},
            )
        )
    if writable(ctx, "action", "action"):

        async def reset(c, data):
            await send(c, "action", "action", 1)

        result.append(
            EntitySpec(
                "button",
                "radar_reset_unoccupied",
                "重置无人状态",
                lambda c: {},
                actions={"press": reset},
            )
        )
    values = delay_values(ctx)
    if values is not None and writable(ctx, "basicFence", "delayTimeList"):
        for i in range(1, 9):
            sid = f"userFence{i}"
            fid = ctx.value(sid, "fenceID")
            if not isinstance(fid, int) or not 0 < fid < len(values):
                continue
            if ctx.value(sid, "fenceType") != 0 or ctx.value(sid, "enableFence") != 1:
                continue
            name = ctx.value(sid, "fenceName") or f"区域{fid}"
            result.append(delay_entity(sid, fid, name))
    return tuple(result)


def delay_entity(sid, fid, name):
    options = {"快速响应": "0", "精准响应": "2"}

    def state(c):
        values = delay_values(c)
        value = values[fid] if values else None
        return {
            "current_option": next((k for k, v in options.items() if v == value), None)
        }

    async def select(c, data):
        if data.get("option") not in options:
            raise ValueError("Unsupported region response mode")
        if not hasattr(c, "_radar_delay_lock"):
            c._radar_delay_lock = asyncio.Lock()
        async with c._radar_delay_lock:
            values = delay_values(c)
            if (
                values is None
                or c.value(sid, "fenceID") != fid
                or c.value(sid, "enableFence") != 1
            ):
                raise ValueError("Region configuration changed; reload the integration")
            pending = getattr(c, "_radar_delay_pending", None)
            if pending and values[pending[0]] != pending[1]:
                raise ValueError(
                    "Waiting for the previous region setting to be reported"
                )
            value = options[data["option"]]
            if values[fid] == value:
                return
            values[fid] = value
            await send(c, "basicFence", "delayTimeList", ",".join(values))
            c._radar_delay_pending = (fid, value)

    return EntitySpec(
        "select",
        f"radar_region_{fid}_response",
        f"{name}无人响应",
        state,
        {"options": tuple(options)},
        {"select_option": select},
    )
