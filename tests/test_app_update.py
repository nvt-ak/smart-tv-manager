import json
import os
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import app_update  # noqa: E402

BASE = app_update.DOWNLOAD_PREFIX + "v1.9.0/"


def release(tag="v1.9.0", digest="sha256:" + "ab" * 32, url_prefix=BASE):
    return {
        "tag_name": tag,
        "body": "notes",
        "html_url": "https://github.com/nvt-ak/smart-tv-manager/releases/tag/" + tag,
        "assets": [
            {"name": "SmartTVManager-macos.dmg", "browser_download_url": url_prefix + "SmartTVManager-macos.dmg",
             "size": 10, "digest": digest},
            {"name": "SmartTVManager-windows-x64.zip", "browser_download_url": url_prefix + "SmartTVManager-windows-x64.zip",
             "size": 20, "digest": digest},
        ],
    }


class VersionTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(app_update.parse_version("v1.9.0"), (1, 9, 0))
        self.assertEqual(app_update.parse_version("1.10"), (1, 10))
        self.assertEqual(app_update.parse_version("v2.0.0-rc1"), (2, 0, 0))
        self.assertEqual(app_update.parse_version("nonsense"), ())

    def test_newer_compares_numbers_not_text(self):
        self.assertTrue(app_update.is_newer("1.10.0", "1.9.0"))
        self.assertTrue(app_update.is_newer("1.8.1", "1.8.0"))
        self.assertTrue(app_update.is_newer("1.9", "1.8.5"))
        self.assertFalse(app_update.is_newer("1.8.0", "1.8.0"))
        self.assertFalse(app_update.is_newer("1.8", "1.8.0"))
        self.assertFalse(app_update.is_newer("1.7.9", "1.8.0"))
        self.assertFalse(app_update.is_newer("", "1.8.0"))


class AssetTest(unittest.TestCase):
    def test_picks_the_file_of_the_platform(self):
        self.assertEqual(app_update.pick_asset(release(), "win32")["name"], "SmartTVManager-windows-x64.zip")
        self.assertEqual(app_update.pick_asset(release(), "darwin")["name"], "SmartTVManager-macos.dmg")
        self.assertIsNone(app_update.pick_asset(release(), "linux"))

    def test_digest_is_read(self):
        self.assertEqual(app_update.pick_asset(release(), "win32")["sha256"], "ab" * 32)
        self.assertEqual(app_update.pick_asset(release(digest=""), "win32")["sha256"], "")

    def test_foreign_download_url_is_refused(self):
        self.assertIsNone(app_update.pick_asset(release(url_prefix="https://evil.example/"), "win32"))

    def test_check_latest(self):
        body = json.dumps(release()).encode()
        info = app_update.check_latest("1.8.0", fetch=lambda url: body, platform="win32")
        self.assertTrue(info["available"])
        self.assertEqual(info["version"], "1.9.0")
        self.assertFalse(info["can_self_update"])  # not a frozen build in the tests
        same = app_update.check_latest("1.9.0", fetch=lambda url: body, platform="win32")
        self.assertFalse(same["available"])


class DownloadTest(unittest.TestCase):
    def test_refuses_url_outside_the_repo(self):
        with self.assertRaises(Exception):
            app_update.download({"name": "x.zip", "url": "https://evil.example/x.zip"}, lambda *_: None, tempfile.mkdtemp())

    def test_verify_size_and_checksum(self):
        asset = {"size": 5, "sha256": "aa" * 32}
        with self.assertRaises(Exception):
            app_update.download.__globals__["_verify"](4, "aa" * 32, asset)
        with self.assertRaises(Exception):
            app_update.download.__globals__["_verify"](5, "bb" * 32, asset)
        app_update.download.__globals__["_verify"](5, "aa" * 32, asset)
        # No digest published: the size alone is checked.
        app_update.download.__globals__["_verify"](5, "anything", {"size": 5, "sha256": ""})


class ScriptTest(unittest.TestCase):
    def test_windows_script_waits_copies_and_restarts(self):
        s = app_update.windows_script(4321, r"C:\tmp\new", r"C:\Apps\SmartTVManager", r"C:\Apps\SmartTVManager\SmartTVManager.exe", r"C:\tmp\e.log")
        self.assertIn('PID eq 4321', s)
        self.assertIn('robocopy "C:\\tmp\\new" "C:\\Apps\\SmartTVManager" /E', s)
        self.assertIn('start "" "C:\\Apps\\SmartTVManager\\SmartTVManager.exe"', s)
        self.assertLess(s.index("robocopy"), s.index("start"))
        self.assertNotIn("/MIR", s)

    def test_windows_script_rejects_paths_cmd_would_mangle(self):
        with self.assertRaises(Exception):
            app_update.windows_script(1, r"C:\a%b", r"C:\x", r"C:\x\a.exe", r"C:\l")

    def test_mac_script_quotes_paths_with_spaces(self):
        s = app_update.mac_script(77, "/Users/a b/up.dmg", "/Applications/SmartTV Manager.app", "/tmp/e.log")
        self.assertIn("kill -0 77", s)
        self.assertIn("'/Users/a b/up.dmg'", s)
        self.assertIn("'/Applications/SmartTV Manager.app.new'", s)
        self.assertIn("com.apple.quarantine", s)
        self.assertLess(s.index("cp -R"), s.index("\nopen "))


class ExtractTest(unittest.TestCase):
    def _zip(self, names):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "u.zip")
        with zipfile.ZipFile(path, "w") as z:
            for n in names:
                z.writestr(n, "x")
        return d, path

    def test_finds_the_folder_with_the_exe(self):
        d, path = self._zip(["SmartTVManager/SmartTVManager.exe", "SmartTVManager/_internal/a.dll"])
        root = app_update.extract_windows(path, d)
        self.assertTrue(os.path.isfile(os.path.join(root, "SmartTVManager.exe")))

    def test_zip_without_the_exe_is_refused(self):
        d, path = self._zip(["readme.txt"])
        with self.assertRaises(Exception):
            app_update.extract_windows(path, d)


class ProgressTest(unittest.TestCase):
    def test_progress_round_trip(self):
        p = app_update.Progress()
        self.assertEqual(p.get()["state"], "idle")
        p.set(state="downloading", done=5, total=10)
        self.assertEqual((p.get()["state"], p.get()["done"]), ("downloading", 5))


if __name__ == "__main__":
    unittest.main()
