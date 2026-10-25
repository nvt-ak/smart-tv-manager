"""Official `adb` (Android platform-tools) helper: Wireless debugging pairing.

adb-shell cannot do the TLS + pairing handshake that Android 11+ "Wireless
debugging" requires, so for that one step we drive Google's own `adb`. After
pairing we switch the TV to plain TCP (port 5555), which the rest of the app
(adb-shell) already handles.
"""
import io
import os
import re
import shutil
import ssl
import subprocess
import sys
import urllib.request
import zipfile
from typing import Callable, Optional

import paths
from app_brand import user_data_dir

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover
    _CTX = ssl.create_default_context()

_PLATFORM = {"win32": "windows", "darwin": "darwin"}.get(sys.platform, "linux")
_EXE = "adb.exe" if sys.platform == "win32" else "adb"
DOWNLOAD_URL = f"https://dl.google.com/android/repository/platform-tools-latest-{_PLATFORM}.zip"
_NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _managed_dir() -> str:
    return os.path.join(user_data_dir(), "platform-tools")


def find_adb() -> Optional[str]:
    """Bundled copy, then the copy we downloaded, then whatever is on PATH."""
    for base in (os.path.join(paths.app_root(), "platform-tools"), _managed_dir()):
        p = os.path.join(base, _EXE)
        if os.path.isfile(p):
            return p
    return shutil.which("adb")


def ensure_adb(on_step: Optional[Callable[[str], None]] = None) -> str:
    """Return a path to adb, downloading Google's platform-tools once if needed."""
    found = find_adb()
    if found:
        return found
    if on_step:
        on_step("Đang tải Android platform-tools (adb) từ Google, khoảng 7 MB...")
    try:
        req = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent": "SmartTVManager"})
        with urllib.request.urlopen(req, timeout=120, context=_CTX) as r:
            data = r.read()
        dest = _managed_dir()
        tmp = dest + ".tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(tmp)  # the zip's top-level folder is "platform-tools"
        inner = os.path.join(tmp, "platform-tools")
        shutil.rmtree(dest, ignore_errors=True)
        shutil.move(inner, dest)
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception as exc:
        raise Exception(
            f"Không tải được adb ({exc}). Hãy cài Android platform-tools và thêm vào PATH, "
            "hoặc đặt thư mục «platform-tools» cạnh ứng dụng."
        ) from exc
    p = os.path.join(_managed_dir(), _EXE)
    if not os.path.isfile(p):
        raise Exception("Đã tải platform-tools nhưng không thấy file adb bên trong.")
    if sys.platform != "win32":
        os.chmod(p, 0o755)
    return p


def _run(adb: str, args: list, timeout: float = 30.0) -> str:
    cp = subprocess.run(
        [adb, *args], capture_output=True, text=True, timeout=timeout,
        creationflags=_NOWIN, stdin=subprocess.DEVNULL,
    )
    return ((cp.stdout or "") + (cp.stderr or "")).strip()


def pair(adb: str, host: str, pair_port: int, code: str) -> str:
    out = _run(adb, ["pair", f"{host}:{int(pair_port)}", code], timeout=40)
    if "success" not in out.lower():
        raise Exception(
            f"Ghép cặp thất bại: {out or 'không có phản hồi'}. "
            "Kiểm tra IP, CỔNG GHÉP CẶP và mã 6 số trên màn hình «Ghép nối thiết bị bằng mã» của TV "
            "(mã chỉ có hiệu lực khi hộp thoại đó còn mở)."
        )
    return out


def find_pair_port(adb: str, host: str, attempts: int = 4) -> Optional[int]:
    """Discover the pairing port via mDNS; the TV only advertises it while the
    "Pair device with pairing code" dialog is open."""
    import time
    for _ in range(attempts):
        out = _run(adb, ["mdns", "services"], timeout=15)
        for m in re.finditer(r"_adb-tls-pairing\._tcp\.?\s+([\d.]+):(\d+)", out):
            if m.group(1) == host:
                return int(m.group(2))
        time.sleep(1.5)
    return None


def find_connect_port(adb: str, host: str) -> Optional[int]:
    """Discover the Wireless-debugging connect port via mDNS (after pairing)."""
    out = _run(adb, ["mdns", "services"], timeout=15)
    for m in re.finditer(r"_adb-tls-connect\._tcp\.?\s+([\d.]+):(\d+)", out):
        if m.group(1) == host:
            return int(m.group(2))
    return None


def switch_to_tcpip(adb: str, host: str, connect_port: int, tcp_port: int = 5555) -> str:
    """adb connect over TLS, then `adb tcpip 5555` so adb-shell can use the TV."""
    target = f"{host}:{int(connect_port)}"
    try:
        out = _run(adb, ["connect", target], timeout=20)
        low = out.lower()
        if "connected to" not in low:
            raise Exception(
                f"Không kết nối được {target}: {out or 'không có phản hồi'}. "
                "Cổng kết nối là cổng hiển thị ở màn hình chính «Gỡ lỗi không dây» (khác cổng ghép cặp)."
            )
        res = _run(adb, ["-s", target, "tcpip", str(int(tcp_port))], timeout=20)
        if "restarting" not in res.lower():
            raise Exception(f"adb tcpip thất bại: {res or 'không có phản hồi'}")
        return res
    finally:
        # Do not leave a background adb server holding port 5037 / the TV's connection.
        try:
            _run(adb, ["kill-server"], timeout=10)
        except Exception:
            pass
