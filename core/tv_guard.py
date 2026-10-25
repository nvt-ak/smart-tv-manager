"""TV Guard: install and control the on-TV screen-time companion app (see tv-guard/).

The enforcement runs on the TV itself, so this module only sets things up and sends signed
commands over ADB. Commands use `am broadcast`; every command except `provision` carries an HMAC
signature, see tv-guard/app/src/main/java/com/smarttvmanager/guard/CommandAuth.kt.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import shlex
import time
from typing import Callable, Optional

import adb_client
import paths

PACKAGE = "com.smarttvmanager.guard"
SERVICE = f"{PACKAGE}/{PACKAGE}.GuardService"
COMPONENT = f"{PACKAGE}/.CommandReceiver"
ACTION = f"{PACKAGE}.CMD"
# Version of the APK this app ships. Bump together with tv-guard/app/build.gradle.kts and
# BuildConfigLike.kt (a test keeps them in sync).
EXPECTED_VERSION = "0.2.1"
PIN_ITERATIONS = 120_000
SERVICE_WAIT_S = 25.0
SERVICE_POLL_S = 2.0
REBIND_PAUSE_S = 1.0
# TCL's TclAppBoot refuses to bind services (and to start a stopped process for a broadcast) for apps
# whose vendor op is not allowed: "forbid bind service ... callee_doesn't_have_OP_AUTO_START".
# On the TCL Google TV the op shows up in `cmd appops get` as APP_AUTO_START (mode "ignore" by
# default after every install). Other spellings are tried too for other vendors; unknown ones just fail.
AUTO_START_OPS = ("APP_AUTO_START", "AUTO_START", "OP_AUTO_START")
BACKGROUND_OPS = ("RUN_IN_BACKGROUND", "RUN_ANY_IN_BACKGROUND")
DEFAULT_TZ = "Asia/Ho_Chi_Minh"
KEYS_DIR = os.path.join(adb_client.KEY_DIR, "guard")

StepFn = Callable[[str, str], None]


class GuardError(Exception):
    """A failure the user can act on. `code` is the TV's error code when there is one."""

    def __init__(self, message: str, code: str = ""):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# Pure helpers (unit tested without a TV)
# ---------------------------------------------------------------------------

def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def hash_pin(pin: str, salt: Optional[bytes] = None, iterations: int = PIN_ITERATIONS) -> str:
    """`pbkdf2$<iterations>$<salt>$<hash>` (unpadded URL-safe base64), the format PinHasher.kt reads."""
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations, 32)
    return "$".join(["pbkdf2", str(iterations), b64u(salt).rstrip("="), b64u(dk).rstrip("=")])


def validate_pin(pin: str) -> str:
    pin = (pin or "").strip()
    if not pin.isdigit() or not 4 <= len(pin) <= 8:
        raise GuardError("PIN phải gồm 4–8 chữ số (remote TV chỉ nhập được số).")
    return pin


def sign(secret: bytes, cmd: str, seq: int, payload: str) -> str:
    # Must match CommandAuth.message(): "<cmd>\n<seq>\n<payload>".
    return hmac.new(secret, f"{cmd}\n{seq}\n{payload}".encode("utf-8"), hashlib.sha256).hexdigest()


def build_broadcast_cmd(cmd: str, payload_text: str, secret: Optional[bytes], seq: int) -> str:
    """Shell command line for the TV. Values are single-quoted for the TV's sh."""
    payload = b64u(payload_text.encode("utf-8")) if payload_text else ""
    parts = ["am", "broadcast", "-n", COMPONENT, "-a", ACTION, "--es", "cmd", cmd]
    if cmd != "provision":
        if secret is None:
            raise GuardError("Chưa có khoá điều khiển cho TV này.")
        parts += ["--es", "seq", str(seq), "--es", "sig", sign(secret, cmd, seq, payload)]
    parts += ["--es", "payload", payload]
    return " ".join(shlex.quote(p) for p in parts)


_RESULT_RE = re.compile(r'data="(.*)"\s*$', re.DOTALL)


def parse_broadcast_result(output: str) -> str:
    """Extract the receiver's result string from `am broadcast` output."""
    for line in reversed((output or "").strip().splitlines()):
        m = _RESULT_RE.search(line.strip())
        if m:
            return m.group(1)
    raise GuardError(
        "TV không trả kết quả từ TV Guard (app chưa chạy hoặc bị hệ thống chặn): "
        + ((output or "").strip()[:200] or "(trống)")
    )


