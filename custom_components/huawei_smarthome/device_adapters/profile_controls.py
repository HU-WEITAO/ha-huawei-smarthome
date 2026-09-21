"""Profile validation and small entity factories for explicitly mapped products.

These helpers do not discover entities from arbitrary writable fields. Product
adapters choose every service/field explicitly; reads never send commands.
"""

from __future__ import annotations

import math

from .api import EntitySpec


def field(ctx, sid, key):
    for service in (ctx.profile or {}).get("services", []):
        if service.get("serviceId") == sid:
            return next(
                (
                    f
                    for f in service.get("characteristics", [])
                    if f.get("characteristicName") == key
                ),
                None,
            )
    return None


def number(value):
    try:
        if isinstance(value, bool):
            return None
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError, OverflowError):
        return None


def boolean(value):
    if value in (0, "0", False):
        return False
    if value in (1, "1", True):
        return True
    return None


def numeric(ctx, sid, key):
    value = number(ctx.value(sid, key))
    schema = field(ctx, sid, key)
    if value is None or not schema:
        return None
    low, high = number(schema.get("min")), number(schema.get("max"))
    if (low is not None and value < low) or (high is not None and value > high):
        return None
    return value


def writable(ctx, sid, key):
    schema = field(ctx, sid, key)
    return bool(schema and "W" in schema.get("method", ""))


def validate(ctx, sid, key, value):
    schema = field(ctx, sid, key)
    if not writable(ctx, sid, key):
        raise ValueError(f"Profile does not permit writing {sid}.{key}")
    kind = schema.get("characteristicType")
    if kind in ("int", "float", "double", "bool", "enum"):
        parsed = number(value)
        if parsed is None:
            raise ValueError("A finite numeric command is required")
        if kind in ("int", "bool", "enum"):
            if not parsed.is_integer():
                raise ValueError("An integer command is required")
            value = int(parsed)
        else:
            value = parsed
        low, high = number(schema.get("min")), number(schema.get("max"))
        if (low is not None and value < low) or (high is not None and value > high):
            raise ValueError("Command is outside the product Profile range")
        step = number(schema.get("step"))
        if (
            step
            and low is not None
            and not math.isclose(
                (value - low) / step, round((value - low) / step), abs_tol=1e-6
            )
        ):
            raise ValueError("Command does not match the product Profile step")
    if kind == "string" and not isinstance(value, str):
        raise ValueError("A string command is required")
    choices = schema.get("enumList", [])
    if choices and str(value) not in {str(e["enumVal"]) for e in choices}:
        raise ValueError("Command is not in the product Profile enum")
    return value


async def send(ctx, sid, key, value):
    value = validate(ctx, sid, key, value)
    await ctx.async_send_service(sid, {key: value})


def quantize(ctx, sid, key, value):
    schema = field(ctx, sid, key)
    value = number(value)
    if schema is None or value is None:
        raise ValueError("Missing numeric Profile or invalid input")
    low, high = float(schema["min"]), float(schema["max"])
    step = float(schema.get("step") or 1)
    return int(max(low, min(high, low + round((value - low) / step) * step)))


def sensor(
    ctx,
    sid,
    key,
    name,
    *,
    unit=None,
    device_class=None,
    binary=False,
    enum=False,
    scale=1,
):
    schema = field(ctx, sid, key)
    if schema is None or "R" not in schema.get("method", ""):
        return None
    metadata = {}
    if unit:
        metadata["unit"] = unit
    if device_class:
        metadata["device_class"] = device_class

    def state(c):
        raw = c.value(sid, key)
        if binary:
            return {"is_on": boolean(raw)}
        if enum:
            value = next(
                (
                    v.get("descCh") or str(raw)
                    for v in schema.get("enumList", [])
                    if str(v.get("enumVal")) == str(raw)
                ),
                None,
            )
        else:
            value = numeric(c, sid, key)
            if value is not None:
                value = value / 10 if scale == 0.1 else value * scale
        return {"native_value": value}

    return EntitySpec(
        "binary_sensor" if binary else "sensor",
        f"{sid}_{key}",
        name,
        state,
        metadata=metadata,
    )


def control_switch(ctx, sid, key, name, inverted=False):
    if not writable(ctx, sid, key):
        return None

    async def on(c, d):
        await send(c, sid, key, 0 if inverted else 1)

    async def off(c, d):
        await send(c, sid, key, 1 if inverted else 0)

    return EntitySpec(
        "switch",
        f"{sid}_{key}_control",
        name,
        lambda c: {
            "is_on": (
                not boolean(c.value(sid, key))
                if inverted and boolean(c.value(sid, key)) is not None
                else boolean(c.value(sid, key))
            )
        },
        actions={"turn_on": on, "turn_off": off},
    )


def control_number(ctx, sid, key, name, unit=None):
    schema = field(ctx, sid, key)
    if not writable(ctx, sid, key) or "min" not in schema or "max" not in schema:
        return None

    async def set_value(c, d):
        await send(c, sid, key, d["value"])

    return EntitySpec(
        "number",
        f"{sid}_{key}_control",
        name,
        lambda c: {"native_value": numeric(c, sid, key)},
        {
            "min": float(schema["min"]),
            "max": float(schema["max"]),
            "step": float(schema.get("step") or 1),
            "unit": unit,
        },
        {"set_value": set_value},
    )


def control_select(ctx, sid, key, name):
    if not writable(ctx, sid, key):
        return None
    options = {
        str(v["enumVal"]): v.get("descCh", str(v["enumVal"]))
        for v in field(ctx, sid, key).get("enumList", [])
    }
    if not options:
        return None

    async def select(c, d):
        value = next((k for k, v in options.items() if v == d["option"]), None)
        if value is None:
            raise ValueError("Unknown option")
        await send(c, sid, key, int(value))

    return EntitySpec(
        "select",
        f"{sid}_{key}_control",
        name,
        lambda c: {"current_option": options.get(str(c.value(sid, key)))},
        {"options": tuple(options.values())},
        {"select_option": select},
    )


def command_button(ctx, sid, key, value, name):
    if not writable(ctx, sid, key):
        return None
    if str(value) not in {
        str(e["enumVal"]) for e in field(ctx, sid, key).get("enumList", [])
    }:
        return None

    async def press(c, d):
        await send(c, sid, key, value)

    return EntitySpec(
        "button",
        f"{sid}_{key}_{value}_command",
        name,
        lambda c: {},
        actions={"press": press},
    )


def reading_entities(ctx, rows):
    result = []
    for row in rows:
        sid, key, name, unit, device_class, *kind = row
        scale = (
            0.1
            if (ctx.prod_id.upper() == "2OPO" and sid in ("temperature", "humidity"))
            or (
                ctx.prod_id.upper() == "2GIP"
                and sid in ("totalWater", "totalGas", "curWater")
            )
            else 1
        )
        spec = sensor(
            ctx,
            sid,
            key,
            name,
            unit=unit,
            device_class=device_class,
            binary=kind == ["binary"],
            enum=kind == ["enum"],
            scale=scale,
        )
        if spec is not None:
            result.append(spec)
    return result
