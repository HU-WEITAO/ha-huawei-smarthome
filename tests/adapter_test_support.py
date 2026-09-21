"""Load protocol-only adapters without importing HA or contacting a device."""

import copy
import importlib
import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Namespace packages bypass the integration's HA startup; real adapter code and
# EntitySpec are imported unchanged. No Home Assistant API is mocked here.
for name, path in [
    ("custom_components", ROOT / "custom_components"),
    ("custom_components.huawei_smarthome", ROOT / "custom_components/huawei_smarthome"),
    (
        "custom_components.huawei_smarthome.device_adapters",
        ROOT / "custom_components/huawei_smarthome/device_adapters",
    ),
]:
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules[name] = module

PROFILES = json.loads((ROOT / "tests/fixtures/verified_profiles.json").read_text())


def module(name):
    return importlib.import_module(
        "custom_components.huawei_smarthome.device_adapters." + name
    )


class Context:
    def __init__(self, product, states=None):
        self.prod_id = product
        self.profile = copy.deepcopy(PROFILES[product])
        self.states = copy.deepcopy(states or {})
        self.commands = []
        self.available = True
        self.fail_sid = None

    def value(self, sid, key):
        return self.states.get(sid, {}).get(key)

    def service_updated_at(self, sid):
        return datetime(2026, 1, 1, tzinfo=timezone.utc) if sid in self.states else None

    async def async_send_service(self, sid, data):
        if sid == self.fail_sid:
            raise RuntimeError("Simulated rejected command")
        self.commands.append((sid, dict(data)))
        # Deliberately do not update state on ACK: only a device report can.

    def specs(self):
        return module("prod_" + self.prod_id.upper()).ADAPTER.entities(self)

    def named(self, name):
        return next(spec for spec in self.specs() if spec.name == name)
