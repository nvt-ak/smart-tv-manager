"""Detect TV launchers and compatibility."""
import re
from typing import Any, Dict, Optional

from adb_shell.adb_device import AdbDeviceTcp

import adb_client
from . import adb_commands


class LauncherDetector:
    SMTV_PKG = "com.smtv_manager.home"
    GATHIN_PKG = SMTV_PKG  # legacy name kept for callers; upstream CleanYourTV is no longer supported
    PACKAGES = (SMTV_PKG,)

    def __init__(self, device: AdbDeviceTcp):
        self.device = device

    def _shell(self, cmd: str) -> str:
        # Dùng run_shell: timeout theo lệnh (25-45s) + reconnect/retry như tab Packages.
        # Trước đây dùng device.shell() timeout mặc định ~8s nên lỗi mạng bị nuốt thành "chưa cài".
        try:
            return adb_client.run_shell(self.device, cmd)
        except Exception as e:
            raise Exception(f"Shell error: {e}")

    def is_installed(self, pkg: str) -> bool:
        """True/False khi TV trả lời; RAISE nếu không hỏi được (không đoán là 'chưa cài')."""
        out = self._shell(f"pm list packages {pkg} 2>&1")
        return any(line.strip() == f"package:{pkg}" for line in out.splitlines())

    def installed_launcher(self) -> Optional[str]:
        """The launcher to drive: the default Home if it is one of ours, else the first installed.

        None when none is installed; RAISES when the TV cannot be asked.
        """
        installed = [p for p in self.PACKAGES if self.is_installed(p)]
        if not installed:
            return None
        try:
            home = self.get_default_home()
        except Exception:
            home = None
        return home if home in installed else installed[0]

    def get_default_home(self) -> Optional[str]:
        resolve_out = self._shell(adb_commands.HOME_RESOLVE_CMD)
        role_out = ""
        try:
            role_out = self._shell(adb_commands.HOME_ROLE_CMD)
        except Exception:
            pass  # Android < 10 has no role service
        return adb_commands.parse_home_package(resolve_out, role_out)

    def detect_gathin(self) -> Dict[str, Any]:
        error = None
        try:
            pkg = self.installed_launcher()
            installed: Optional[bool] = pkg is not None
            pkg = pkg or self.GATHIN_PKG
        except Exception as e:
            pkg, installed, error = self.GATHIN_PKG, None, str(e)  # None = không xác định
        home = None
        if installed is not None:
            try:
                home = self.get_default_home()
            except Exception as e:
                error = error or str(e)
        is_default = home == pkg
        stock_disabled = None
        if installed is not None:
            try:
                from .theme_manager import STOCK_HOME_PKGS, STOCK_GREP
                out = self._shell(f"pm list packages -d 2>&1 | grep -E '{STOCK_GREP}'")
                off = {
                    ln.strip()[len("package:"):]
                    for ln in (out or "").splitlines()
                    if ln.strip().startswith("package:")
                } & set(STOCK_HOME_PKGS)
                stock_disabled = bool(off) and (home or "") not in STOCK_HOME_PKGS
            except Exception:
                stock_disabled = None
        # Gathin đang là launcher mặc định thì chắc chắn đã cài.
        if installed is None and is_default:
            installed, error = True, None
        return {
            "pkg": pkg,
            "installed": installed,
            "is_default_home": is_default,
            "current_home": home,
            "compatible": bool(installed),
            "error": error,
            "stock_disabled": stock_disabled,
        }

    def discover_config(self) -> Dict[str, Any]:
        """Try to find gathin config files."""
        paths = []
        candidates = [
            f"/data/data/{self.SMTV_PKG}",
            f"/data/data/{self.SMTV_PKG}/shared_prefs",
            f"/data/data/{self.SMTV_PKG}/files",
            f"/data/data/{self.SMTV_PKG}/databases",
            f"/sdcard/Android/data/{self.SMTV_PKG}",
            f"/sdcard/Android/data/{self.SMTV_PKG}/files",
        ]
        # Một lần gọi shell thay vì 6 lần (mỗi lần = 1 round-trip qua Wi-Fi).
        script = "; ".join(f"echo '##{p}'; ls -la {p} 2>&1 | head -15" for p in candidates)
        try:
            out = self._shell(script)
        except Exception:
            return {"candidates": paths}
        for chunk in out.split("##")[1:]:
            p, _, listing = chunk.partition("\n")
            p = p.strip()
            if "No such file" not in listing and "Permission denied" not in listing or "drwx" in listing:
                paths.append({"path": p, "listing": listing})
        return {"candidates": paths}
