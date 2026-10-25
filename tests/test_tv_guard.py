"""Tests for core/tv_guard.py against a fake TV that speaks the same broadcast protocol."""
import json
import os
import shlex
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import tv_guard  # noqa: E402
from core.tv_guard import GuardError, KeyStore, TvGuard  # noqa: E402


class FakeTv:
    """Minimal model of the TV side: package state, settings, and the CommandReceiver rules."""

    def __init__(self, clock_offset_s: int = 0, start_after_polls: int = 0):
        self.start_after_polls = start_after_polls
        self.status_polls = 0
        self.never_starts = False
        self.version = tv_guard.EXPECTED_VERSION
        self.overlay_broken = False
        self.installed = False
        self.enabled = []
        self.secret = None
        self.last_seq = 0
        self.pin_hash = None
        self.policy = None
        self.manual_lock_until = 0
        self.clock_offset_s = clock_offset_s
        self.available = True
        self.commands = []

    def now_ms(self) -> int:
        return int((time.time() + self.clock_offset_s) * 1000)

    # adb-shell device API used by adb_client.run_shell
    def shell(self, command, **_kw):
        self._stv_last_ok = time.monotonic()
        self.commands.append(command)
        if command.startswith("pm path"):
            return "package:/data/app/guard/base.apk\n" if self.installed else ""
        if command.startswith("pm uninstall"):
            if not self.installed:
                return "Failure [DELETE_FAILED_INTERNAL_ERROR]\n"
            self.installed, self.secret, self.pin_hash, self.policy = False, None, None, None
            self.enabled = []
            self.last_seq = 0
            return "Success\n"
        if command.startswith("settings get secure enabled_accessibility_services"):
            return (":".join(self.enabled) or "null") + "\n"
        if command.startswith("settings put secure enabled_accessibility_services"):
            self.enabled = shlex.split(command)[-1].split(":")
            return ""
        if command.startswith("settings put secure accessibility_enabled"):
            return ""
        if command.startswith("getprop persist.sys.timezone"):
            return "Asia/Ho_Chi_Minh\n"
        if command.startswith("date +%s"):
            return f"{self.now_ms() // 1000}\n"
        if command.startswith(("getprop ro.", "dumpsys", "logcat")) or "dumpsys package" in command or "dumpsys accessibility" in command:
            return "FAKE-DIAG\n"
        if command.startswith("cmd appops set"):
            self.commands.append("APPOPS")
            return ""
        if command.startswith(("cmd ", "dumpsys deviceidle")):
            return "FAKE-DIAG\n"
        if command.startswith("echo ok"):
            return "ok\n"
        if command.startswith("am broadcast"):
            return f'Broadcast completed: result=-1, data="{self._receive(shlex.split(command))}"\n'
        raise AssertionError(f"unexpected shell command: {command}")

    def _receive(self, argv):
        if not self.installed:
            return None  # callers never get here for an uninstalled app
        extras = {}
        i = 0
        while i < len(argv):
            if argv[i] == "--es":
                extras[argv[i + 1]] = argv[i + 2]
                i += 3
            else:
                i += 1
        cmd, payload = extras["cmd"], extras.get("payload", "")
        if cmd == "provision":
            if self.secret is not None:
                return "error:already_provisioned"
            self.secret = tv_guard.base64.urlsafe_b64decode(payload)
            return "ok"
        if self.secret is None:
            return "error:not_provisioned"
        seq = int(extras.get("seq", "0"))
        good = tv_guard.hmac.compare_digest(extras.get("sig", ""), tv_guard.sign(self.secret, cmd, seq, payload))
        if not good or seq <= self.last_seq or seq > self.now_ms() + 5 * 60 * 1000:
            return "error:auth"
        self.last_seq = seq
        text = tv_guard.base64.urlsafe_b64decode(payload).decode() if payload else ""
        if cmd == "ping":
            return "ok:pong"
        if cmd == "set_pin":
            self.pin_hash = text
            return "ok"
        if cmd == "set_policy":
            self.policy = json.loads(text)
            return "ok"
        if cmd == "lock_now":
            if not self.policy:
                return "error:no_policy"
            self.manual_lock_until = self.now_ms() + int(text) * 60_000
            return "ok"
        if cmd == "unlock_now":
            self.manual_lock_until = 0
            return "ok"
        if cmd == "status":
            self.status_polls += 1
            running = bool(self.enabled) and not self.never_starts and self.status_polls > self.start_after_polls
            decision = "LOCK" if self.manual_lock_until > self.now_ms() else "ALLOW"
            snap = {
                "version": self.version, "overlay_showing": decision == "LOCK" and not self.overlay_broken,
                "overlay_error": "BadTokenException: fake" if self.overlay_broken else None,
                "reason": "LOCKED_MANUAL" if decision == "LOCK" else "OUTSIDE_WINDOW",
                "zone": "Asia/Ho_Chi_Minh", "local_time": "2026-10-25T16:30:00", "local_day": 7,
                "running": running, "now_ms": self.now_ms(), "pin_set": bool(self.pin_hash),
                "policy_loaded": self.policy is not None, "policy": self.policy,
                "manual_lock_until_ms": self.manual_lock_until,
                "decision": "LOCK" if self.manual_lock_until > self.now_ms() else "ALLOW",
            }
            return "ok:" + json.dumps(snap, separators=(",", ":"))
        return "error:unknown_cmd"


