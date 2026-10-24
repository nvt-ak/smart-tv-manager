"""APK install flow with cleanup."""
import os
import time
from typing import Any, Callable, Dict

from adb_shell.adb_device import AdbDeviceTcp

import adb_client


class ApkInstaller:
    def __init__(self, device: AdbDeviceTcp):
        self.device = device

    def _shell(self, cmd: str, timeout: float = 60.0) -> str:
        try:
            return self.device.shell(
                cmd,
                transport_timeout_s=timeout,
                read_timeout_s=timeout,
                timeout_s=timeout,
            )
        except Exception as e:
            raise Exception(f"Shell error: {e}")

    def _push_apk(self, local_apk: str, remote_path: str, progress_cb: Callable[[str], None] | None) -> None:
        try:
            size = os.path.getsize(local_apk)
        except OSError:
            size = 0
        timeout = adb_client.push_timeout_int(size)
        size_kb = max(1, size // 1024)
        last: Exception | None = None
        for attempt in range(3):
            try:
                if attempt > 0:
                    if progress_cb:
                        progress_cb(f"Thử đẩy lại lần {attempt + 1}/3 (timeout {int(timeout)}s)...")
                    time.sleep(1.0)
                    adb_client.reconnect(self.device, timeout=15.0)
                else:
                    adb_client.ensure_connected(self.device, timeout=15.0)
                if progress_cb:
                    progress_cb(f"Đang đẩy APK ({size_kb} KB, tối đa ~{int(timeout)}s)...")
                self.device.push(
                    local_apk,
                    remote_path,
                    transport_timeout_s=timeout,
                    read_timeout_s=timeout,
                )
                return
            except Exception as e:
                last = e
                msg = str(e).lower()
                if attempt >= 2 or "timed out" not in msg:
                    break
        hint = (
            "ADB qua Wi‑Fi không kịp đẩy file — TV sleep, Wi‑Fi yếu hoặc phiên ADB treo. "
            "Thử đánh thức TV, cùng LAN, tắt/bật Gỡ lỗi USB rồi kết nối lại."
        )
        detail = str(last) if last else "unknown"
        raise Exception(f"Đẩy APK lên TV thất bại: {detail}. {hint}")

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
            self._push_apk(local_apk, remote_path, progress_cb)
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
            install_timeout = max(
                180.0,
                adb_client.transfer_timeout_s(os.path.getsize(local_apk)) * 0.75,
            )
            out = self._shell(f"pm install {flag_str} {remote_path} 2>&1", timeout=install_timeout)
            result = {"ok": "Success" in out or "success" in out.lower(), "output": out.strip()}
            if progress_cb:
                progress_cb("Đang dọn dẹp file tạm...")
            try:
                self._shell(f"rm -f {remote_path}", timeout=30.0)
            except Exception:
                pass
            if not result["ok"]:
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
                self._shell(f"rm -f {remote_path}", timeout=30.0)
            except Exception:
                pass
            raise e
