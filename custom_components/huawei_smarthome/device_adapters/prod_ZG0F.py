"""Product ZG0F: verified explicit service mappings.

See docs/adapters/verified-products.md for evidence and supported scope.
"""

from .profile_controls import (
    control_number,
    control_select,
    control_switch,
    reading_entities,
)

READINGS = [
    ("basicFenceEvent", "existent", "有人", None, "occupancy", "binary"),
    ("luminance", "current", "光照度原始值", None, None),
    ("luminance", "level", "光照等级", None, None, "enum"),
    ("basicFenceEvent", "standingExistent", "站立状态", None, "occupancy", "binary"),
    ("basicFenceEvent", "nightLightIndication", "起夜状态", None, None, "binary"),
    ("basicFenceEvent", "across", "穿越虚拟墙", None, None, "binary"),
    ("basicFenceEvent", "nonBedStatus", "非床区域活动", None, None, "enum"),
    ("faultDetection", "status", "设备故障", None, "problem", "binary"),
]
SWITCHES = [
    ("switch", "on", "传感器检测"),
    ("switch", "reportSwitch", "事件上报"),
    ("backlight", "on", "指示灯"),
    ("basicFence", "enableFence", "区域检测"),
    ("basicFence", "standingExistentEnable", "站立检测"),
    ("basicFence", "acrossEnable", "安防检测"),
    ("basicFence", "nightLightIndicationEnable", "起夜检测"),
]
SELECTS = [("basicFence", "singleReport", "人员定位上报")]
NUMBERS = [("luminance", "threshold", "光照变化阈值", None)]


class ProductAdapter:
    prod_id = "ZG0F"

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

        from .radar_map import entities as radar_map_entities
        from .radar_options import entities as radar_option_entities
        from .radar_tuning import entities as radar_tuning_entities

        result.extend(radar_map_entities(context))
        result.extend(radar_option_entities(context))
        result.extend(radar_tuning_entities(context))

        return tuple(spec for spec in result if spec is not None)


ADAPTER = ProductAdapter()
