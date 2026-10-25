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


def _friendly_pm_shell_error(err: Exception, package: str, *, enabling: bool) -> str:
    text = str(err)
    if "SecurityException" in text and "Shell cannot change component state" in text:
        action = "bật" if enabling else "tắt"
        return (
            f"TV không cho phép {action} «{package}» qua ADB "
            "(ứng dụng hệ thống / OEM khóa hoặc chỉ quản lý trên TV)."
        )
    if "SecurityException" in text:
        return f"TV từ chối thao tác package «{package}» (SecurityException)."
    return text


def _pm_state_message_ok(out: str, *, enabling: bool) -> bool:
    text = (out or "").strip().lower()
    if not text:
        return False
    if "error:" in text or "exception" in text:
        return False
    if "new state:" in text:
        return True
    if enabling and "already enabled" in text:
        return True
    if not enabling and ("already disabled" in text or "disabled-user" in text):
        return True
    return False


def _grep_package_in_pm_list(out: str, package: str) -> bool:
    needle = f"package:{package}"
    for line in (out or "").splitlines():
        if line.strip() == needle:
            return True
    return False


class PackageManager:
    def __init__(self, device: AdbDeviceTcp):
        self.device = device

    def _shell(self, cmd: str, timeout: float | None = None) -> str:
        timeout = float(timeout if timeout is not None else adb_client.CONNECT_TIMEOUT)
        last_err: Exception | None = None
        for attempt in range(2):
            try:
                adb_client.ensure_connected(self.device, timeout=timeout)
                out = self.device.shell(
                    cmd,
                    transport_timeout_s=timeout,
                    read_timeout_s=timeout,
                    timeout_s=timeout,
                )
                adb_client.mark_ok(self.device)
                return out
            except Exception as e:
                last_err = e
                adb_client.mark_bad(self.device)
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
            "pm list packages -e --user 0; echo '---SPLIT---'; "
            "pm list packages -d --user 0"
        )
        out = self._shell(script, timeout=adb_client.SHELL_HEAVY_TIMEOUT)
        parts = out.split("---SPLIT---")
        all_raw = _parse_package_lines(parts[0] if parts else "")
        user = _parse_package_lines(parts[1] if len(parts) > 1 else "")
        enabled = _parse_package_lines(parts[2] if len(parts) > 2 else "")
        disabled_flag = _parse_package_lines(parts[3] if len(parts) > 3 else "")
        user_set = set(user)
        enabled_set = set(enabled)
        all_pkgs = sorted(set(all_raw) | user_set | enabled_set | set(disabled_flag))
        disabled_set = (set(all_pkgs) - enabled_set) | set(disabled_flag)
        system = sorted(set(all_pkgs) - user_set)
        return {
            "user": sorted(user),
            "system": system,
            "disabled": sorted(disabled_set),
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
            resolve_out = self._shell(
                adb_commands.HOME_RESOLVE_CMD, timeout=adb_client.SHELL_HEAVY_TIMEOUT
            )
            role_out = ""
            try:
                role_out = self._shell(adb_commands.HOME_ROLE_CMD)
            except Exception:
                pass
            return adb_commands.parse_home_package(resolve_out, role_out)
        except Exception:
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

    def uninstall(self, package: str) -> bool:
        """Gỡ hẳn app người dùng (pm uninstall). App hệ thống thì dùng vô hiệu hóa."""
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+", package or ""):
            raise Exception("Tên package không hợp lệ")
        out = (self._shell(f"pm uninstall {package} 2>&1", timeout=adb_client.SHELL_HEAVY_TIMEOUT) or "").strip()
        if "Success" in out:
            return True
        if "DELETE_FAILED_DEVICE_POLICY_MANAGER" in out or "DELETE_FAILED_INTERNAL_ERROR" in out:
            raise Exception(f"Không gỡ được {package}: app hệ thống hoặc bị chính sách chặn ({out})")
        raise Exception(out or f"pm uninstall không thành công: {package}")

    def is_package_enabled(self, package: str) -> bool:
        """One package only — avoid full `pm list -e` over Wi‑Fi."""
        try:
            out = self._shell(
                f"pm list packages -e --user 0 {package} 2>&1",
                timeout=adb_client.SHELL_DEFAULT_TIMEOUT,
            )
            return _grep_package_in_pm_list(out, package)
        except Exception:
            return True

    def enable(self, package: str) -> bool:
        try:
            out = self._shell(adb_commands.enable_cmd(package))
            if _pm_state_message_ok(out, enabling=True):
                return True
            if self.is_package_enabled(package):
                return True
            raise Exception(
                (out or f"pm enable không đổi trạng thái {package}").strip()
            )
        except Exception as e:
            raise Exception(_friendly_pm_shell_error(e, package, enabling=True))

    def disable_user(self, package: str) -> bool:
        try:
            out = self._shell(adb_commands.disable_user_cmd(package))
            if _pm_state_message_ok(out, enabling=False):
                return True
            if not self.is_package_enabled(package):
                return True
            raise Exception(
                (out or f"pm disable-user không đổi trạng thái {package}").strip()
            )
        except Exception as e:
            raise Exception(_friendly_pm_shell_error(e, package, enabling=False))
