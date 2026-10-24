"""Common ADB shell commands."""
import re
from typing import Any, Dict, Optional


KEYCODES = {
    "back": 4,
    "home": 3,
    "menu": 82,
    "settings": 176,
    "input": 178,
    "power": 26,
    "volume_up": 24,
    "volume_down": 25,
    "mute": 164,
    "play": 126,
    "pause": 127,
    "play_pause": 85,
    "dpad_up": 19,
    "dpad_down": 20,
    "dpad_left": 21,
    "dpad_right": 22,
    "dpad_center": 23,
}


def getprop_cmd(prop: str) -> str:
    return f"getprop {prop}"


def list_packages_cmd(flags: str = "") -> str:
    if flags:
        return f"pm list packages {flags}"
    return "pm list packages"


def open_app_cmd(package: str) -> str:
    return f"monkey -p {package} -c android.intent.category.LAUNCHER 1"


def force_stop_cmd(package: str) -> str:
    return f"am force-stop {package}"


def app_info_cmd(package: str) -> str:
    return f"am start -a android.settings.APPLICATION_DETAILS_SETTINGS -d package:{package}"


def enable_cmd(package: str) -> str:
    return f"pm enable --user 0 {package}"


def disable_user_cmd(package: str) -> str:
    return f"pm disable-user --user 0 {package}"


def get_default_home_cmd() -> str:
    # Try to get current default launcher/home
    return "cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME 2>/dev/null || dumpsys package resolver 2>/dev/null | head -80"


# `--brief` prints "pkg/.Activity" on the last line. The old `grep name=` approach saw only the
# class name (no "pkg/") on modern Android, so the default Home was never detected.
HOME_RESOLVE_CMD = (
    "cmd package resolve-activity --brief -a android.intent.action.MAIN "
    "-c android.intent.category.HOME 2>&1 | tail -n 1"
)
# Android 10+: the default Home app is the holder of the HOME role.
# Android 10 has no `get-role-holders`; fall back to the role service dump.
HOME_ROLE_CMD = (
    "cmd role get-role-holders --user 0 android.app.role.HOME 2>&1 | grep -iv 'unknown\\|usage'; "
    "dumpsys role 2>&1 | grep -A6 'android.app.role.HOME' | head -10"
)

_PKG_RE = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+", re.IGNORECASE)


def parse_home_package(resolve_out: str = "", role_out: str = "") -> Optional[str]:
    """Package of the default Home, or None when none is chosen (chooser) / unknown."""
    lines = [ln.strip() for ln in (resolve_out or "").splitlines() if ln.strip()]
    if lines:
        m = re.match(r"^([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*)/", lines[-1], re.IGNORECASE)
        # "android/...ResolverActivity" = the chooser: no default Home has been picked.
        if m and m.group(1) != "android":
            return m.group(1)
    for ln in (role_out or "").splitlines():
        ln = ln.strip()
        low = ln.lower()
        if not ln or any(k in low for k in ("exception", "error", "unknown", "usage", "can't find", "no role")):
            continue
        for m in _PKG_RE.finditer(ln):
            tok = m.group(0)
            if tok.lower().startswith(("android.app.role", "android.permission", "android.os")):
                continue
            return tok
    return None
