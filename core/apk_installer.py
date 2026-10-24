"""APK install flow with cleanup."""
import os
import posixpath
import time
from typing import Any, Callable, Dict

from adb_shell.adb_device import AdbDeviceTcp


class ApkInstaller:
    def __init__(self, device: AdbDeviceTcp):
        self.device = device

    def _shell(self, cmd: str) -> str:
        try:
            return self.device.shell(cmd)
        except Exception as e:
            raise Exception(f"Shell error: {e}")

    def install(
        self,
        local_apk: str,
        remote_path: str = None,
        progress_cb: Callable[[str], None] = None,
        reinstall: bool = True,
        allow_downgrade: bool = False,
        grant_permissions: bool = False,
    ) -> Dict[str, Any]:
        if not os.path.exists(local_apk):
            raise Exception("File APK không tồn tại")
        filename = os.path.basename(local_apk)
        if not remote_path:
            remote_path = f"/sdcard/Download/{filename}"
        try:
            if progress_cb:
                progress_cb("Đang đẩy APK lên TV...")
            self.device.push(local_apk, remote_path)
            if progress_cb:
                progress_cb("Đang cài đặt...")
            flags = ["-t"]
            if reinstall:
                flags.append("-r")
            if allow_downgrade:
                flags.append("-d")
            if grant_permissions:
                flags.append("-g")
            flag_str = " ".join(flags)
            out = self._shell(f"pm install {flag_str} {remote_path} 2>&1")
            result = {"ok": "Success" in out or "success" in out.lower(), "output": out.strip()}
            if progress_cb:
                progress_cb("Đang dọn dẹp file tạm...")
            try:
                self._shell(f"rm -f {remote_path}")
            except Exception:
                pass
            if not result["ok"]:
                # Try to map common errors
                if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in out:
                    raise Exception("Cài đặt thất bại: Chữ ký khác với phiên bản đã cài. Gỡ app cũ hoặc dùng APK cùng chữ ký.")
                if "INSTALL_FAILED_VERSION_DOWNGRADE" in out:
                    raise Exception("Cài đặt thất bại: APK cũ hơn phiên bản đang cài. Hãy dùng phiên bản mới hơn.")
                if "INSTALL_FAILED_PERMISSION_MODEL_DOWNGRADE" in out:
                    raise Exception("Cài đặt thất bại: Không thể hạ quyền.")
                if "INSTALL_FAILED_INVALID_APK" in out:
                    raise Exception("Cài đặt thất bại: File APK không hợp lệ.")
                raise Exception(f"Cài đặt thất bại: {out.strip()}")
            return result
        except Exception as e:
            try:
                self._shell(f"rm -f {remote_path}")
            except Exception:
                pass
            raise e