class FakeInstaller:
    def __init__(self, tv):
        self.tv = tv

    def install(self, path, progress_cb=None, **_kw):
        self.tv.installed = True
        if progress_cb:
            progress_cb("Success")
        return {"ok": True, "output": "Success"}


POLICY = {"schedules": [{"days": [1, 2, 3, 4, 5, 6, 7], "start": "21:00", "end": "06:30"}], "unlock_minutes": 30}


class TvGuardFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.keys = KeyStore(self.tmp.name)
        self.tv = FakeTv()
        self.guard = TvGuard(self.tv, "192.168.1.50", 5555, keys=self.keys)
        self.steps = []
        self._orig_locate = tv_guard.locate_apk
        tv_guard.locate_apk = lambda on_step: "fake.apk"

    def tearDown(self):
        tv_guard.locate_apk = self._orig_locate
        self.tmp.cleanup()

    def on_step(self, msg, detail=""):
        self.steps.append(msg)

    def setup(self, pin="1234"):
        return self.guard.setup(FakeInstaller(self.tv), pin, POLICY, self.on_step)

    def test_fresh_setup_pairs_and_protects(self):
        info = self.setup()
        self.assertEqual(info["state"], "protected")
        self.assertTrue(self.tv.pin_hash.startswith("pbkdf2$"))
        self.assertNotIn("1234", self.tv.pin_hash)
        self.assertEqual(self.tv.policy["tz"], "Asia/Ho_Chi_Minh")
        self.assertEqual(self.steps[-1], "done")
        for stage in ("install", "enable", "pair", "pin", "policy", "verify"):
            self.assertIn(stage, self.steps)

    def test_setup_grants_auto_start_before_enabling_the_service(self):
        self.setup()
        cmds = self.tv.commands
        first_grant = next(i for i, c in enumerate(cmds) if c.startswith("cmd appops set") or c == "APPOPS")
        first_enable = next(i for i, c in enumerate(cmds) if c.startswith("settings put secure enabled_accessibility_services"))
        self.assertLess(first_grant, first_enable)
        self.assertTrue(any("AUTO_START" in c for c in cmds))

    def test_enabling_an_already_enabled_service_rewrites_the_setting_to_force_a_rebind(self):
        self.tv.installed = True
        self.tv.enabled = ["other/.Svc", tv_guard.SERVICE]
        self.guard.enable_accessibility()
        puts = [c for c in self.tv.commands if c.startswith("settings put secure enabled_accessibility_services")]
        self.assertEqual(len(puts), 2)
        self.assertNotIn("GuardService", puts[0])
        self.assertIn("GuardService", puts[1])
        self.assertIn("other/.Svc", puts[0])

    def test_second_setup_keeps_pairing_and_does_not_reinstall_from_scratch(self):
        self.setup()
        self.steps.clear()
        self.setup(pin="")
        self.assertNotIn("reset", self.steps)
        self.assertNotIn("pair", self.steps)
        self.assertNotIn("pin", self.steps)  # empty PIN keeps the existing one
        self.assertTrue(self.tv.pin_hash)

    def test_installed_without_local_key_is_reset_and_repaired(self):
        self.setup()
        self.keys.delete("192.168.1.50", 5555)  # e.g. setup was done from another PC
        self.steps.clear()
        info = self.setup()
        self.assertIn("reset", self.steps)
        self.assertEqual(info["state"], "protected")

    def test_mismatched_secret_triggers_reset(self):
        self.setup()
        self.tv.secret = b"x" * 32  # TV paired with someone else
        self.steps.clear()
        info = self.setup()
        self.assertIn("reset", self.steps)
        self.assertEqual(info["state"], "protected")

    def test_stale_local_key_is_dropped_on_fresh_install(self):
        self.keys.create("192.168.1.50", 5555)  # left over from a previous install
        info = self.setup()
        self.assertEqual(info["state"], "protected")

    def test_tv_clock_far_from_pc_clock_still_works(self):
        self.tv.clock_offset_s = -3600  # TV clock one hour behind this PC
        info = self.setup()
        self.assertEqual(info["state"], "protected")

    def test_rapid_commands_use_increasing_sequence_numbers(self):
        self.setup()
        for _ in range(5):
            self.guard.send("ping")

    def test_waits_for_a_slow_service_to_start(self):
        self.tv.start_after_polls = 3  # the service binds a few seconds after the setting is written
        orig_sleep = tv_guard.time.sleep
        tv_guard.time.sleep = lambda _s: None
        try:
            info = self.setup()
        finally:
            tv_guard.time.sleep = orig_sleep
        self.assertEqual(info["state"], "protected")
        self.assertIn("verify", self.steps)

    def test_service_that_never_starts_fails_with_diagnostics(self):
        self.tv.never_starts = True
        orig_sleep, orig_wait = tv_guard.time.sleep, tv_guard.SERVICE_WAIT_S
        tv_guard.time.sleep = lambda _s: None
        tv_guard.SERVICE_WAIT_S = 0.0
        try:
            with self.assertRaises(GuardError) as cm:
                self.guard.wait_running = lambda on_step, **_k: self.guard.summary()  # no real waiting
                self.setup()
        finally:
            tv_guard.time.sleep, tv_guard.SERVICE_WAIT_S = orig_sleep, orig_wait
        self.assertIn("trợ năng", str(cm.exception))
        self.assertIn("diag", self.steps)
        diag = [s for s in self.steps if s == "diag"]
        self.assertEqual(len(diag), 1)

    def test_diagnose_reports_every_section(self):
        self.setup()
        text = self.guard.diagnose()
        for section in ("== android ==", "== package ==", "== settings ==", "== accessibility ==", "== logcat ==", "== status command =="):
            self.assertIn(section, text)

    def test_service_off_state(self):
        self.setup()
        self.tv.enabled = []
        self.assertEqual(self.guard.summary()["state"], "service_off")

    def test_manual_lock_state_and_unlock(self):
        self.setup()
        self.guard.send("lock_now", "10")
        self.assertEqual(self.guard.summary()["state"], "locked_manual")
        self.guard.send("unlock_now", "0")
        self.assertEqual(self.guard.summary()["state"], "protected")

    def test_lock_that_cannot_draw_its_overlay_is_not_reported_as_locked(self):
        self.setup()
        self.tv.overlay_broken = True
        self.guard.send("lock_now", "10")
        info = self.guard.summary()
        self.assertEqual(info["state"], "lock_failed")
        self.assertIn("BadToken", info["status"]["overlay_error"])

    def test_outdated_tv_guard_is_flagged_for_update(self):
        self.setup()
        self.assertFalse(self.guard.summary()["update_available"])
        self.tv.version = "0.1.0-spike"
        info = self.guard.summary()
        self.assertTrue(info["update_available"])
        self.assertEqual(info["state"], "protected")  # still works, just old

    def test_update_keeps_pairing_pin_and_policy(self):
        self.setup()
        self.tv.version = "0.1.0-spike"
        self.steps.clear()
        pin_before, secret_before = self.tv.pin_hash, self.tv.secret
        self.setup(pin="")
        self.assertNotIn("reset", self.steps)
        self.assertEqual(self.tv.pin_hash, pin_before)
        self.assertEqual(self.tv.secret, secret_before)

    def test_expected_version_matches_the_kotlin_constant(self):
        kt = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "tv-guard", "app", "src", "main", "java", "com", "smarttvmanager", "guard",
                          "BuildConfigLike.kt")
        with open(kt, encoding="utf-8") as f:
            self.assertIn(f'VERSION = "{tv_guard.EXPECTED_VERSION}"', f.read())

    def test_not_installed_summary(self):
        s = self.guard.summary()
        self.assertEqual(s["state"], "not_installed")
        self.assertIsNone(s["status"])

    def test_uninstall_removes_key(self):
        self.setup()
        self.guard.uninstall()
        self.assertIsNone(self.keys.load("192.168.1.50", 5555))
        self.assertEqual(self.guard.summary()["state"], "not_installed")

    def test_invalid_input_fails_before_touching_the_tv(self):
        with self.assertRaises(GuardError):
            self.guard.setup(FakeInstaller(self.tv), "12", POLICY, self.on_step)
        with self.assertRaises(GuardError):
            self.guard.setup(
                FakeInstaller(self.tv), "1234",
                {"schedules": [{"days": [], "start": "21:00", "end": "06:00"}]}, self.on_step,
            )
        self.assertEqual(self.tv.commands, [])