ERROR_TEXT = {
    "auth": "Khoá điều khiển không khớp với TV (app đã được ghép cặp từ máy khác?).",
    "not_provisioned": "TV Guard chưa được ghép cặp với app này.",
    "already_provisioned": "TV Guard đã được ghép cặp với máy khác.",
    "provision_window_closed": "Đã quá 15 phút kể từ khi cài, không thể ghép cặp lần đầu.",
    "no_policy": "Chưa có lịch khoá trên TV.",
    "bad_pin_hash": "TV từ chối mã PIN (định dạng sai).",
}


def check_result(result: str) -> str:
    if result.startswith("error:"):
        code = result.split(":", 1)[1].split(":", 1)[0]
        msg = ERROR_TEXT.get(code) or f"TV Guard báo lỗi: {result[6:]}"
        raise GuardError(msg, code)
    return result


def normalize_policy(raw: dict, tz: str = DEFAULT_TZ) -> dict:
    """Validate a UI policy and return the JSON object the TV expects (mode "all" for now)."""
    schedules = []
    for s in raw.get("schedules") or []:
        days = sorted({int(d) for d in s.get("days") or []})
        if not days or any(d < 1 or d > 7 for d in days):
            raise GuardError("Mỗi khung giờ cần chọn ít nhất một ngày.")
        start, end = str(s.get("start", "")), str(s.get("end", ""))
        for t in (start, end):
            if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t):
                raise GuardError(f"Giờ không hợp lệ: {t!r} (dạng HH:MM).")
        if start == end:
            raise GuardError("Giờ bắt đầu và kết thúc không được trùng nhau.")
        schedules.append({"days": days, "start": start, "end": end})
    unlock = int(raw.get("unlock_minutes") or 30)
    if not 1 <= unlock <= 720:
        raise GuardError("Thời gian mở khoá phải từ 1 đến 720 phút.")
    return {
        "version": 1,
        "mode": "all",
        "apps": [],
        "schedules": schedules,
        "failsafe_hours": int(raw.get("failsafe_hours") or 12),
        "unlock_minutes": unlock,
        "tz": str(raw.get("tz") or tz),
    }


# ---------------------------------------------------------------------------
# Per-TV control key (stored next to the ADB key, owner-only)
# ---------------------------------------------------------------------------

class KeyStore:
    def __init__(self, directory: str = KEYS_DIR):
        self.directory = directory

    def _path(self, host: str, port: int) -> str:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", f"{host}_{int(port)}")
        return os.path.join(self.directory, f"{safe}.json")

    def load(self, host: str, port: int) -> Optional[bytes]:
        try:
            with open(self._path(host, port), encoding="utf-8") as f:
                return base64.urlsafe_b64decode(json.load(f)["secret"])
        except Exception:
            return None

    def create(self, host: str, port: int) -> bytes:
        secret = os.urandom(32)
        os.makedirs(self.directory, mode=0o700, exist_ok=True)
        path = self._path(host, port)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"secret": b64u(secret)}, f)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return secret

    def delete(self, host: str, port: int) -> None:
        try:
            os.remove(self._path(host, port))
        except OSError:
            pass


# ---------------------------------------------------------------------------
# APK source
# ---------------------------------------------------------------------------

def locate_apk(on_step: StepFn) -> str:
    """Local debug build if present (developer checkout), otherwise the prebuilt release."""
    override = os.environ.get("SMARTTV_GUARD_APK", "").strip()
    if override and os.path.isfile(override):
        on_step("apk", f"Dùng APK chỉ định: {override}")
        return override
    local = os.path.join(paths.app_root(), "tv-guard", "dist", "TvGuard-debug.apk")
    if os.path.isfile(local):
        on_step("apk", "Dùng bản build cục bộ (tv-guard/dist)")
        return local
    return _download_release(on_step)


