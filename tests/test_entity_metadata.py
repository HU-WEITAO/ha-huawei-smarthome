"""Generic platform metadata tests, independent of contributed adapters."""

import importlib
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
for name, path in [
    ("custom_components", ROOT / "custom_components"),
    ("custom_components.huawei_smarthome", ROOT / "custom_components/huawei_smarthome"),
    (
        "custom_components.huawei_smarthome.device_adapters",
        ROOT / "custom_components/huawei_smarthome/device_adapters",
    ),
]:
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(path)]
        sys.modules[name] = package

HAS_HA = importlib.util.find_spec("homeassistant") is not None


@unittest.skipUnless(HAS_HA, "Requires a Home Assistant Python environment")
class MetadataTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from custom_components.huawei_smarthome.device_adapters.api import EntitySpec

        self.spec_class = EntitySpec
        self.state_listeners = set()
        self.service_listeners = set()
        self.context = SimpleNamespace(
            home_id="test-home",
            dev_id="test-device",
            available=True,
            add_state_listener=self.state_listeners.add,
            remove_state_listener=self.state_listeners.discard,
            add_service_update_listener=self.service_listeners.add,
            remove_service_update_listener=self.service_listeners.discard,
        )
        self.values = {"native_value": 12}

    def entity(self, platform="sensor", metadata=None):
        spec = self.spec_class(
            platform, "test", "Test", lambda c: self.values, metadata or {}
        )
        module = importlib.import_module(
            "custom_components.huawei_smarthome." + platform
        )
        entity = getattr(module, "HuaweiAdapter" + platform.title())(self.context, spec)
        entity.async_write_ha_state = lambda: None
        return entity

    def test_cover_and_humidifier_device_classes(self):
        for platform, device_class in [
            ("cover", "curtain"),
            ("humidifier", "dehumidifier"),
        ]:
            with self.subTest(platform=platform):
                self.assertEqual(
                    self.entity(platform, {"device_class": device_class}).device_class,
                    device_class,
                )
                self.assertIsNone(self.entity(platform).device_class)

    def test_sensor_attributes_follow_reported_state_without_mutation(self):
        entity = self.entity()
        self.assertIsNone(entity.extra_state_attributes)
        self.values["extra_state_attributes"] = {"coordinates": [1, 2]}
        self.assertEqual(entity.extra_state_attributes, {"coordinates": [1, 2]})
        entity.extra_state_attributes["new"] = True
        self.assertNotIn("new", self.values["extra_state_attributes"])
        self.values["extra_state_attributes"] = {"coordinates": [3, 4]}
        self.assertEqual(entity.extra_state_attributes, {"coordinates": [3, 4]})

    async def test_timestamps_only_follow_configured_service_and_fields(self):
        entity = self.entity(
            metadata={
                "attribute_update_timestamps": {
                    "position_received_at": {
                        "service": "location",
                        "fields": ("position", "legacyPosition"),
                    },
                    "status_received_at": {"service": "status", "fields": ("mode",)},
                }
            }
        )
        await entity.async_added_to_hass()
        self.assertEqual(len(self.state_listeners), 1)
        self.assertEqual(len(self.service_listeners), 1)
        callback = next(iter(self.service_listeners))
        self.assertEqual(
            entity.extra_state_attributes,
            {"position_received_at": None, "status_received_at": None},
        )
        callback("location", {"occupied": 1}, None)
        callback("other", {"position": "1,2"}, None)
        self.assertIsNone(entity.extra_state_attributes["position_received_at"])
        callback("location", {"legacyPosition": "1,2"}, None)
        first = entity.extra_state_attributes["position_received_at"]
        self.assertIsNotNone(first)
        callback("status", {"mode": 1}, None)
        self.assertEqual(entity.extra_state_attributes["position_received_at"], first)
        self.assertIsNotNone(entity.extra_state_attributes["status_received_at"])
        callback("location", {"position": ""}, None)
        self.assertIsNotNone(entity.extra_state_attributes["position_received_at"])
        await entity.async_will_remove_from_hass()
        self.assertFalse(self.state_listeners)
        self.assertFalse(self.service_listeners)

    async def test_plain_sensor_keeps_original_listener_lifecycle(self):
        entity = self.entity()
        await entity.async_added_to_hass()
        self.assertEqual(len(self.state_listeners), 1)
        self.assertFalse(self.service_listeners)
        self.assertIsNone(entity.extra_state_attributes)
        await entity.async_will_remove_from_hass()
        self.assertFalse(self.state_listeners)
