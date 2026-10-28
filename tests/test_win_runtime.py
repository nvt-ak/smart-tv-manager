"""Windows startup hardening contracts (portable parts only)."""
import os
import tempfile
import unittest
from unittest.mock import patch

import win_runtime


class UnblockTests(unittest.TestCase):
    def test_noop_off_windows(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(win_runtime.os, "name", "posix"):
            self.assertEqual(win_runtime.unblock_tree(tmp), 0)

    def test_removes_stream_for_every_file_and_ignores_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            sub = os.path.join(tmp, "a", "b"); os.makedirs(sub)
            for p in (os.path.join(tmp, "x.dll"), os.path.join(sub, "y.dll")):
                open(p, "w").close()
            blocked = {os.path.join(tmp, "x.dll") + win_runtime.ZONE_STREAM,
                       os.path.join(sub, "y.dll") + win_runtime.ZONE_STREAM}
            removed = []

            def fake_remove(path):
                if path in blocked:
                    removed.append(path)
                    return
                raise FileNotFoundError(path)

            real_name = os.name
            with patch.object(win_runtime.os, "name", "nt"), patch.object(win_runtime.os, "remove", fake_remove), \
                    patch("os.walk", wraps=os.walk):
                count = win_runtime.unblock_tree(tmp)
            self.assertEqual(count, 2)
            self.assertEqual(set(removed), blocked)
            self.assertEqual(os.name, real_name)


class DiagnosisTests(unittest.TestCase):
    def test_missing_runtime_files_detected_and_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(set(win_runtime.missing_runtime_files(tmp)), set(win_runtime.REQUIRED_RUNTIME_FILES))
            msg = win_runtime.explain_failure(RuntimeError("boom"), tmp)
            self.assertIn("Python.Runtime.dll", msg)
            self.assertIn("boom", msg)

    def test_complete_bundle_gets_unblock_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            for rel in win_runtime.REQUIRED_RUNTIME_FILES:
                path = os.path.join(tmp, "_internal", rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                open(path, "w").close()
            self.assertEqual(win_runtime.missing_runtime_files(tmp), [])
            self.assertIn("Unblock", win_runtime.explain_failure(RuntimeError("x"), tmp))


class GuardedStartTests(unittest.TestCase):
    def test_failure_is_logged_shown_and_exits(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict(os.environ, {"LOCALAPPDATA": tmp}), \
                patch.object(win_runtime, "show_fatal") as shown:
            def boom():
                raise RuntimeError("Failed to resolve Python.Runtime.Loader.Initialize")
            with self.assertRaises(SystemExit):
                win_runtime.start_guarded(boom, tmp, "App")
            shown.assert_called_once()
            with open(win_runtime.log_path(), encoding="utf-8") as fh:
                self.assertIn("Loader.Initialize", fh.read())

    def test_success_passes_through(self):
        calls = []
        win_runtime.start_guarded(lambda: calls.append(1), tempfile.gettempdir(), "App")
        self.assertEqual(calls, [1])


if __name__ == "__main__":
    unittest.main()
