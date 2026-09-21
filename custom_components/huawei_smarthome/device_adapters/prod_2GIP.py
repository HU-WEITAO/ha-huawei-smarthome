"""Product 2GIP: verified explicit service mappings.

See docs/adapters/verified-products.md for evidence and supported scope.
"""

from .profile_controls import (
    control_number,
    control_select,
    control_switch,
    reading_entities,
)

READINGS = [
    ("inletTemperature", "current", "进水温度", "°C", "temperature"),
    ("temperature", "target", "设定温度", "°C", "temperature"),
    ("status", "status", "运行状态", None, None, "enum"),
    ("gasStatus", "gasStatus", "燃气状态异常", None, "problem", "binary"),
    ("totalWater", "current", "累计热水量", "t", None),
    ("totalGas", "current", "累计燃气量", "m³", None),
    ("curWater", "current", "实时出水量", "L", None),
    ("statusOfMachine", "statusOfMachine", "设备安全异常", None, "problem", "binary"),
    ("faultDetection", "code", "故障代码", None, None, "enum"),
    ("faultDetection", "status", "设备故障", None, "problem", "binary"),
]
SWITCHES = [
    ("switch", "on", "电源"),
    ("boostMode", "on", "增压大水量"),
    ("zeroColdSwitch", "on", "一键零冷水"),
]
SELECTS = [("zeroColdMode", "mode", "零冷水季节")]
NUMBERS = [("temperature", "target", "目标温度", "°C")]


class ProductAdapter:
    prod_id = "2GIP"

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
