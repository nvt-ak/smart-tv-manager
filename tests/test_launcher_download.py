"""The launcher APK is downloaded once per release: a cached copy that matches the published SHA-256 is reused."""
import hashlib
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import launcher_builder, launcher_download  # noqa: E402

APK = b"PK\x03\x04 pretend apk"
SHA = hashlib.sha256(APK).hexdigest()


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.apk = os.path.join(self.tmp.name, "smtv-home.apk")
        self.calls = []

        def fake_get(url, timeout=60.0):
            self.calls.append(url)
            return (SHA + "  smtv-home.apk\n").encode() if url.endswith(".sha256") else APK

        self.patches = [
            mock.patch.object(launcher_builder, "cached_apk_path", lambda: self.apk),
            mock.patch.object(launcher_download, "_get", fake_get),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_first_download_verifies_and_caches(self):
        path = launcher_download.download_apk(lambda *a: None)
        self.assertEqual(path, self.apk)
        self.assertEqual(launcher_download.cached_sha(), SHA)

    def test_current_cache_is_not_downloaded_again(self):
        launcher_download.download_apk(lambda *a: None)
        self.calls.clear()
        steps = []
        launcher_download.download_apk(lambda m, d="": steps.append(m))
        self.assertEqual([c for c in self.calls if not c.endswith(".sha256")], [])
        self.assertIn("download_cached", steps)

    def test_stale_cache_is_replaced(self):
        with open(self.apk, "wb") as f:
            f.write(b"old")
        launcher_download.download_apk(lambda *a: None)
        self.assertEqual(launcher_download.cached_sha(), SHA)

    def test_wrong_checksum_is_refused(self):
        with mock.patch.object(launcher_download, "_get",
                               lambda url, timeout=60.0: (b"0" * 64 if url.endswith(".sha256") else APK)):
            with self.assertRaises(Exception):
                launcher_download.download_apk(lambda *a: None)
        self.assertEqual(launcher_download.cached_sha(), "")


if __name__ == "__main__":
    unittest.main()
