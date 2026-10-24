"""Package management for Android TV."""
import re
from typing import Any, Dict, List

from adb_shell.adb_device import AdbDeviceTcp

from . import adb_commands


class PackageManager:
    def __init__(self, device: AdbDeviceTcp):
        self.device = device

    def _shell(self, cmd: str) -> str:
        try:
            return self.device.shell(cmd)
        except Exception as e:
            raise Exception(f"Shell error: {e}")

    def list_packages(self, flag: str = "") -> List[str]:
        out = self._shell(adb_commands.list_packages_cmd(flag))
        packages = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("package:"):
                packages.append(line.replace("package:", "").strip())
        return packages

    def get_all_packages(self) -> Dict[str, List[str]]:
        user = self.list_packages("-3")
        system = self.list_packages("-s")
        disabled = self.list_packages("-d")
        # Merge all
        all_pkgs = sorted(set(user) | set(system) | set(disabled))
        return {
            "user": sorted(user),
            "system": sorted(system),
            "disabled": sorted(disabled),
            "all": all_pkgs,
        }

    def get_package_info(self, package: str) -> Dict[str, Any]:
        info = {"package": package}
        try:
            out = self._shell(f"dumpsys package {package} 2>&1 | grep -E 'versionName|versionCode' | head -4")
            for line in out.splitlines():
                if "versionName" in line:
                    m = re.search(r"versionName=([^\s]+)", line)
                    if m:
                        info["version"] = m.group(1)
                if "versionCode" in line:
                    m = re.search(r"versionCode=(\d+)", line)
                    if m:
                        info["version_code"] = m.group(1)
            out2 = self._shell(f"pm list packages -e 2>&1 | grep -w {package}")
            info["enabled"] = package in out2
        except Exception:
            pass
        return info

    def get_packages_info(self, packages: List[str], limit: int = 80) -> Dict[str, Dict[str, Any]]:
        """Get basic info for a subset of packages to avoid blocking UI."""
        result = {}
        for pkg in packages[:limit]:
            try:
                result[pkg] = self.get_package_info(pkg)
            except Exception:
                result[pkg] = {"package": pkg}
        return result

    def get_current_home(self) -> str:
        try:
            # Try modern approach
            out = self._shell("cmd package resolve-activity -a android.intent.action.MAIN -c android.intent.category.HOME 2>&1 | grep -m1 'name='")
            m = re.search(r"name=([^\s/]+/[^\s}]+)", out)
            if m:
                comp = m.group(1)
                if "/" in comp:
                    return comp.split("/")[0]
            # Fallback
            out2 = self._shell("dumpsys activity activities | grep -A2 mResumedActivity | head -5")
            m2 = re.search(r"([a-zA-Z0-9_.]+)/", out2)
            if m2:
                pkg = m2.group(1)
                # Check if it's a launcher
                return pkg
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