class PureHelpersTest(unittest.TestCase):
    def test_signature_matches_kotlin_fixture(self):
        # Same fixture as DesktopInteropTest.kt; if this changes, the TV rejects every command.
        secret = bytes(range(32))
        self.assertEqual(
            tv_guard.sign(secret, "set_policy", 1761370000000, "eyJtb2RlIjoiYWxsIn0="),
            "764e1fe274957e67d168d970734876fdb8e30eefcc1eaa2edb822ae365baabaa",
        )

    def test_pin_hash_matches_kotlin_fixture(self):
        self.assertEqual(
            tv_guard.hash_pin("2468", salt=bytes([3]) * 16, iterations=20000),
            "pbkdf2$20000$AwMDAwMDAwMDAwMDAwMDAw$MHVDWZ27xS2bdIuVTSux98T2ddHjD7bjI1dzbj-y3ik",
        )

    def test_parse_broadcast_result(self):
        out = 'Broadcasting: Intent {...}\nBroadcast completed: result=-1, data="ok:{\\"a\\":1}"\n'
        self.assertEqual(tv_guard.parse_broadcast_result(out), 'ok:{\\"a\\":1}')
        with self.assertRaises(GuardError):
            tv_guard.parse_broadcast_result("Broadcast completed: result=0")

    def test_error_codes_become_friendly_messages(self):
        with self.assertRaises(GuardError) as cm:
            tv_guard.check_result("error:auth")
        self.assertEqual(cm.exception.code, "auth")
        self.assertIn("khoá", str(cm.exception).lower())

    def test_normalize_policy_rejects_bad_windows(self):
        bad = [
            {"schedules": [{"days": [1], "start": "10:00", "end": "10:00"}]},
            {"schedules": [{"days": [8], "start": "10:00", "end": "11:00"}]},
            {"schedules": [{"days": [1], "start": "25:00", "end": "11:00"}]},
        ]
        for raw in bad:
            with self.assertRaises(GuardError):
                tv_guard.normalize_policy(raw)

    def test_broadcast_command_quotes_values(self):
        line = tv_guard.build_broadcast_cmd("lock_now", "30", b"s" * 32, 5)
        argv = shlex.split(line)
        self.assertEqual(argv[:2], ["am", "broadcast"])
        self.assertIn("MzA=", argv)  # base64 payload survives intact


if __name__ == "__main__":
    unittest.main()
