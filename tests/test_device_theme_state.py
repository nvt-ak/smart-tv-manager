import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    import webview  # noqa: F401
except ImportError:  # the GUI toolkit is not needed to test the Api methods
    sys.modules["webview"] = mock.MagicMock()

import settings_store  # noqa: E402
from main import Api  # noqa: E402


class LastThemePerDeviceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        patcher = mock.patch.object(settings_store, "SETTINGS_PATH", os.path.join(self.tmp, "settings.json"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_each_tv_keeps_its_own_last_theme(self):
        settings_store.set_last_theme("192.168.1.4", 5555, "ha-noi-night-3")
        settings_store.set_last_theme("192.168.1.9", 5555, "crimson")
        self.assertEqual(settings_store.get_last_theme("192.168.1.4", 5555), "ha-noi-night-3")
        self.assertEqual(settings_store.get_last_theme("192.168.1.9", 5555), "crimson")

    def test_unknown_tv_never_inherits_another_tvs_theme(self):
        settings_store.set_last_theme("192.168.1.4", 5555, "ha-noi-night-3")
        self.assertEqual(settings_store.get_last_theme("192.168.1.50", 5555), "")
        # The global value stays as the default for the widget preview only.
        self.assertEqual(settings_store.load().get("last_theme_id"), "ha-noi-night-3")

    def test_port_is_part_of_the_device(self):
        settings_store.set_last_theme("192.168.1.4", 5555, "a")
        self.assertEqual(settings_store.get_last_theme("192.168.1.4", 5556), "")


class ThemeShotPerDeviceTest(unittest.TestCase):
    def test_live_capture_path_differs_per_device(self):
        with mock.patch("os.path.expanduser", return_value=tempfile.mkdtemp()):
            a = Api.theme_shot_path("ha-noi-night-3", "192.168.1.4", 5555)
            b = Api.theme_shot_path("ha-noi-night-3", "192.168.1.9", 5555)
            plain = Api.theme_shot_path("ha-noi-night-3")
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, plain)
        self.assertTrue(a.endswith(".jpg"))


if __name__ == "__main__":
    unittest.main()
