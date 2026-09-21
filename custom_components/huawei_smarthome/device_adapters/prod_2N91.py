"""Product 2N91: verified explicit service mappings.

See docs/adapters/verified-products.md for evidence and supported scope.
"""

from .api import EntitySpec
from .profile_controls import (
    boolean,
    command_button,
    control_number,
    control_select,
    control_switch,
    reading_entities,
    send,
    writable,
)

READINGS = [
    ("seatStatus", "status", "着座", None, "occupancy", "binary"),
    ("seatGear", "gear", "座温档位", None, None, "enum"),
]
SWITCHES = [
    ("dryingSwitch", "on", "烘干"),
    ("Switch", "ECO", "节能模式"),
    ("Switch", "footfeel", "脚感开关"),
    ("Switch", "Mute", "静音"),
    ("Switch", "PreWetting", "预湿润"),
]
SELECTS = [
    ("toiletMode", "mode", "清洗模式"),
    ("windGear", "gear", "烘干风温"),
    ("cheaningGear", "gear", "冲洗强度"),
    ("waterGear", "gear", "水温档位"),
    ("seatGear", "gear", "座温调节"),
    ("hipNozzlePos", "gear", "喷嘴位置"),
    ("Switch", "SenseDistance", "微波感应距离"),
    ("Switch", "AutoFlush", "自动冲水"),
    ("Switch", "AutoFlip", "微波开盖"),
    ("nightled", "gear", "夜灯亮度"),
]
NUMBERS = []


def opening_button(sid, name):
    """Preserve the tested toggle payload while presenting a one-shot button."""

    async def press(context, data):
        current = boolean(context.value(sid, "on"))
        if current is None:
            raise ValueError("Opening control has not reported a state")
        await send(context, sid, "on", 0 if current else 1)

    return EntitySpec(
        "button", f"{sid}_toggle", name, lambda context: {}, actions={"press": press}
    )


class ProductAdapter:
    prod_id = "2N91"

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

        for sid, name in [("seatRing", "座圈开合"), ("filpSwitch", "盖板开合")]:
            if writable(context, sid, "on"):
                result.append(opening_button(sid, name))
        for sid, name in [
            ("smallflushSwitch", "小冲"),
            ("bigflushSwitch", "大冲"),
            ("cleaningSwitch", "喷枪清洗"),
        ]:
            result.append(command_button(context, sid, "on", 1, name))
        result.append(command_button(context, "stop", "action", 0, "停止清洗与烘干"))

        return tuple(spec for spec in result if spec is not None)


ADAPTER = ProductAdapter()
