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
