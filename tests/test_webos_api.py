"""LG acceptance: platform isolation at the public API boundary (no TV required)."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import webview  # noqa: F401
except ImportError:
    sys.modules["webview"] = mock.MagicMock()

import adb_client
import main
import store

HOST = "192.168.1.90"


class DeviceStoreAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(store, "PATH", os.path.join(self.tmp.name, "devices.json"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_old_devices_remain_android_and_keep_custom_ports(self):
        store.save([{"host": HOST, "name": "Old", "port": 5566}, {"host": "old", "name": "Default"}])
        first, second = store.load()
        self.assertEqual(first["platform"], "android_tv")
        self.assertEqual(first["port"], 5566)
        self.assertEqual(second["port"], 5555)

    def test_upsert_keeps_existing_metadata_without_credentials(self):
        store.upsert(HOST, 3001, "LG", platform="lg_webos", model="C6", developer_device="living-room")
        store.upsert(HOST, 3001, "LG renamed", platform="lg_webos")
        device = store.load()[0]
        self.assertEqual(device["platform"], "lg_webos")
        self.assertEqual(device["model"], "C6")
        self.assertEqual(device["developer_device"], "living-room")
        self.assertEqual(device["name"], "LG renamed")


class LgApiAcceptance(unittest.TestCase):
    def setUp(self):
        self.api = main.Api()
        self.lg = mock.Mock()
        self.lg.get_info.return_value = {"model": "OLED C6", "webos": "26"}
        self.lg.list_apps.return_value = [{"id": "netflix", "title": "Netflix"}]
        self.lg.list_inputs.return_value = [{"id": "HDMI_1", "label": "Console"}]
        self.api._get_webos = mock.Mock(return_value=self.lg)
        saved = [{"host": HOST, "port": 3001, "name": "LG", "platform": "lg_webos"}]
        patcher = mock.patch.object(store, "load", return_value=saved)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(adb_client, "connect", side_effect=AssertionError("LG must never connect ADB"))
        self.adb_connect = patcher.start()
        self.addCleanup(patcher.stop)

    def test_explicit_lg_connect_uses_lg_default_and_stores_platform(self):
        with mock.patch.object(store, "upsert") as upsert:
            info = self.api.connect(HOST, platform="lg_webos")
        self.api._get_webos.assert_called_with(HOST, 3001)
        self.assertEqual(info["platform"], "lg_webos")
        self.assertEqual(upsert.call_args.kwargs["platform"], "lg_webos")
        self.adb_connect.assert_not_called()

    def test_saved_lg_reconnect_does_not_require_platform_argument(self):
        with mock.patch.object(store, "upsert"):
            info = self.api.connect(HOST, 3001)
        self.assertEqual(info["platform"], "lg_webos")
        self.adb_connect.assert_not_called()

    def test_lg_pairing_failure_does_not_save_connected_device(self):
        self.api._get_webos.side_effect = RuntimeError("Pairing rejected")
        with mock.patch.object(store, "upsert") as upsert:
            with self.assertRaisesRegex(Exception, "Pairing rejected"):
                self.api.connect(HOST, 3001, platform="lg_webos")
        upsert.assert_not_called()

    def test_numeric_remote_and_text_dispatch_to_lg(self):
        self.api.remote_key(HOST, 3001, 3)
        self.assertEqual(self.lg.remote.call_count, 1)
        self.assertEqual(str(self.lg.remote.call_args.args[0]).lower(), "home")
        self.api.send_input_text(HOST, 3001, "Tìm kiếm tiếng Việt")
        self.lg.send_text.assert_called_once_with("Tìm kiếm tiếng Việt")
        self.adb_connect.assert_not_called()

    def test_lg_app_list_retains_title_and_has_no_android_management(self):
        result = self.api.list_apps(HOST, 3001)
        app = result["apps"][0]
        self.assertEqual(app["package"], "netflix")
        self.assertEqual(app["name"], "Netflix")
        self.assertEqual(app["type"], "user")
        self.assertTrue(app["enabled"])
        self.assertFalse(app["can_disable"])
        self.api.app_action(HOST, 3001, "open", "netflix")
        self.lg.launch_app.assert_called_once_with("netflix")
        self.adb_connect.assert_not_called()

    def test_inputs_dispatch_without_android_shell(self):
        result = self.api.list_inputs(HOST, 3001)
        rows = result.get("inputs") if isinstance(result, dict) else result
        self.assertEqual(rows[0]["id"], "HDMI_1")
        self.api.switch_input(HOST, 3001, "HDMI_1")
        self.lg.switch_input.assert_called_once_with("HDMI_1")
        self.adb_connect.assert_not_called()

    def test_android_transport_gate_blocks_saved_lg_even_on_android_port(self):
        with self.assertRaises(Exception):
            self.api._get_dev(HOST, 5555)
        self.adb_connect.assert_not_called()

    def test_unsupported_mutations_never_acquire_android_transport(self):
        operations = [
            lambda: self.api.app_action(HOST, 3001, "disable", "netflix"),
            lambda: self.api.app_action(HOST, 3001, "uninstall", "netflix"),
            lambda: self.api.device_shell(HOST, 3001, "id"),
            lambda: self.api.capture_screenshot(HOST, 3001),
            lambda: self.api.set_default_home(HOST, 3001),
            lambda: self.api.guard_status(HOST, 3001),
            lambda: self.api.smart_clean_apply(HOST, 3001, ["netflix"]),
        ]
        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaises(Exception):
                    operation()
        self.adb_connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
