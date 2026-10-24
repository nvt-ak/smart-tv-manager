"""Common ADB shell commands."""
from typing import Any, Dict


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
    return f"pm enable {package}"


def disable_user_cmd(package: str) -> str:
    return f"pm disable-user {package}"


def get_default_home_cmd() -> str:
    # Try to get current default launcher/home
    return "cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME 2>/dev/null || dumpsys package resolver 2>/dev/null | head -80"
