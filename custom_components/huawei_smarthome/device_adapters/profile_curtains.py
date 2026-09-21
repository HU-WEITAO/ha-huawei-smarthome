"""Explicitly validated 27WB/2N5R/140B curtain commands and positions."""

from .api import EntitySpec
from .profile_controls import (
    command_button,
    control_number,
    field,
    numeric,
    send,
    sensor,
    writable,
)


def covers(ctx, product):
    sid = key = "mode" if product == "140B" else "action"
    schema = field(ctx, sid, key)
    if not schema or not writable(ctx, sid, key):
        return ()
    labels = {
        int(e["enumVal"]): e.get("descCh", "").strip()
        for e in schema.get("enumList", [])
    }
    if (
        labels.get(0) not in ("关", "关闭窗帘")
        or labels.get(1) not in ("开", "打开窗帘")
        or labels.get(2) not in ("停止", "暂停")
    ):
        return ()
    actions = {}
    for name, value in (("open", 1), ("close", 0), ("stop", 2)):

        async def action(c, data, value=value):
            await send(c, sid, key, value)

        actions[name] = action
    # Only 140B and 2N5R explicitly document 100=open. 27WB position direction
    # is unspecified: expose commands and a raw position sensor until tested.
    positions = product in ("140B", "2N5R")
    if positions and writable(ctx, "opener", "target"):

        async def position(c, data):
            await send(c, "opener", "target", data["position"])

        actions["set_position"] = position

    def state(c):
        value = numeric(c, "opener", "current") if positions else None
        return {
            "current_position": int(value) if value is not None else None,
            "is_closed": value == 0 if value is not None else None,
        }

    result = [
        EntitySpec(
            "cover", "curtain", "窗帘", state, {"device_class": "curtain"}, actions
        )
    ]
    if not positions:
        result.append(sensor(ctx, "opener", "current", "位置原始值", unit="%"))
    if product == "2N5R":
        result.extend(
            e
            for e in (
                control_number(ctx, "rotationAngle", "target", "叶片目标角度", "%"),
                command_button(ctx, "rotationAction", "action", 2, "叶片停止"),
            )
            if e
        )
        result.append(sensor(ctx, "rotationAngle", "current", "叶片角度", unit="%"))
    return tuple(e for e in result if e)


class CurtainProductAdapter:
    def __init__(self, prod_id):
        self.prod_id = prod_id

    def entities(self, context):
        if (context.prod_id or "").casefold() != self.prod_id.casefold():
            return ()
        return covers(context, self.prod_id)
