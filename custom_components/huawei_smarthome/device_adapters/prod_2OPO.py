"""Product 2OPO: verified explicit service mappings.

See docs/adapters/verified-products.md for evidence and supported scope.
"""

from .profile_controls import (
    control_number,
    control_select,
    control_switch,
    reading_entities,
)

READINGS = [
    ("battery", "level", "电量", "%", "battery"),
    ("battery", "alarm", "低电量", None, "battery", "binary"),
    ("temperature", "current", "温度", "°C", "temperature"),
    ("humidity", "current", "湿度", "%", "humidity"),
    ("temperature", "level", "温度舒适度", None, None, "enum"),
    ("humidity", "level", "湿度舒适度", None, None, "enum"),
    ("commonFaultDetection", "status", "设备故障", None, "problem", "binary"),
]
SWITCHES = []
SELECTS = []
NUMBERS = []


class ProductAdapter:
    prod_id = "2OPO"

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

        return tuple(spec for spec in result if spec is not None)


ADAPTER = ProductAdapter()
