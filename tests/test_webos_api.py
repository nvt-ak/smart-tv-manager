"""LG acceptance: platform isolation at the public API boundary (no TV required)."""
import json
import os
import sys
import tempfile
import threading
import time
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
from core import webos_client, webos_home
from core.webos_client import WebOsCommandError, WebOsError

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
        store.upsert(HOST, 3001, "LG", platform="lg_webos", model="C6", developer_device="living-room",
                     client_key="pair-secret", secret="guard-secret", private_key="ssh-secret")
        store.upsert(HOST, 3001, "LG renamed", platform="lg_webos")
        device = store.load()[0]
        self.assertEqual(device["platform"], "lg_webos")
        self.assertEqual(device["model"], "C6")
        self.assertEqual(device["developer_device"], "living-room")
        self.assertEqual(device["name"], "LG renamed")
        self.assertFalse({"client_key", "secret", "private_key"}.intersection(device))

    def test_upsert_drops_metadata_that_is_not_allowlisted(self):
        store.upsert(HOST, 3001, "LG", platform="lg_webos", model="C6", token="pair-secret", note="x")
        device = store.load()[0]
        self.assertEqual(device["model"], "C6")
        self.assertFalse({"token", "note"}.intersection(device))


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

    def test_actual_manager_remote_buttons_map_to_supported_lg_commands(self):
        # These keycodes come from ui/index.html, including Settings vs Input.
        expected = {24: ("volume_up", "volumeup"), 25: ("volume_down", "volumedown"),
                    166: ("channel_up", "channelup"), 167: ("channel_down", "channeldown"),
                    176: ("settings",), 178: ("input",)}
        for keycode, semantics in expected.items():
            with self.subTest(keycode=keycode):
                self.api.remote_key(HOST, 3001, keycode)
                self.assertIn(self.lg.remote.call_args.args[0], semantics)

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


class InlineThread:
    """Run a queued job immediately, so assertions do not race real threads."""
    def __init__(self, target, **kwargs):
        self.target = target

    def start(self):
        self.target()


class LgThemeApplyAcceptance(unittest.TestCase):
    def setUp(self):
        LgApiAcceptance.setUp(self)
        self.theme_id = "aurora-midnight"
        self.theme = next(t for t in self.api._themes.list_themes() if t["id"] == self.theme_id)

    def _apply(self, deploy_error=None):
        with mock.patch.object(main.threading, "Thread", InlineThread), \
                mock.patch.object(main.home_widgets, "widgets_data", return_value={"generated": "12:00"}), \
                mock.patch.object(main.settings_store, "load", return_value={}), \
                mock.patch.object(main.settings_store, "set_last_theme") as save, \
                mock.patch.object(webos_home, "deploy", side_effect=deploy_error,
                                  return_value={"ok": True, "snapshot": True}) as deploy:
            response = self.api.webos_apply_theme_async(HOST, 3001, self.theme_id,
                                                         developer_device="living-room")
            status = self.api.apply_gathin_theme_job(response["job_id"])
        return status, save, deploy

    def test_theme_apply_reports_done_and_persists_only_after_deploy(self):
        status, save, deploy = self._apply()
        self.assertEqual(status["status"], "done")
        self.assertIsNone(status["error"])
        self.assertTrue(status["result"]["ok"])
        self.assertEqual(deploy.call_count, 1)
        self.assertEqual(deploy.call_args.args[1], "living-room")
        self.assertEqual(deploy.call_args.kwargs["expected_host"], HOST)
        save.assert_called_once_with(HOST, 3001, self.theme_id)
        self.adb_connect.assert_not_called()

    def test_failed_deploy_never_sets_last_theme_or_reports_done(self):
        status, save, deploy = self._apply(RuntimeError("Developer Mode expired"))
        self.assertEqual(status["status"], "failed")
        self.assertIn("Developer Mode expired", status["error"])
        save.assert_not_called()
        self.adb_connect.assert_not_called()

    def test_shared_display_name_enters_snapshot_without_mutating_catalog(self):
        import copy
        source = copy.deepcopy(self.theme)
        original_build = webos_home.build_bundle
        snapshots = []

        def build(*args, **kwargs):
            directory = original_build(*args, **kwargs)
            with open(os.path.join(directory, "runtime.json"), encoding="utf-8") as stream:
                snapshots.append(json.load(stream))
            return directory

        with mock.patch.object(main.settings_store, "get_home_widgets",
                               return_value={"enabled": True, "display_name": "Gia đình Tài", "show_name": True}), \
                mock.patch.object(main.home_widgets, "build_board_lines", return_value=([], {})), \
                mock.patch.object(webos_home, "build_bundle", side_effect=build):
            status, _, _ = self._apply()
        self.assertEqual(status["status"], "done")
        self.assertEqual(snapshots[0]["config"]["greeting_name"], "Gia đình Tài")
        self.assertEqual(self.theme, source)

    def test_unknown_theme_is_rejected_without_deploy_or_state_change(self):
        with mock.patch.object(main.threading, "Thread", InlineThread), \
                mock.patch.object(main.settings_store, "set_last_theme") as save, \
                mock.patch.object(webos_home, "deploy") as deploy:
            with self.assertRaisesRegex(Exception, "Theme không tồn tại"):
                self.api.webos_apply_theme_async(HOST, 3001, "../../not-a-theme")
        save.assert_not_called()
        deploy.assert_not_called()
        self.assertEqual(self.api._webos_deploying, set())

    def test_webos_theme_apply_refuses_android_device(self):
        with mock.patch.object(store, "load", return_value=[]), \
                mock.patch.object(webos_home, "deploy") as deploy:
            with self.assertRaises(Exception):
                self.api.webos_apply_theme_async("android", 5555, self.theme_id)
        deploy.assert_not_called()

    def test_denied_input_list_does_not_fail_apply(self):
        self.lg.list_inputs.side_effect = WebOsCommandError("403 access denied")
        status, save, deploy = self._apply()
        self.assertEqual(status["status"], "done")
        save.assert_called_once()
        self.assertEqual(deploy.call_count, 1)

    def test_transport_failure_reading_apps_still_fails_apply(self):
        self.lg.list_apps.side_effect = WebOsError("LG đã đóng kết nối.")
        status, save, deploy = self._apply()
        self.assertEqual(status["status"], "failed")
        save.assert_not_called()
        deploy.assert_not_called()


