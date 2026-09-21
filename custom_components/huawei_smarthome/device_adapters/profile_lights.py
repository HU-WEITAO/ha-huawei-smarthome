"""Verified on/off and white-light controllers; no inferred RGB support."""

from .api import EntitySpec
from .profile_controls import (
    boolean,
    field,
    number,
    numeric,
    quantize,
    send,
    validate,
    writable,
)

LIGHTS = {
    "ZG0X": "onoff",
    "ZG0Y": "onoff",
    "ZG0S": "onoff",
    "ZG0R": "onoff",
    "28RD": "onoff",
    "ZG1I": "cct",
    "ZG0O": "cct",
    "20CL": "cct",
    "2AOS": "cct",
    "2JDD": "cct",
    "155F": "cct",
}


def lights(ctx, product):
    if not writable(ctx, "switch", "on"):
        return ()
    dim = LIGHTS[product] == "cct" and writable(ctx, "brightness", "brightness")
    cct = dim and writable(ctx, "cct", "colorTemperature")
    # ZG0O includes RGB in its shared Profile, but these installed strips have
    # not demonstrated RGB state. Expose only the observed CCT functionality.
    metadata = {
        "supported_color_modes": {
            "color_temp" if cct else "brightness" if dim else "onoff"
        }
    }
    if cct:
        schema = field(ctx, "cct", "colorTemperature")
        metadata.update(
            min_color_temp_kelvin=int(schema["min"]),
            max_color_temp_kelvin=int(schema["max"]),
        )

    def state(c):
        brightness = numeric(c, "brightness", "brightness") if dim else None
        return {
            "is_on": boolean(c.value("switch", "on")),
            "brightness": round(brightness * 255 / 100)
            if brightness is not None
            else None,
            "color_temp_kelvin": numeric(c, "cct", "colorTemperature") if cct else None,
            "color_mode": next(iter(metadata["supported_color_modes"])),
        }

    async def on(c, data):
        # Validate all parameters before performing even the power-on command.
        brightness, temperature = None, None
        if data.get("brightness") is not None:
            if (
                not dim
                or number(data["brightness"]) is None
                or not 0 <= float(data["brightness"]) <= 255
            ):
                raise ValueError("Unsupported or invalid brightness")
            brightness = quantize(
                c, "brightness", "brightness", float(data["brightness"]) * 100 / 255
            )
        if data.get("color_temp_kelvin") is not None:
            if not cct:
                raise ValueError("Color temperature is unsupported")
            temperature = quantize(
                c, "cct", "colorTemperature", data["color_temp_kelvin"]
            )
        if data.get("rgb_color") is not None:
            raise ValueError("RGB has not been verified for this product")
        validate(c, "switch", "on", 1)
        if brightness is not None:
            validate(c, "brightness", "brightness", brightness)
        if temperature is not None:
            validate(c, "cct", "colorTemperature", temperature)
            if product == "ZG0O":
                validate(c, "colourMode", "mode", 1)
        if data.get("brightness") is not None and float(data["brightness"]) == 0:
            await off(c, {})
            return
        await send(c, "switch", "on", 1)
        if brightness is not None:
            await send(c, "brightness", "brightness", brightness)
        if temperature is not None:
            if product == "ZG0O":
                await send(c, "colourMode", "mode", 1)
            await send(c, "cct", "colorTemperature", temperature)

    async def off(c, data):
        await send(c, "switch", "on", 0)

    return (
        EntitySpec(
            "light", "light", "灯", state, metadata, {"turn_on": on, "turn_off": off}
        ),
    )


class LightProductAdapter:
    def __init__(self, prod_id):
        self.prod_id = prod_id

    def entities(self, context):
        if (context.prod_id or "").casefold() != self.prod_id.casefold():
            return ()
        return lights(context, self.prod_id)
