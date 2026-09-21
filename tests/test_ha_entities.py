"""Entity integration checks; skipped when Home Assistant is not installed."""

import importlib
import importlib.util
import unittest
from types import SimpleNamespace

from adapter_test_support import PROFILES, Context

HAS_HA = importlib.util.find_spec("homeassistant") is not None


@unittest.skipUnless(HAS_HA, "Run inside a Home Assistant Python environment")
class HomeAssistantTests(unittest.IsolatedAsyncioTestCase):
    def context(self, product):
        c = Context(product)
        c.home_id = "synthetic-home"
        c.dev_id = "synthetic-device"
        c.name = "Test device"
        c.state_listeners = set()
        c.service_listeners = set()
        c.add_state_listener = c.state_listeners.add
        c.remove_state_listener = c.state_listeners.discard
        c.add_service_update_listener = c.service_listeners.add
        c.remove_service_update_listener = c.service_listeners.discard
        return c

    def entity_class(self, platform):
        names = {
            "binary_sensor": "BinarySensor",
            "sensor": "Sensor",
            "light": "Light",
            "cover": "Cover",
            "humidifier": "Humidifier",
            "button": "Button",
            "switch": "Switch",
            "number": "Number",
            "select": "Select",
        }
        m = importlib.import_module("custom_components.huawei_smarthome." + platform)
        return getattr(m, "HuaweiAdapter" + names[platform])

    def test_all_products_instantiate_real_ha_entities(self):
        from homeassistant.util.unit_system import METRIC_SYSTEM

        for product in PROFILES:
            c = self.context(product)
            for spec in c.specs():
                with self.subTest(product=product, entity=spec.name):
                    entity = self.entity_class(spec.platform)(c, spec)
                    entity.hass = SimpleNamespace(
                        config=SimpleNamespace(units=METRIC_SYSTEM)
                    )
                    _ = entity.state
                    self.assertTrue(entity.available)
            self.assertEqual(c.commands, [])

    async def test_position_timestamp_only_tracks_coordinate_reports(self):
        c = self.context("ZG0F")
        spec = c.named("区域与人员位置")
        entity = self.entity_class("sensor")(c, spec)
        entity.async_write_ha_state = lambda: None
        await entity.async_added_to_hass()
        self.assertEqual(len(c.service_listeners), 1)
        self.assertIsNone(entity.extra_state_attributes["position_received_at"])
        callback = next(iter(c.service_listeners))
        callback("basicFenceEvent", {"existent": 1}, None)
        self.assertIsNone(entity.extra_state_attributes["position_received_at"])
        callback("basicFenceEvent", {"postionList": "1,2,0"}, None)
        first = entity.extra_state_attributes["position_received_at"]
        self.assertIsNotNone(first)
        callback("luminance", {"current": 20}, None)
        self.assertEqual(entity.extra_state_attributes["position_received_at"], first)
        callback("basicFenceEvent", {"positionList": ""}, None)
        self.assertIsNotNone(entity.extra_state_attributes["position_received_at"])
        await entity.async_will_remove_from_hass()
        self.assertEqual(c.service_listeners, set())
        self.assertEqual(c.state_listeners, set())

    def test_device_class_metadata(self):
        for pid, platform, name in [
            ("140B", "cover", "curtain"),
            ("29XC", "humidifier", "dehumidifier"),
        ]:
            c = self.context(pid)
            spec = next(s for s in c.specs() if s.platform == platform)
            self.assertEqual(self.entity_class(platform)(c, spec).device_class, name)

    def test_plain_sensor_adds_no_timestamps(self):
        c = self.context("2OPO")
        entity = self.entity_class("sensor")(c, c.named("温度"))
        self.assertIsNone(entity.extra_state_attributes)
