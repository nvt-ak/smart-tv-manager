"""Safety layer for package operations."""
import json
import os
from typing import List, Set

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PROTECTED_PATH = os.path.join(DATA_DIR, "protected_packages.json")


class SafetyChecker:
    def __init__(self):
        self.protected: Set[str] = set()
        self.sensitive: Set[str] = set()
        self._load()

    def _load(self):
        try:
            with open(PROTECTED_PATH, encoding="utf-8") as f:
                data = json.load(f)
            self.protected = set(data.get("critical", []))
            self.sensitive = set(data.get("sensitive", []))
        except Exception:
            # Fallback minimal critical list
            self.protected = {
                "android",
                "com.android.systemui",
                "com.android.settings",
                "com.android.packageinstaller",
                "com.android.permissioncontroller",
                "com.android.keyguard",
            }
            self.sensitive = set()

    def is_protected(self, package: str) -> bool:
        if not package:
            return True
        if package in self.protected:
            return True
        # Protect any package starting with android.* that is critical
        if package == "android":
            return True
        return False

    def is_sensitive(self, package: str) -> bool:
        return package in self.sensitive

    def can_disable(self, package: str, current_home: str = None, is_only_home: bool = False) -> tuple:
        """Return (allowed, reason)."""
        if self.is_protected(package):
            return False, "Package quan trọng hệ thống - không được vô hiệu hóa"
        if current_home and package == current_home:
            if is_only_home:
                return False, "Đây là Home/Launcher đang hoạt động và là duy nhất - không được vô hiệu hóa"
            return False, "Đây là Home/Launcher đang hoạt động - không được vô hiệu hóa"
        if self.is_sensitive(package):
            return False, "Package nhạy cảm - cần thận trọng, tạm thời chặn"
        return True, None


safety = SafetyChecker()
