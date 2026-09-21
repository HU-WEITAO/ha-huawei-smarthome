"""Read-only ZG0F geometry from vendor H5's count+XY and XYZ formats.

Verified against ZG0F/h5_001/static/js/app.19cc73a380576e9b191d.js.
Position reporting is an explicit user action, never enabled during rendering.
"""

from __future__ import annotations

import math

from .api import EntitySpec


def numbers(value):
    if not isinstance(value, str) or len(value) > 4096:
        return []
    try:
        result = [float(x.strip()) for x in value.split(",")]
    except (TypeError, ValueError):
        return []
    return result if all(math.isfinite(x) and abs(x) <= 100000 for x in result) else []


def polygon(value, counted=False):
    n = numbers(value)
    if counted:
        if (
            not n
            or n[0] != int(n[0])
            or not 3 <= n[0] <= 64
            or len(n) < 1 + 2 * int(n[0])
        ):
            return []
        n = n[1 : 1 + 2 * int(n[0])]
    if len(n) < 6 or len(n) % 2:
        return []
    points = [{"x": n[i], "y": n[i + 1]} for i in range(0, len(n), 2)]
    if len({(p["x"], p["y"]) for p in points}) < 3:
        return []
    return points


def map_state(c):
    regions = []
    outer = []
    for i in range(1, 4):
        outer.extend(polygon(c.value("basicFence", f"locationList{i}"), True))
    if outer:
        regions.append(
            {
                "name": c.value("basicFence", "fenceName") or "总区域",
                "kind": "boundary",
                "points": outer,
            }
        )
    for i in range(1, 9):
        sid = f"userFence{i}"
        if c.value(sid, "enableFence") not in (1, "1", True):
            continue
        pts = polygon(c.value(sid, "locationList"))
        if pts:
            regions.append(
                {
                    "name": str(c.value(sid, "fenceName") or f"区域{i}"),
                    "kind": "region",
                    "points": pts,
                    "occupied": c.value(f"userFenceEvent{i}", "existent")
                    in (1, "1", True),
                }
            )
    walls = []
    for i in range(1, 26):
        v = numbers(c.value("basicFence", f"virtualWallList{i}"))
        if len(v) >= 5 and v[0] in (1, 2, 3, 4, 5, 6):
            walls.append(
                {
                    "type": int(v[0]),
                    "points": [{"x": v[1], "y": v[2]}, {"x": v[3], "y": v[4]}],
                }
            )
    raw = c.value("basicFenceEvent", "positionList")
    if raw is None:
        raw = c.value("basicFenceEvent", "postionList")
    v = numbers(raw)
    points = []
    if len(v) % 3 == 0:
        points = [
            {"x": v[i], "y": v[i + 1], "z": v[i + 2]}
            for i in range(0, min(len(v), 96), 3)
        ]
    tag = c.value("basicFenceEvent", "positionTag")
    if tag is None:
        tag = c.value("basicFenceEvent", "postionTag")
    occupied = c.value("basicFenceEvent", "existent")
    occupied = (
        True
        if occupied in (1, "1", True)
        else False
        if occupied in (0, "0", False)
        else None
    )
    install = numbers(c.value("devLocation", "installCoord"))
    return {
        "native_value": "有人"
        if occupied is True
        else "无人"
        if occupied is False
        else "待上报",
        "extra_state_attributes": {
            "radar_map": True,
            "regions": regions,
            "walls": walls,
            "positions": points,
            "position_valid": tag not in (None, 0, "0", False) and bool(points),
            "occupied": occupied,
            "report_mode": c.value("basicFence", "singleReport"),
            "sensor_position": {"x": install[0], "y": install[1]}
            if len(install) >= 2
            else None,
            "coordinate_system": "vendor_xy",
            "freshness_seconds": 15,
        },
    }


def entities(ctx):
    return (
        EntitySpec(
            "sensor",
            "radar_area_map",
            "区域与人员位置",
            map_state,
            {
                "radar_map": True,
                "attribute_update_timestamps": {
                    "position_received_at": {
                        "service": "basicFenceEvent",
                        "fields": ("positionList", "postionList"),
                    }
                },
            },
        ),
    )