def _download_release(on_step: StepFn) -> str:
    from core.launcher_download import _get  # shared HTTP helper with the certifi context

    with open(os.path.join(paths.app_root(), "data", "tvguard", "release.json"), encoding="utf-8") as f:
        pin = json.load(f)
    base = pin["release_base"].rstrip("/")
    on_step("apk", "Đang tải TV Guard dựng sẵn...")
    try:
        want = _get(f"{base}/{pin['sha256_file']}", 30).decode("utf-8", "replace").split()[0].lower()
        data = _get(f"{base}/{pin['apk']}", 300)
    except Exception as exc:
        raise GuardError(
            f"Không tải được TV Guard ({exc}). Release «tv-guard» có thể chưa được tạo: "
            "chạy workflow «Build TV Guard APK» trên GitHub."
        ) from exc
    got = hashlib.sha256(data).hexdigest()
    if len(want) != 64 or got != want:
        raise GuardError(f"SHA-256 không khớp (mong đợi {want[:12]}…, nhận {got[:12]}…) — huỷ để an toàn.")
    cache = os.path.join(adb_client.KEY_DIR, "cache")
    os.makedirs(cache, exist_ok=True)
    out = os.path.join(cache, "TvGuard.apk")
    with open(out, "wb") as f:
        f.write(data)
    on_step("apk", f"Đã tải {len(data) // 1024} KB · sha256 {got[:12]}…")
    return out


# ---------------------------------------------------------------------------
# Device control
# ---------------------------------------------------------------------------

