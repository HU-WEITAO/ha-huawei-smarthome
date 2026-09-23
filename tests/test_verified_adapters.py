"""Offline regression tests: synthetic states, selected public protocol fields."""

import ast
import json
import unittest
from pathlib import Path

from adapter_test_support import PROFILES, Context, module


class Tests(unittest.IsolatedAsyncioTestCase):
    def test_products_have_no_shared_adapter_implementation_dependency(self):
        directory = (
            Path(__file__).resolve().parents[1]
            / "custom_components/huawei_smarthome/device_adapters"
        )
        for pid in PROFILES:
            tree = ast.parse((directory / f"prod_{pid}.py").read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level:
                    self.assertEqual(node.module, "api", pid)
        for stem in (
            "profile_controls",
            "profile_lights",
            "profile_curtains",
            "radar_map",
            "radar_options",
            "radar_tuning",
        ):
            self.assertFalse((directory / (stem + ".py")).exists())

    def test_product_scope_and_passive_readers(self):
        for pid in PROFILES:
            with self.subTest(pid=pid):
                c = Context(pid)
                specs = c.specs()
                self.assertTrue(specs)
                self.assertEqual(len(specs), len({s.key for s in specs}))
                for spec in specs:
                    json.dumps(spec.state(c), allow_nan=False)
                self.assertEqual(c.commands, [])
                adapter = module("prod_" + pid).ADAPTER
                c.prod_id = "unrelated"
                self.assertEqual(adapter.entities(c), ())
                c.prod_id = pid.lower()
                self.assertTrue(adapter.entities(c))

    async def test_all_lights_power_and_report(self):
        for pid in (
            "ZG0X",
            "ZG0Y",
            "ZG0S",
            "ZG0R",
            "28RD",
            "ZG1I",
            "ZG0O",
            "20CL",
            "2AOS",
            "2JDD",
            "155F",
        ):
            c = Context(pid, {"switch": {"on": 0}})
            s = c.specs()[0]
            await s.actions["turn_on"](c, {})
            self.assertFalse(s.state(c)["is_on"])  # ACK must not fabricate state.
            c.states["switch"]["on"] = 1
            self.assertTrue(s.state(c)["is_on"])
            await s.actions["turn_off"](c, {})
            self.assertEqual(c.commands, [("switch", {"on": 1}), ("switch", {"on": 0})])

    async def test_dimming_kelvin_and_mode_order(self):
        for pid in ["20CL", "155F", "2JDD", "2AOS", "ZG1I", "ZG0O"]:
            c = Context(pid, {"brightness": {"brightness": 100}})
            s = c.specs()[0]
            self.assertEqual(s.state(c)["brightness"], 255)
            await s.actions["turn_on"](
                c, {"brightness": 128, "color_temp_kelvin": 3500}
            )
            expected = [("switch", {"on": 1}), ("brightness", {"brightness": 50})]
            if pid == "ZG0O":
                expected.append(("colourMode", {"mode": 1}))
            expected.append(("cct", {"colorTemperature": 3500}))
            self.assertEqual(c.commands, expected)

    async def test_invalid_light_input_sends_nothing(self):
        for bad in [-1, 256, float("nan"), float("inf"), "invalid", True]:
            c = Context("20CL")
            with self.assertRaises(ValueError):
                await c.specs()[0].actions["turn_on"](c, {"brightness": bad})
            self.assertEqual(c.commands, [])
        for data in [{"rgb_color": (255, 0, 0)}, {"color_temp_kelvin": float("nan")}]:
            c = Context("ZG0O")
            with self.assertRaises(ValueError):
                await c.specs()[0].actions["turn_on"](c, data)
            self.assertEqual(c.commands, [])

    async def test_zero_brightness_still_validates_other_parameters(self):
        c = Context("20CL")
        with self.assertRaises(ValueError):
            await c.specs()[0].actions["turn_on"](
                c, {"brightness": 0, "color_temp_kelvin": float("nan")}
            )
        self.assertEqual(c.commands, [])

    async def test_zero_brightness_and_onoff_only(self):
        c = Context("20CL")
        await c.specs()[0].actions["turn_on"](c, {"brightness": 0})
        self.assertEqual(c.commands, [("switch", {"on": 0})])
        c = Context("ZG0X")
        with self.assertRaises(ValueError):
            await c.specs()[0].actions["turn_on"](c, {"brightness": 100})
        self.assertEqual(c.commands, [])

    async def test_missing_mode_fails_before_power(self):
        c = Context("ZG0O")
        c.profile["services"] = [
            s for s in c.profile["services"] if s["serviceId"] != "colourMode"
        ]
        with self.assertRaises(ValueError):
            await c.specs()[0].actions["turn_on"](c, {"color_temp_kelvin": 3500})
        self.assertEqual(c.commands, [])

    async def test_rejected_command_aborts_remaining_steps(self):
        c = Context("ZG0O")
        c.fail_sid = "colourMode"
        with self.assertRaises(RuntimeError):
            await c.specs()[0].actions["turn_on"](c, {"color_temp_kelvin": 3500})
        self.assertEqual(c.commands, [("switch", {"on": 1})])

    async def test_curtain_commands_and_position_direction(self):
        for pid in ["27WB", "2N5R", "140B"]:
            c = Context(pid, {"opener": {"current": 0}})
            s = c.specs()[0]
            for action in ["open", "close", "stop"]:
                await s.actions[action](c, {})
            sid = "mode" if pid == "140B" else "action"
            self.assertEqual(c.commands, [(sid, {sid: v}) for v in [1, 0, 2]])
            if pid == "27WB":
                self.assertNotIn("set_position", s.actions)
                self.assertIsNone(s.state(c)["is_closed"])
            else:
                self.assertTrue(s.state(c)["is_closed"])
                await s.actions["set_position"](c, {"position": 55})
                self.assertEqual(c.commands[-1], ("opener", {"target": 55}))
                c.states["opener"]["current"] = 100
                self.assertFalse(s.state(c)["is_closed"])
                with self.assertRaises(ValueError):
                    await s.actions["set_position"](c, {"position": 101})

    async def test_blade_control_is_separate(self):
        c = Context("2N5R")
        await c.named("叶片目标角度").actions["set_value"](c, {"value": 50})
        await c.named("叶片停止").actions["press"](c, {})
        self.assertEqual(
            c.commands,
            [("rotationAngle", {"target": 50}), ("rotationAction", {"action": 2})],
        )

    def test_temperature_humidity_units_and_invalid_state(self):
        c = Context(
            "2OPO",
            {
                "temperature": {"current": 276},
                "humidity": {"current": 560},
                "battery": {"level": 76, "alarm": 0},
            },
        )
        for name, value in [("温度", 27.6), ("湿度", 56), ("电量", 76)]:
            self.assertEqual(c.named(name).state(c)["native_value"], value)
        self.assertFalse(c.named("低电量").state(c)["is_on"])
        c.states["temperature"]["current"] = float("nan")
        self.assertIsNone(c.named("温度").state(c)["native_value"])
        c.states["battery"]["alarm"] = 9
        self.assertIsNone(c.named("低电量").state(c)["is_on"])

    def test_water_scaling_and_units(self):
        c = Context(
            "2GIP",
            {
                "totalWater": {"current": 123},
                "totalGas": {"current": 456},
                "curWater": {"current": 78},
            },
        )
        for name, value, unit in [
            ("累计热水量", 12.3, "t"),
            ("累计燃气量", 45.6, "m³"),
            ("实时出水量", 7.8, "L"),
        ]:
            s = c.named(name)
            self.assertEqual(s.state(c)["native_value"], value)
            self.assertEqual(s.metadata["unit"], unit)

    async def test_water_controls(self):
        c = Context("2GIP")
        await c.named("目标温度").actions["set_value"](c, {"value": 40})
        await c.named("一键零冷水").actions["turn_on"](c, {})
        await c.named("增压大水量").actions["turn_off"](c, {})
        self.assertEqual(
            c.commands,
            [
                ("temperature", {"target": 40}),
                ("zeroColdSwitch", {"on": 1}),
                ("boostMode", {"on": 0}),
            ],
        )
        with self.assertRaises(ValueError):
            await c.named("目标温度").actions["set_value"](c, {"value": 1000})
        self.assertEqual(len(c.commands), 3)

    async def test_toilet_buttons_preserve_tested_toggle(self):
        c = Context("2N91", {"seatRing": {"on": 0}, "filpSwitch": {"on": 1}})
        for name in ["座圈开合", "盖板开合"]:
            s = c.named(name)
            self.assertEqual(s.platform, "button")
            await s.actions["press"](c, {})
        self.assertEqual(
            c.commands, [("seatRing", {"on": 1}), ("filpSwitch", {"on": 0})]
        )
        c.states["seatRing"] = {}
        with self.assertRaises(ValueError):
            await c.named("座圈开合").actions["press"](c, {})
        self.assertEqual(len(c.commands), 2)

    async def test_toilet_flush_dry_stop(self):
        c = Context("2N91")
        for name in ["小冲", "大冲", "停止清洗与烘干"]:
            await c.named(name).actions["press"](c, {})
        await c.named("烘干").actions["turn_on"](c, {})
        self.assertEqual(
            c.commands,
            [
                ("smallflushSwitch", {"on": 1}),
                ("bigflushSwitch", {"on": 1}),
                ("stop", {"action": 0}),
                ("dryingSwitch", {"on": 1}),
            ],
        )

    async def test_bath_standby_preserves_lighting_command(self):
        c = Context("29UZ", {"control": {"light": 1, "wind": 1}})
        s = c.named("待机")
        self.assertEqual(s.platform, "button")
        await s.actions["press"](c, {})
        self.assertEqual(c.commands, [("Switch", {"on1": 1})])
        self.assertEqual(c.states["control"]["light"], 1)
        for name, key in [
            ("照明", "light"),
            ("夜灯", "nightLight"),
            ("吹风", "wind"),
            ("换气", "ventilate"),
            ("干燥", "dry"),
        ]:
            await c.named(name).actions["turn_on"](c, {})
            self.assertEqual(c.commands[-1], ("control", {key: 1}))

    async def test_dehumidifier_commands_and_validation(self):
        c = Context(
            "29XC",
            {"switch": {"on": 1}, "HUM": {"display": 55}, "SetDUM": {"SetDUM": 50}},
        )
        s = c.named("除湿控制")
        self.assertEqual(s.metadata["device_class"], "dehumidifier")
        self.assertEqual(s.state(c)["current_humidity"], 55)
        await s.actions["set_humidity"](c, {"humidity": 60})
        await c.named("光催化").actions["turn_on"](c, {})
        await c.named("定时关机").actions["set_value"](c, {"value": 2})
        self.assertEqual(
            c.commands,
            [
                ("SetDUM", {"SetDUM": 60}),
                ("Purify", {"Purify": 1}),
                ("Countdown", {"Countdown": 2}),
            ],
        )
        with self.assertRaises(ValueError):
            await s.actions["set_humidity"](c, {"humidity": 31})
        with self.assertRaises(ValueError):
            await s.actions["set_mode"](c, {"mode": "invalid"})
        self.assertEqual(len(c.commands), 3)

    async def test_robot_actions(self):
        c = Context("A36L")
        for name in ["回充", "清扫", "暂停", "继续", "设备查找"]:
            await c.named(name).actions["press"](c, {})
        self.assertEqual(
            c.commands, [("action", {"action": v}) for v in [0, 1, 2, 19, 21]]
        )

    async def test_readonly_guard(self):
        c = Context("20CL")
        for s in c.profile["services"]:
            if s["serviceId"] == "cct":
                s["characteristics"][0]["method"] = "R"
        for sid, key, v in [("cct", "colorTemperature", 3500), ("missing", "on", 1)]:
            with self.assertRaises(ValueError):
                await module("prod_20CL")._send(c, sid, key, v)
        self.assertEqual(c.commands, [])

    async def test_every_explicit_control_accepts_schema_values(self):
        for pid in PROFILES:
            c = Context(pid, {"seatRing": {"on": 0}, "filpSwitch": {"on": 0}})
            for s in c.specs():
                with self.subTest(pid=pid, entity=s.name):
                    if s.platform == "switch":
                        await s.actions["turn_on"](c, {})
                        await s.actions["turn_off"](c, {})
                    elif s.platform == "number":
                        await s.actions["set_value"](c, {"value": s.metadata["min"]})
                    elif s.platform == "select":
                        for option in s.metadata["options"]:
                            await s.actions["select_option"](c, {"option": option})
                    elif s.platform == "button":
                        await s.actions["press"](c, {})


class RadarTests(unittest.IsolatedAsyncioTestCase):
    def context(self):
        return Context(
            "ZG0F",
            {
                "basicFence": {
                    "advancedPara": (1 << 25) | (1 << 29),
                    "delayTimeList": ",".join(["0"] * 16),
                },
                "userFence1": {
                    "fenceID": 1,
                    "fenceName": "Zone A",
                    "fenceType": 0,
                    "enableFence": 1,
                },
                "userFence2": {
                    "fenceID": 2,
                    "fenceName": "Zone B",
                    "fenceType": 0,
                    "enableFence": 1,
                },
            },
        )

    async def test_flags_preserve_bits_and_wait_for_report(self):
        c = self.context()
        raw = c.states["basicFence"]["advancedPara"]
        await c.named("抗干扰增强").actions["turn_on"](c, {})
        self.assertEqual(c.commands[-1], ("basicFence", {"advancedPara": raw | 1}))
        self.assertFalse(c.named("抗干扰增强").state(c)["is_on"])
        with self.assertRaises(ValueError):
            await c.named("防宠检测").actions["turn_on"](c, {})
        c.states["basicFence"]["advancedPara"] = raw | 1
        await c.named("防宠检测").actions["turn_on"](c, {})
        self.assertEqual(c.commands[-1], ("basicFence", {"advancedPara": raw | 1 | 32}))

    async def test_rejected_flag_can_be_retried(self):
        c = self.context()
        c.fail_sid = "basicFence"
        with self.assertRaises(RuntimeError):
            await c.named("抗干扰增强").actions["turn_on"](c, {})
        c.fail_sid = None
        await c.named("抗干扰增强").actions["turn_on"](c, {})
        self.assertEqual(len(c.commands), 1)

    def test_unknown_mask_and_unsupported_pets(self):
        c = self.context()
        for value in [-1, 1]:
            c.states["basicFence"]["advancedPara"] = value
            self.assertNotIn("防宠检测", [s.name for s in c.specs()])

    async def test_region_response_preserves_other_entries(self):
        c = self.context()
        before = c.states["basicFence"]["delayTimeList"].split(",")
        await c.named("Zone A无人响应").actions["select_option"](
            c, {"option": "精准响应"}
        )
        before[1] = "2"
        self.assertEqual(
            c.commands[-1], ("basicFence", {"delayTimeList": ",".join(before)})
        )
        with self.assertRaises(ValueError):
            await c.named("Zone B无人响应").actions["select_option"](
                c, {"option": "精准响应"}
            )
        c.states["basicFence"]["delayTimeList"] = ",".join(before)
        await c.named("Zone B无人响应").actions["select_option"](
            c, {"option": "精准响应"}
        )
        before[2] = "2"
        self.assertEqual(c.commands[-1][1]["delayTimeList"], ",".join(before))

    async def test_changed_region_rejects_old_control(self):
        c = self.context()
        s = c.named("Zone A无人响应")
        c.states["userFence1"]["fenceID"] = 3
        with self.assertRaises(ValueError):
            await s.actions["select_option"](c, {"option": "精准响应"})
        self.assertEqual(c.commands, [])

    async def test_tuning_limits_and_reset(self):
        c = self.context()
        await c.named("检测灵敏度").actions["select_option"](c, {"option": "低"})
        await c.named("最小感应高度").actions["set_value"](c, {"value": 25})
        await c.named("重置无人状态").actions["press"](c, {})
        self.assertEqual(
            c.commands,
            [
                ("basicFence", {"sensitivity": 4}),
                ("basicFence", {"filteringHeight": 25}),
                ("action", {"action": 1}),
            ],
        )
        with self.assertRaises(ValueError):
            await c.named("最小感应高度").actions["set_value"](c, {"value": 23})
        with self.assertRaises(ValueError):
            await c.named("检测灵敏度").actions["select_option"](
                c, {"option": "未配置"}
            )
        self.assertEqual(len(c.commands), 3)

    def test_geometry_timestamp_and_unknown_position(self):
        c = self.context()
        c.states["basicFence"].update(
            locationList1="4,0,0,4,0,4,3,0,3", virtualWallList1="1,0,0,4,3"
        )
        c.states["userFence1"]["locationList"] = "0,0,2,0,2,2,0,2"
        c.states["basicFenceEvent"] = {
            "existent": 1,
            "postionTag": 1,
            "postionList": "1,2,0,3,4,0",
        }
        s = c.named("区域与人员位置")
        a = s.state(c)["extra_state_attributes"]
        self.assertEqual(len(a["positions"]), 2)
        self.assertEqual(len(a["regions"]), 2)
        self.assertTrue(a["position_valid"])
        self.assertEqual(
            s.metadata["attribute_update_timestamps"]["position_received_at"]["fields"],
            ("positionList", "postionList"),
        )
        c.states["basicFenceEvent"] = {"postionList": "nan,2,0"}
        a = s.state(c)["extra_state_attributes"]
        self.assertFalse(a["position_valid"])
        self.assertEqual(a["positions"], [])
        self.assertIsNone(a["occupied"])
        self.assertEqual(c.commands, [])


if __name__ == "__main__":
    unittest.main()