class LgDeploymentConcurrency(unittest.TestCase):
    def setUp(self):
        LgApiAcceptance.setUp(self)
        self.theme_id = "aurora-midnight"

    def test_deploy_neither_blocks_the_tv_nor_allows_a_second_apply(self):
        observed = {}

        def deploy(*args, **kwargs):
            lock = self.api._dev_op_lock(HOST, 3001)
            probe = []

            def try_lock():  # a remote key press would need this lock from another thread
                got = lock.acquire(timeout=1)
                probe.append(got)
                if got:
                    lock.release()

            thread = threading.Thread(target=try_lock)
            thread.start()
            thread.join()
            observed["lock_free"] = probe == [True]
            try:
                self.api.webos_apply_theme_async(HOST, 3001, self.theme_id)
            except Exception as exc:
                observed["second_apply"] = str(exc)
            return {"ok": True, "snapshot": True}

        with mock.patch.object(main.home_widgets, "widgets_data", return_value={"generated": "12:00"}), \
                mock.patch.object(main.settings_store, "load", return_value={}), \
                mock.patch.object(main.settings_store, "set_last_theme"), \
                mock.patch.object(webos_home, "deploy", side_effect=deploy):
            job_id = self.api.webos_apply_theme_async(HOST, 3001, self.theme_id)["job_id"]
            deadline = time.monotonic() + 20
            while self.api.apply_gathin_theme_job(job_id)["status"] == "running":
                self.assertLess(time.monotonic(), deadline, "apply job did not finish")
                time.sleep(0.02)
            status = self.api.apply_gathin_theme_job(job_id)
            self.assertEqual(status["status"], "done", status["error"])
            self.assertTrue(observed["lock_free"], "deploy must not hold the per-TV operation lock")
            self.assertIn("Đang cài Home webOS", observed["second_apply"])
            # The slot is released afterwards, so a later Apply is accepted again.
            again = self.api.webos_apply_theme_async(HOST, 3001, self.theme_id)["job_id"]
            while self.api.apply_gathin_theme_job(again)["status"] == "running":
                time.sleep(0.02)


class LgDeviceLifecycle(unittest.TestCase):
    def setUp(self):
        LgApiAcceptance.setUp(self)
        self.keys_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.keys_dir.cleanup)
        for patcher in (mock.patch.object(webos_client, "user_data_dir", return_value=self.keys_dir.name),
                        mock.patch.object(store, "remove", return_value=[])):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.keys = webos_client.WebOsKeyStore()
        for endpoint in ((HOST, 3001), (HOST, 3000), ("192.168.1.91", 3001)):
            self.keys.save(webos_client.identity_for(*endpoint),
                           {"client_key": "k", "certificate_sha256": "pin"})

    def test_removing_an_lg_tv_forgets_its_pairing_but_not_other_tvs(self):
        cached = mock.Mock()
        self.api._webos_cache[f"{HOST}:3001"] = cached
        self.api.remove(HOST)
        cached.close.assert_called_once()
        self.assertEqual(self.api._webos_cache, {})
        self.assertEqual(self.keys.load(webos_client.identity_for(HOST, 3001)), {})
        self.assertEqual(self.keys.load(webos_client.identity_for(HOST, 3000)), {})
        self.assertEqual(self.keys.load(webos_client.identity_for("192.168.1.91", 3001))["client_key"], "k")

    def test_removing_an_android_tv_leaves_webos_keys_alone(self):
        store.load.return_value = [{"host": HOST, "port": 5555, "platform": "android_tv"}]
        self.api.remove(HOST)
        self.assertEqual(self.keys.load(webos_client.identity_for(HOST, 3001))["client_key"], "k")

    def test_forget_pairing_clears_key_and_certificate_pin_on_every_endpoint(self):
        result = self.api.forget_webos_pairing(HOST)
        self.assertTrue(result["removed"])
        for port in (3000, 3001):
            self.assertEqual(self.keys.load(webos_client.identity_for(HOST, port)), {})
        self.assertFalse(self.api.forget_webos_pairing(HOST)["removed"])

    def test_forget_pairing_is_refused_for_android(self):
        store.load.return_value = [{"host": HOST, "port": 5555, "platform": "android_tv"}]
        with self.assertRaises(Exception):
            self.api.forget_webos_pairing(HOST)
        self.assertEqual(self.keys.load(webos_client.identity_for(HOST, 3001))["client_key"], "k")

    def test_saved_port_wins_over_the_android_default_argument(self):
        self.api.remote_key(HOST, 5555, 3)
        self.api._get_webos.assert_called_with(HOST, 3001)
        self.api.list_apps(HOST)
        self.api._get_webos.assert_called_with(HOST, 3001)

    def test_platform_lookup_is_cached_and_cleared_by_remove(self):
        store.load.reset_mock()
        for _ in range(5):
            self.assertEqual(self.api._device_platform(HOST), "lg_webos")
        self.assertEqual(store.load.call_count, 1)
        self.api.remove(HOST)
        store.load.return_value = []
        self.assertEqual(self.api._device_platform(HOST), "android_tv")


if __name__ == "__main__":
    unittest.main()