class TvGuard:
    """Controls TV Guard on one TV. `dev` is a connected adb-shell device; the caller holds the
    per-device operation lock (adb-shell is not thread-safe)."""

    def __init__(self, dev, host: str, port: int = 5555, keys: Optional[KeyStore] = None):
        self.dev = dev
        self.host = host
        self.port = int(port)
        self.keys = keys or KeyStore()
        self._seq_base: Optional[int] = None
        self._seq_t0 = 0.0
        self._last_seq = 0

    # -- shell helpers ------------------------------------------------------
    def _shell(self, cmd: str, timeout: Optional[float] = None) -> str:
        return adb_client.run_shell(self.dev, cmd, timeout)

    def _next_seq(self) -> int:
        """Sequence numbers follow the TV's clock, not the PC's, because the TV rejects values
        more than 5 minutes ahead of its own time."""
        if self._seq_base is None:
            tv_ms = 0
            try:
                tv_ms = int(self._shell("date +%s").strip().splitlines()[-1]) * 1000
            except Exception:
                pass
            self._seq_base = tv_ms or int(time.time() * 1000)
            self._seq_t0 = time.monotonic()
        seq = self._seq_base + int((time.monotonic() - self._seq_t0) * 1000)
        self._last_seq = max(seq, self._last_seq + 1)
        return self._last_seq

    # -- state --------------------------------------------------------------
    def is_installed(self) -> bool:
        return "package:" in self._shell(f"pm path {PACKAGE}")

    def accessibility_enabled(self) -> bool:
        out = self._shell("settings get secure enabled_accessibility_services").strip()
        return SERVICE in out.split(":")

    def tv_timezone(self) -> str:
        tz = self._shell("getprop persist.sys.timezone").strip()
        return tz if re.fullmatch(r"[A-Za-z_]+(/[A-Za-z0-9_+-]+)+", tz) else DEFAULT_TZ

    # -- commands -----------------------------------------------------------
    def send(self, cmd: str, text: str = "", timeout: float = 20.0) -> str:
        secret = None if cmd == "provision" else self.keys.load(self.host, self.port)
        seq = 0 if cmd == "provision" else self._next_seq()
        line = build_broadcast_cmd(cmd, text, secret, seq)
        out = self._shell(line, timeout)
        return check_result(parse_broadcast_result(out))

    def provision(self) -> None:
        secret = self.keys.create(self.host, self.port)
        try:
            self.send_raw_provision(secret)
        except Exception:
            self.keys.delete(self.host, self.port)
            raise

    def send_raw_provision(self, secret: bytes) -> None:
        # `provision` carries the secret itself (already base64) instead of a wrapped payload.
        parts = ["am", "broadcast", "-n", COMPONENT, "-a", ACTION,
                 "--es", "cmd", "provision", "--es", "payload", b64u(secret)]
        out = self._shell(" ".join(shlex.quote(p) for p in parts), 20.0)
        check_result(parse_broadcast_result(out))

    def status(self) -> Optional[dict]:
        """Live status from the TV, or None when TV Guard cannot answer."""
        if not self.is_installed():
            return None
        try:
            res = self.send("status")
        except GuardError:
            return None
        if not res.startswith("ok:"):
            return None
        try:
            return json.loads(res[3:])
        except ValueError:
            return None

    def summary(self) -> dict:
        """Everything the UI needs for the TV Guard card, in one cheap call."""
        installed = self.is_installed()
        info = {
            "installed": installed,
            "enabled": False,
            "paired": self.keys.load(self.host, self.port) is not None,
            "state": "not_installed",
            "status": None,
        }
        if not installed:
            return info
        info["enabled"] = self.accessibility_enabled()
        st = self.status() if info["paired"] else None
        info["status"] = st
        info["version"] = (st or {}).get("version")
        info["update_available"] = bool(st) and st.get("version") != EXPECTED_VERSION
        if not info["paired"]:
            info["state"] = "unpaired"
        elif st is None:
            info["state"] = "unreachable"
        elif not info["enabled"] or not st.get("running"):
            info["state"] = "service_off"
        elif not st.get("pin_set") or not st.get("policy_loaded"):
            info["state"] = "incomplete"
        elif st.get("decision") == "LOCK":
            # The TV decided to lock; only call it locked when the cover is really on screen.
            if not st.get("overlay_showing"):
                info["state"] = "lock_failed"
            elif st.get("manual_lock_until_ms", 0) > st.get("now_ms", 0):
                info["state"] = "locked_manual"
            else:
                info["state"] = "locked"
        else:
            info["state"] = "protected"
        return info

    def grant_background_access(self) -> str:
        """Allow TV Guard to be started in the background. Best effort: returns a one-line report
        of what each op returned, because the accepted op names vary by TV vendor."""
        notes = []
        for op in AUTO_START_OPS + BACKGROUND_OPS:
            out = self._shell(f"cmd appops set {PACKAGE} {op} allow 2>&1").strip()
            failed = bool(re.search(r"error|unknown|exception|invalid|denied", out, re.I))
            notes.append(f"{op}: {out[:60] if failed else 'ok'}")
        try:
            self._shell(f"dumpsys deviceidle whitelist +{PACKAGE} 2>&1")
        except Exception:
            pass  # not available on every build; the appops grants above are what matters
        return "; ".join(notes)

    def enable_accessibility(self, rebind: bool = True) -> None:
        cur = self._shell("settings get secure enabled_accessibility_services").strip()
        items = [] if cur in ("", "null") else [c for c in cur.split(":") if c]
        if rebind and SERVICE in items:
            # A bind the TV refused earlier is not retried while the setting is unchanged, so drop
            # our entry first and add it back to make the system try again.
            rest = [c for c in items if c != SERVICE]
            self._shell(f"settings put secure enabled_accessibility_services {shlex.quote(':'.join(rest))}")
            time.sleep(REBIND_PAUSE_S)
        if SERVICE not in items:
            items.append(SERVICE)
        self._shell(f"settings put secure enabled_accessibility_services {shlex.quote(':'.join(items))}")
        self._shell("settings put secure accessibility_enabled 1")

    def uninstall(self) -> None:
        out = self._shell(f"pm uninstall {PACKAGE}")
        self.keys.delete(self.host, self.port)
        if "Success" not in out and "Unknown package" not in out:
            raise GuardError(f"Gỡ TV Guard thất bại: {out.strip()[:200]}")

    # -- the one-click flow ---------------------------------------------------
    def setup(self, installer, pin: str, policy: dict, on_step: StepFn) -> dict:
        """Install, enable, pair, set PIN and schedule, then verify. `installer` is an
        ApkInstaller bound to the same device."""
        # Validate everything before the first command reaches the TV.
        pin = validate_pin(pin) if pin else ""
        pol = normalize_policy(policy)
        if not (policy or {}).get("tz"):
            pol["tz"] = self.tv_timezone()

        installed = self.is_installed()
        if installed and not self._pairing_usable(on_step):
            on_step("reset", "Gỡ bản cũ để ghép cặp lại (khoá điều khiển cũ không còn dùng được)")
            self.uninstall()
            installed = False
        if not installed:
            # A fresh install has no secret on the TV, so any key kept here is stale.
            self.keys.delete(self.host, self.port)

        apk = locate_apk(on_step)
        on_step("install", "Đang cài TV Guard lên TV...")
        res = installer.install(apk, progress_cb=lambda m: on_step("install", m),
                                reinstall=True, allow_downgrade=True, grant_permissions=False)
        if res.get("ok") is False:
            raise GuardError(res.get("output") or "pm install không thành công")

        on_step("enable", "Đang cấp quyền tự khởi động cho TV Guard (TV TCL chặn dịch vụ nền nếu thiếu)...")
        on_step("enable", "Quyền nền: " + self.grant_background_access())
        on_step("enable", "Đang bật dịch vụ trợ năng của TV Guard...")
        self.enable_accessibility()
        time.sleep(1.5)

        if self.keys.load(self.host, self.port) is None:
            on_step("pair", "Đang ghép cặp app với TV Guard...")
            self.provision()
        self.send("ping")

        if pin:
            on_step("pin", "Đang đặt mã PIN (TV chỉ lưu bản băm)...")
            self.send("set_pin", hash_pin(pin))
        on_step("policy", "Đang lưu lịch khoá lên TV...")
        self.send("set_policy", json.dumps(pol))

        on_step("verify", "Đang kiểm tra lại trên TV...")
        info = self.wait_running(on_step)
        st = info.get("status") or {}
        if not st.get("running"):
            on_step("diag", self.diagnose())
            if info.get("status") is None:
                raise GuardError(
                    "Đã cài nhưng không đọc được trạng thái từ TV Guard. Xem «Chi tiết kỹ thuật» "
                    "bên dưới để biết nguyên nhân, rồi gửi nội dung đó khi cần hỗ trợ."
                )
            raise GuardError(
                "Đã cài nhưng dịch vụ trợ năng chưa chạy sau "
                f"{int(SERVICE_WAIT_S)} giây. Một số TV chặn việc bật tự động: vào Cài đặt › Trợ năng › "
                "TV Guard và bật thủ công, rồi bấm «Làm mới». Chi tiết kỹ thuật bên dưới cho biết lý do."
            )
        if not st.get("pin_set"):
            raise GuardError("Chưa có PIN trên TV. Nhập PIN rồi lưu lại.")
        on_step("done", "TV Guard đang bảo vệ TV này")
        return info

    def wait_running(self, on_step: StepFn, timeout: float = SERVICE_WAIT_S,
                     interval: float = SERVICE_POLL_S) -> dict:
        """Poll until the accessibility service reports running; the TV can take several seconds
        to bind it after the setting is written."""
        deadline = time.monotonic() + timeout
        while True:
            info = self.summary()
            if (info.get("status") or {}).get("running"):
                return info
            if time.monotonic() >= deadline:
                return info
            on_step("verify", "Đang chờ dịch vụ trợ năng khởi động...")
            time.sleep(interval)

    def diagnose(self) -> str:
        """Plain-text snapshot for support: what the TV thinks about our package and service."""
        probes = [
            ("android", "getprop ro.product.model; getprop ro.build.version.release; getprop ro.build.version.sdk"),
            ("package", f"pm path {PACKAGE}; dumpsys package {PACKAGE} | grep -E 'versionName|versionCode|firstInstallTime|enabled=|stopped='"),
            ("settings", "settings get secure enabled_accessibility_services; settings get secure accessibility_enabled"),
            ("accessibility", "dumpsys accessibility | grep -i -E -A3 'smarttvmanager|Bound services|Enabled services|Binding services|Crashed services'"),
            # Does the system consider our service installed? A service missing here is never bound.
            ("appops", f"cmd appops get {PACKAGE} 2>&1 | head -30"),
            ("a11y installed", "dumpsys accessibility | grep -i -n -E 'installed|smarttvmanager|gathin' | head -20"),
            ("a11y registered", "cmd package query-services --brief -a android.accessibilityservice.AccessibilityService 2>&1 | head -30"),
            ("logcat", "logcat -d -t 2000 2>/dev/null | grep -i -E 'smarttvmanager|AndroidRuntime|FATAL|AccessibilityManagerService|AccessibilityServiceInfo' | tail -40"),
        ]
        parts = []
        for name, cmd in probes:
            try:
                out = self._shell(cmd, 45.0).strip() or "(empty)"
            except Exception as exc:  # keep going: a partial report is still useful
                out = f"(failed: {exc})"
            parts.append(f"== {name} ==\n{out}")
        try:
            parts.append("== status command ==\n" + self.send("status")[:600])
        except Exception as exc:
            parts.append(f"== status command ==\n(failed: {exc})")
        return "\n\n".join(parts)

    def _pairing_usable(self, on_step: StepFn) -> bool:
        if self.keys.load(self.host, self.port) is None:
            return False
        try:
            self.send("ping")
            return True
        except GuardError as e:
            on_step("pair_check", str(e))
            return False
