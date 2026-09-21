"""Product 29XC: verified explicit service mappings.

See docs/adapters/verified-products.md for evidence and supported scope.
"""

from .api import EntitySpec
from .profile_controls import (
    boolean,
    control_number,
    control_select,
    control_switch,
    field,
    numeric,
    reading_entities,
    send,
    writable,
)

READINGS = [
    ("Temp", "display", "温度", "°C", "temperature"),
    ("HUM", "display", "湿度", "%", "humidity"),
    ("commonFilterElement1", "alarm", "滤网更换提醒", None, "problem", "binary"),
    ("commonFilterElement1", "leftTime", "滤网剩余时间", "h", None),
    ("commonFaultDetection", "code", "故障代码", None, None, "enum"),
    ("commonFaultDetection", "status", "设备故障", None, "problem", "binary"),
]
SWITCHES = [("childLockSwitch", "on", "童锁"), ("Purify", "Purify", "光催化")]
SELECTS = [("SetSpeed", "set", "风速")]
NUMBERS = [("Countdown", "Countdown", "定时关机", "h")]


def dehumidifier(ctx):
    needed = [("switch", "on"), ("SetDUM", "SetDUM"), ("SetMode", "set")]
    if not all(writable(ctx, *f) for f in needed):
        return ()
    modes = {
        str(x["enumVal"]): x["descCh"] for x in field(ctx, "SetMode", "set")["enumList"]
    }

    def state(c):
        return {
            "is_on": boolean(c.value("switch", "on")),
            "current_humidity": numeric(c, "HUM", "display"),
            "target_humidity": numeric(c, "SetDUM", "SetDUM"),
            "mode": modes.get(str(c.value("SetMode", "set"))),
        }

    async def on(c, data):
        await send(c, "switch", "on", 1)

    async def off(c, data):
        await send(c, "switch", "on", 0)

    async def humidity(c, data):
        await send(c, "SetDUM", "SetDUM", data["humidity"])

    async def mode(c, data):
        value = next((v for v, label in modes.items() if label == data["mode"]), None)
        if value is None:
            raise ValueError("Unknown dehumidifier mode")
        await send(c, "SetMode", "set", int(value))

    return (
        EntitySpec(
            "humidifier",
            "dehumidifier",
            "除湿控制",
            state,
            {
                "device_class": "dehumidifier",
                "min_humidity": 30,
                "max_humidity": 80,
                "modes": tuple(modes.values()),
            },
            {
                "turn_on": on,
                "turn_off": off,
                "set_humidity": humidity,
                "set_mode": mode,
            },
        ),
    )


class ProductAdapter:
    prod_id = "29XC"

    def entities(self, context):
        if (context.prod_id or "").casefold() != self.prod_id.casefold():
            return ()
        result = reading_entities(context, READINGS)
        for sid, key, name in SWITCHES:
            result.append(control_switch(context, sid, key, name))
        for sid, key, name in SELECTS:
            result.append(control_select(context, sid, key, name))
        for sid, key, name, unit in NUMBERS:
            result.append(control_number(context, sid, key, name, unit))

        result.extend(dehumidifier(context))

        return tuple(spec for spec in result if spec is not None)


ADAPTER = ProductAdapter()
