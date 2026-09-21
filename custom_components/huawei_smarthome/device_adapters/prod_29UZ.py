"""Product 29UZ: verified explicit service mappings.

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
    ("temperature", "current", "温度", "°C", "temperature"),
    ("control", "warmWind", "风暖状态", None, None, "enum"),
    ("control", "ventilate", "换气状态", None, "running", "binary"),
    ("control", "light", "照明状态", None, None, "binary"),
    ("commonFaultDetection", "code", "故障代码", None, None, "enum"),
    ("commonFaultDetection", "status", "设备故障", None, "problem", "binary"),
]
SWITCHES = [
    ("control", "ventilate", "换气"),
    ("control", "light", "照明"),
    ("control", "dry", "干燥"),
    ("control", "wind", "吹风"),
    ("control", "nightLight", "夜灯"),
]
SELECTS = [("control", "warmWind", "风暖档位")]
NUMBERS = []


class ProductAdapter:
    prod_id = "29UZ"

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

        result.append(command_button(context, "Switch", "on1", 1, "待机"))

        return tuple(spec for spec in result if spec is not None)


ADAPTER = ProductAdapter()
