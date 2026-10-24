"""Package management for Android TV."""
import re
from typing import Any, Dict, List

from adb_shell.adb_device import AdbDeviceTcp

import adb_client
from . import adb_commands


def _parse_package_lines(out: str) -> List[str]:
    packages = []
    for line in (out or "").splitlines():
        line = line.strip()
        if line.startswith("package:"):
            packages.append(line.replace("package:", "").strip())
    return packages


class PackageManager:
    def __init__(self, device: AdbDeviceTcp):
        self.device = device

    def _shell(self, cmd: str, timeout: float | None = None) -> str:
        timeout = float(timeout if timeout is not None else adb_client.CONNECT_TIMEOUT)
        last_err: Exception | None = None
        for attempt in range(2):
            try:
                adb_client.ensure_connected(self.device, timeout=timeout)
                return self.device.shell(
                    cmd,
                    transport_timeout_s=timeout,
                    read_timeout_s=timeout,
                    timeout_s=timeout,
                )
            except Exception as e:
                last_err = e
                if attempt == 0:
                    try:
                        adb_client.reconnect(self.device, timeout=min(timeout, 15.0))
                    except Exception:
                        pass
        raise Exception(f"Shell error: {last_err}")

    def list_packages(self, flag: str = "", timeout: float | None = None) -> List[str]:
        t = timeout if timeout is not None else adb_client.SHELL_HEAVY_TIMEOUT
        out = self._shell(adb_commands.list_packages_cmd(flag), timeout=t)
        return _parse_package_lines(out)

    def get_all_packages(self) -> Dict[str, List[str]]:
        """One round-trip for all three pm list variants (saves Wi‑Fi latency)."""
        script = (
            "pm list packages; echo '---SPLIT---'; "
            "pm list packages -3; echo '---SPLIT---'; "
            "pm list packages -d"
        )
        out = self._shell(script, timeout=adb_client.SHELL_HEAVY_TIMEOUT)
        parts = out.split("---SPLIT---")
        all_raw = _parse_package_lines(parts[0] if parts else "")
        user = _parse_package_lines(parts[1] if len(parts) > 1 else "")
        disabled = _parse_package_lines(parts[2] if len(parts) > 2 else "")
        user_set = set(user)
        all_pkgs = sorted(set(all_raw) | user_set | set(disabled))
        system = sorted(set(all_pkgs) - user_set)
        return {
            "user": sorted(user),
            "system": system,
            "disabled": sorted(disabled),
            "all": all_pkgs,
        }

    def get_package_info(self, package: str) -> Dict[str, Any]:
        info = {"package": package}
        try:
            out = self._shell(
                f"dumpsys package {package} 2>&1 | grep -E 'versionName|versionCode' | head -4",
                timeout=adb_client.SHELL_HEAVY_TIMEOUT,
            )
            for line in out.splitlines():
                if "versionName" in line:
                    m = re.search(r"versionName=([^\s]+)", line)
                    if m:
                        info["version"] = m.group(1)
                if "versionCode" in line:
                    m = re.search(r"versionCode=(\d+)", line)
                    if m:
                        info["version_code"] = m.group(1)
            out2 = self._shell(
                f"pm list packages -e 2>&1 | grep -w {package}",
                timeout=adb_client.SHELL_HEAVY_TIMEOUT,
            )
            info["enabled"] = package in out2
        except Exception:
            pass
        return info

    def get_packages_info(self, packages: List[str], limit: int = 80) -> Dict[str, Dict[str, Any]]:
        """Basic info for a small subset — each package is 1–2 shell calls."""
        result = {}
        for pkg in packages[:limit]:
            try:
                result[pkg] = self.get_package_info(pkg)
            except Exception:
                result[pkg] = {"package": pkg}
        return result

    def get_launcher_package_set(self) -> set[str]:
        """Packages with MAIN+LAUNCHER or LEANBACK_LAUNCHER activities (one round-trip per query)."""
        found: set[str] = set()
        for category in (
            "android.intent.category.LAUNCHER",
            "android.intent.category.LEANBACK_LAUNCHER",
        ):
            try:
                out = self._shell(
                    "cmd package query-intent-activities "
                    f"-a android.intent.action.MAIN -c {category} 2>&1",
                    timeout=adb_client.SHELL_HEAVY_TIMEOUT,
                )
                for line in (out or "").splitlines():
                    m = re.search(r"([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)/", line, re.I)
                    if m:
                        found.add(m.group(1))
            except Exception:
                continue
        return found

    def get_current_home(self) -> str:
        try:
            out = self._shell(
                "cmd package resolve-activity -a android.intent.action.MAIN "
                "-c android.intent.category.HOME 2>&1 | grep -m1 'name='",
                timeout=adb_client.SHELL_HEAVY_TIMEOUT,
            )
            m = re.search(r"name=([^\s/]+/[^\s}]+)", out)
            if m:
                comp = m.group(1)
                if "/" in comp:
                    return comp.split("/")[0]
            out2 = self._shell(
                "dumpsys activity activities | grep -A2 mResumedActivity | head -5",
                timeout=adb_client.SHELL_HEAVY_TIMEOUT,
            )
            m2 = re.search(r"([a-zA-Z0-9_.]+)/", out2)
            if m2:
                return m2.group(1)
        except Exception:
            pass
        return None

    def open_app(self, package: str) -> bool:
        try:
            self._shell(adb_commands.open_app_cmd(package))
            return True
        except Exception as e:
            raise Exception(str(e))

    def force_stop(self, package: str) -> bool:
        try:
            self._shell(adb_commands.force_stop_cmd(package))
            return True
        except Exception as e:
            raise Exception(str(e))

    def open_app_info(self, package: str) -> bool:
        try:
            self._shell(adb_commands.app_info_cmd(package))
            return True
        except Exception as e:
            raise Exception(str(e))

    def enable(self, package: str) -> bool:
        try:
            self._shell(adb_commands.enable_cmd(package))
            return True
        except Exception as e:
            raise Exception(str(e))

    def disable_user(self, package: str) -> bool:
        try:
            self._shell(adb_commands.disable_user_cmd(package))
            return True
        except Exception as e:
            raise Exception(str(e))
