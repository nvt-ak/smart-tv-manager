"""Tải APK SmartTV Home dựng sẵn (GitHub Actions của repo nvt-ak/smtv-home) và kiểm tra SHA-256."""
import hashlib
import json
import os
import ssl
import urllib.request
from typing import Callable

import paths
from core import launcher_builder

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover
    _CTX = ssl.create_default_context()


def load_pin() -> dict:
    p = os.path.join(paths.app_root(), "data", "cleanyourtv", "launcher-pin.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _get(url: str, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "SmartTVManager"})
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
        return r.read()


def latest_sha() -> str:
    """SHA-256 of the newest published APK (a 80-byte file: cheap to poll). Raises when offline."""
    pin = load_pin()
    base = pin["release_base"].rstrip("/")
    return _get(f"{base}/{pin['sha256_file']}", 20).decode("utf-8", "replace").split()[0].lower()


def _file_sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def cached_sha() -> str:
    """SHA-256 of the cached APK, or '' when there is none."""
    p = launcher_builder.cached_apk_path()
    try:
        return _file_sha(p) if os.path.isfile(p) else ""
    except OSError:
        return ""


def download_apk(on_step: Callable[[str, str], None], force: bool = False) -> str:
    """Download the newest APK unless the cached one already is it. Returns the cached path."""
    pin = load_pin()
    base = pin["release_base"].rstrip("/")
    on_step("download_start", f"{base}/{pin['apk']}")
    try:
        want = latest_sha()
        if not force and want and cached_sha() == want:
            on_step("download_cached", f"đã có bản mới nhất · sha256 {want[:12]}…")
            return launcher_builder.cached_apk_path()
        data = _get(f"{base}/{pin['apk']}", 300)
    except Exception as exc:
        raise Exception(
            f"Không tải được bản dựng sẵn ({exc}). Release «smtv-home-latest» có thể chưa được tạo "
            "(chạy workflow «Build APK» trên repo nvt-ak/smtv-home)."
        ) from exc
    got = hashlib.sha256(data).hexdigest()
    if len(want) != 64 or got != want:
        raise Exception(f"SHA-256 không khớp (mong đợi {want[:12]}…, nhận {got[:12]}…) — huỷ để an toàn.")
    out = launcher_builder.cached_apk_path()
    with open(out, "wb") as f:
        f.write(data)
    on_step("download_done", f"{len(data) // 1024} KB · sha256 {got[:12]}…")
    return out
