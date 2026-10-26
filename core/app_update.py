"""Update SmartTV Manager from its own GitHub releases instead of downloading it again from the website.

Flow: check_latest() -> download() (size and SHA-256 checked) -> prepare_helper(). The helper is a small script
that waits for this process to exit, swaps the installed files and starts the app again. It runs from a frozen
build only: from source there is nothing to replace, so the caller opens the release page instead.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import ssl
import subprocess
import sys
import threading
import urllib.request
import zipfile
from typing import Callable, Optional

from app_brand import user_data_dir

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover
    _CTX = ssl.create_default_context()

REPO = "nvt-ak/smart-tv-manager"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASE_PAGE = f"https://github.com/{REPO}/releases/latest"
# Only files of this repo's releases are ever downloaded and run.
DOWNLOAD_PREFIX = f"https://github.com/{REPO}/releases/download/"
WIN_ASSET = "SmartTVManager-windows-x64.zip"
MAC_ASSET = "SmartTVManager-macos.dmg"
MAC_APP_NAME = "SmartTV Manager.app"
FAILURE_LOG = "update-error.log"


def parse_version(text: str) -> tuple:
    """'v1.9.0' -> (1, 9, 0). Anything after the numbers (a suffix such as -rc1) is ignored."""
    m = re.match(r"^\s*v?(\d+(?:\.\d+)*)", str(text or ""))
    if not m:
        return ()
    return tuple(int(p) for p in m.group(1).split("."))


def is_newer(latest: str, current: str) -> bool:
    a, b = parse_version(latest), parse_version(current)
    if not a or not b:
        return False
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)) > b + (0,) * (width - len(b))


def platform_asset_name(platform: Optional[str] = None) -> Optional[str]:
    plat = platform or sys.platform
    if plat == "win32":
        return WIN_ASSET
    if plat == "darwin":
        return MAC_ASSET
    return None


def pick_asset(release: dict, platform: Optional[str] = None) -> Optional[dict]:
    want = platform_asset_name(platform)
    if not want:
        return None
    for a in release.get("assets") or []:
        if a.get("name") != want:
            continue
        url = str(a.get("browser_download_url") or "")
        if not url.startswith(DOWNLOAD_PREFIX):
            return None
        digest = str(a.get("digest") or "")
        sha = digest.split(":", 1)[1].lower() if digest.lower().startswith("sha256:") else ""
        return {"name": want, "url": url, "size": int(a.get("size") or 0), "sha256": sha}
    return None


def check_latest(current: str, fetch: Optional[Callable[[str], bytes]] = None, platform: Optional[str] = None) -> dict:
    """Ask GitHub for the newest release. Returns {available, version, notes, asset, page_url, can_self_update}."""
    getter = fetch or _http_get
    release = json.loads(getter(API_LATEST).decode("utf-8"))
    tag = str(release.get("tag_name") or "")
    version = tag.lstrip("vV")
    asset = pick_asset(release, platform)
    return {
        "available": is_newer(version, current),
        "current": current,
        "version": version,
        "notes": str(release.get("body") or "")[:4000],
        "page_url": str(release.get("html_url") or RELEASE_PAGE),
        "asset": asset,
        "can_self_update": bool(asset) and can_self_update(platform),
    }


def _http_get(url: str, timeout: float = 20.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "SmartTVManager", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
        return r.read()


def install_dir(platform: Optional[str] = None) -> str:
    """Windows: the folder holding the exe. macOS: the .app bundle that is running."""
    exe = os.path.abspath(sys.executable)
    if (platform or sys.platform) == "darwin":
        return os.path.dirname(os.path.dirname(os.path.dirname(exe)))
    return os.path.dirname(exe)


def can_self_update(platform: Optional[str] = None) -> bool:
    """Only a packaged build whose install location this user may write to."""
    plat = platform or sys.platform
    if not getattr(sys, "frozen", False) or plat not in ("win32", "darwin"):
        return False
    target = install_dir(plat)
    parent = os.path.dirname(target) if plat == "darwin" else target
    return os.path.isdir(target) and os.access(parent, os.W_OK)


def updates_dir() -> str:
    d = os.path.join(user_data_dir(), "updates")
    os.makedirs(d, exist_ok=True)
    return d


def download(asset: dict, on_progress: Callable[[int, int], None], dest_dir: Optional[str] = None) -> str:
    """Stream the release file to disk and verify it. Raises on a wrong size or checksum, leaving nothing behind."""
    url = str(asset.get("url") or "")
    if not url.startswith(DOWNLOAD_PREFIX):
        raise Exception("Địa chỉ tải không thuộc repo SmartTV Manager — huỷ để an toàn.")
    out_dir = dest_dir or updates_dir()
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, os.path.basename(str(asset.get("name") or "update.bin")))
    part = out + ".part"
    sha = hashlib.sha256()
    done = 0
    req = urllib.request.Request(url, headers={"User-Agent": "SmartTVManager"})
    try:
        with urllib.request.urlopen(req, timeout=60, context=_CTX) as r, open(part, "wb") as f:
            total = int(r.headers.get("Content-Length") or asset.get("size") or 0)
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                sha.update(chunk)
                done += len(chunk)
                on_progress(done, total)
        _verify(done, sha.hexdigest(), asset)
        os.replace(part, out)
    except Exception:
        try:
            os.remove(part)
        except OSError:
            pass
        raise
    return out


def _verify(size: int, digest: str, asset: dict) -> None:
    want_size = int(asset.get("size") or 0)
    if want_size and size != want_size:
        raise Exception(f"File tải về có dung lượng {size} B, GitHub báo {want_size} B — tải lại.")
    want_sha = str(asset.get("sha256") or "").lower()
    if want_sha and digest != want_sha:
        raise Exception(f"SHA-256 không khớp (mong đợi {want_sha[:12]}…, nhận {digest[:12]}…) — huỷ để an toàn.")


def _unsafe_for_cmd(*paths: str) -> bool:
    return any('"' in p or "%" in p or "\n" in p for p in paths)


def windows_script(pid: int, src: str, dst: str, exe: str, log: str) -> str:
    """cmd script: wait until this process is gone, copy the new files over the install folder, start the app."""
    if _unsafe_for_cmd(src, dst, exe, log):
        raise Exception("Đường dẫn cài đặt có ký tự đặc biệt (% hoặc \") — hãy cập nhật thủ công.")
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        ":wait\r\n"
        f'tasklist /FI "PID eq {int(pid)}" 2>nul | find "{int(pid)}" >nul\r\n'
        "if not errorlevel 1 (\r\n"
        "  timeout /t 1 /nobreak >nul\r\n"
        "  goto wait\r\n"
        ")\r\n"
        f'robocopy "{src}" "{dst}" /E /R:10 /W:1 /NFL /NDL /NJH /NJS /NP >nul\r\n'
        "if errorlevel 8 (\r\n"
        f'  echo robocopy failed > "{log}"\r\n'
        "  exit /b 1\r\n"
        ")\r\n"
        f'start "" "{exe}"\r\n'
    )


def mac_script(pid: int, dmg: str, bundle: str, log: str) -> str:
    """sh script: wait for this process, mount the DMG, swap the .app, clear quarantine, reopen."""
    q = shlex.quote
    return (
        "#!/bin/bash\n"
        f"while kill -0 {int(pid)} 2>/dev/null; do sleep 1; done\n"
        f"MNT=$(hdiutil attach -nobrowse -noverify -noautoopen {q(dmg)} | grep -o '/Volumes/.*' | head -1)\n"
        f'APP="$MNT/{MAC_APP_NAME}"\n'
        f'if [ ! -d "$APP" ]; then echo "no app in dmg" > {q(log)}; hdiutil detach "$MNT" -quiet; exit 1; fi\n'
        f"rm -rf {q(bundle + '.new')}\n"
        f'cp -R "$APP" {q(bundle + ".new")} && rm -rf {q(bundle)} && mv {q(bundle + ".new")} {q(bundle)} '
        f"|| {{ echo copy failed > {q(log)}; hdiutil detach \"$MNT\" -quiet; exit 1; }}\n"
        'hdiutil detach "$MNT" -quiet\n'
        f"xattr -dr com.apple.quarantine {q(bundle)} 2>/dev/null\n"
        f"open {q(bundle)}\n"
    )


def extract_windows(zip_path: str, work_dir: str) -> str:
    """Unpack the release zip and return the folder whose content replaces the install folder."""
    target = os.path.join(work_dir, "new")
    if os.path.isdir(target):
        _rmtree(target)
    with zipfile.ZipFile(zip_path) as z:
        bad = z.testzip()
        if bad:
            raise Exception(f"File zip hỏng ({bad}) — tải lại.")
        z.extractall(target)
    inner = os.path.join(target, "SmartTVManager")
    root = inner if os.path.isfile(os.path.join(inner, "SmartTVManager.exe")) else target
    if not os.path.isfile(os.path.join(root, "SmartTVManager.exe")):
        raise Exception("Bản tải về không có SmartTVManager.exe — huỷ.")
    return root


def _rmtree(path: str) -> None:
    import shutil
    shutil.rmtree(path, ignore_errors=True)


def prepare_and_launch(downloaded: str, pid: Optional[int] = None, platform: Optional[str] = None) -> str:
    """Write the helper script next to the download and start it detached. The caller must exit right after."""
    plat = platform or sys.platform
    pid = int(pid or os.getpid())
    work = os.path.dirname(downloaded)
    log = os.path.join(work, FAILURE_LOG)
    if os.path.exists(log):
        os.remove(log)
    if plat == "win32":
        src = extract_windows(downloaded, work)
        script = os.path.join(work, "apply-update.cmd")
        with open(script, "w", encoding="utf-8", newline="") as f:
            f.write(windows_script(pid, src, install_dir("win32"), os.path.abspath(sys.executable), log))
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
        subprocess.Popen(["cmd", "/c", script], creationflags=flags, close_fds=True)
        return script
    if plat == "darwin":
        script = os.path.join(work, "apply-update.sh")
        with open(script, "w", encoding="utf-8", newline="\n") as f:
            f.write(mac_script(pid, downloaded, install_dir("darwin"), log))
        os.chmod(script, 0o700)
        subprocess.Popen(["/bin/bash", script], start_new_session=True, close_fds=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return script
    raise Exception("Hệ điều hành này chưa hỗ trợ tự cập nhật.")


def cleanup_old(keep: Optional[str] = None) -> None:
    """Remove the files of earlier updates (called at start-up, when no helper is running any more)."""
    d = os.path.join(user_data_dir(), "updates")
    if not os.path.isdir(d):
        return
    for name in os.listdir(d):
        p = os.path.join(d, name)
        if name == FAILURE_LOG or (keep and os.path.abspath(p) == os.path.abspath(keep)):
            continue
        if os.path.isdir(p):
            _rmtree(p)
        else:
            try:
                os.remove(p)
            except OSError:
                pass


def pop_failure() -> str:
    """What the last helper run reported if it could not swap the files (read once, then forgotten)."""
    path = os.path.join(user_data_dir(), "updates", FAILURE_LOG)
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read().strip()
        os.remove(path)
    except OSError:
        return ""
    return text or "không rõ lý do"


class Progress:
    """Thread-safe status the UI polls while a download runs."""

    def __init__(self):
        self._lock = threading.Lock()
        self._s = {"state": "idle", "done": 0, "total": 0, "error": "", "path": ""}

    def set(self, **kw):
        with self._lock:
            self._s.update(kw)

    def get(self) -> dict:
        with self._lock:
            return dict(self._s)
