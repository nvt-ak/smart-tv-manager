"""Detect TV launchers and compatibility."""
import re
from typing import Any, Dict, Optional

from adb_shell.adb_device import AdbDeviceTcp


class LauncherDetector:
    GATHIN_PKG = "com.gathin.tvhome"

    def __init__(self, device: AdbDeviceTcp):
        self.device = device

    def _shell(self, cmd: str) -> str:
        try:
            return self.device.shell(cmd)
        except Exception as e:
            raise Exception(f"Shell error: {e}")

    def is_installed(self, pkg: str) -> bool:
        try:
            out = self._shell(f"pm list packages | grep {pkg}")
            return pkg in out
        except Exception:
            return False

    def get_default_home(self) -> Optional[str]:
        try:
            out = self._shell("cmd package resolve-activity -a android.intent.action.MAIN -c android.intent.category.HOME 2>&1 | grep -m1 'name='")
            m = re.search(r"name=([^\s/]+/[^\s}]+)", out)
            if m:
                comp = m.group(1)
                if "/" in comp:
                    return comp.split("/")[0]
            out2 = self._shell("dumpsys package resolver 2>&1 | grep -A 15 'preferredActivities' | head -20")
            m2 = re.search(r"([a-zA-Z0-9_.]+)/[a-zA-Z0-9_.]+", out2)
            if m2:
                return m2.group(1)
        except Exception:
            pass
        return None

    def detect_gathin(self) -> Dict[str, Any]:
        installed = self.is_installed(self.GATHIN_PKG)
        home = self.get_default_home()
        is_default = home == self.GATHIN_PKG
        return {
            "pkg": self.GATHIN_PKG,
            "installed": installed,
            "is_default_home": is_default,
            "current_home": home,
            "compatible": installed,
        }

    def discover_config(self) -> Dict[str, Any]:
        """Try to find gathin config files."""
        paths = []
        candidates = [
            "/data/data/com.gathin.tvhome",
            "/data/data/com.gathin.tvhome/shared_prefs",
            "/data/data/com.gathin.tvhome/files",
            "/data/data/com.gathin.tvhome/databases",
            "/sdcard/Android/data/com.gathin.tvhome",
            "/sdcard/Android/data/com.gathin.tvhome/files",
        ]
        for p in candidates:
            try:
                out = self._shell(f"ls -la {p} 2>&1 | head -15")
                if "No such file" not in out and "Permission denied" not in out or "drwx" in out:
                    paths.append({"path": p, "listing": out})
            except Exception:
                pass
        return {"candidates": paths}
