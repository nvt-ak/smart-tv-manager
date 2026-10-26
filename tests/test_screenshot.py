"""capture_screenshot pulls the TV's PNG to the PC and removes the temporary file on the TV."""
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

import adb_client  # noqa: E402
import main  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 32


class FakeDev:
    def __init__(self):
        self.pulled = []

    def pull(self, src, dst, **kwargs):
        self.pulled.append(src)
        with open(dst, "wb") as f:
            f.write(PNG)


class CaptureScreenshotTests(unittest.TestCase):
    def _api(self, shell_out="-rw------- 1 shell shell 1234 smarttvmanager-shot.png"):
        api = main.Api()
        dev = FakeDev()
        api._get_dev = lambda host, port=5555: dev
        cmds = []

        def fake_shell(device, cmd, timeout=None):
            cmds.append(cmd)
            return shell_out

        return api, dev, cmds, fake_shell

    def test_pulls_png_to_pc_and_cleans_up(self):
        api, dev, cmds, fake_shell = self._api()
        with tempfile.TemporaryDirectory() as home, \
                mock.patch.object(adb_client, "run_shell", fake_shell), \
                mock.patch("os.path.expanduser", return_value=home):
            res = api.capture_screenshot("192.168.1.50")
            self.assertTrue(os.path.isfile(res["path"]))
            self.assertTrue(res["path"].startswith(home))
            self.assertEqual(res["bytes"], len(PNG))
            self.assertTrue(res["name"].endswith(".png"))
        self.assertEqual(dev.pulled, ["/data/local/tmp/smarttvmanager-shot.png"])
        self.assertTrue(any("screencap -p" in c for c in cmds))
        self.assertTrue(cmds[-1].startswith("rm -f"))

    def test_tv_that_cannot_capture_raises(self):
        api, dev, cmds, fake_shell = self._api("ls: No such file or directory")
        with tempfile.TemporaryDirectory() as home, \
                mock.patch.object(adb_client, "run_shell", fake_shell), \
                mock.patch("os.path.expanduser", return_value=home):
            with self.assertRaises(Exception):
                api.capture_screenshot("192.168.1.50")
        self.assertEqual(dev.pulled, [])


class ThemeShotTests(unittest.TestCase):
    def test_keeps_a_1280x720_jpeg_per_theme(self):
        from PIL import Image
        api = main.Api()
        with tempfile.TemporaryDirectory() as home, mock.patch("os.path.expanduser", return_value=home):
            src = os.path.join(home, "full.png")
            Image.new("RGB", (1920, 1080), (10, 20, 30)).save(src)
            api.capture_screenshot = lambda host, port=5555: {"path": src, "name": "full.png", "bytes": 1}
            res = api.capture_theme_screenshot("192.168.1.50", 5555, "aurora-midnight", delay_s=0)
            self.assertTrue(res["path"].endswith("aurora-midnight.jpg"))
            with Image.open(res["path"]) as im:
                self.assertEqual(im.size, (1280, 720))
            self.assertTrue(res["jpg_b64"])


if __name__ == "__main__":
    unittest.main()
