"""Product A36L: verified explicit service mappings.

See docs/adapters/verified-products.md for evidence and supported scope.
"""

from .profile_controls import (
    command_button,
    control_number,
    control_select,
    control_switch,
    reading_entities,
)

READINGS = [
    ("battery", "level", "电量", "%", "battery"),
    ("status", "status", "运行状态", None, None, "enum"),
]
SWITCHES = []
SELECTS = []
NUMBERS = []


class ProductAdapter:
    prod_id = "A36L"

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

        for value, name in [
            (0, "回充"),
            (1, "清扫"),
            (2, "暂停"),
            (19, "继续"),
            (21, "设备查找"),
        ]:
            result.append(command_button(context, "action", "action", value, name))

        return tuple(spec for spec in result if spec is not None)


ADAPTER = ProductAdapter()
