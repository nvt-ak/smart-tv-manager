"""SmartTV Manager: desktop app, lists TVs on the LAN and connects over ADB."""
import os
from concurrent.futures import ThreadPoolExecutor

import webview

import adb_client
from app_brand import APP_DISPLAY_NAME, APP_VERSION
import paths
import store
from core.package_manager import PackageManager
from core.safety import safety
from core.apk_analyzer import ApkAnalyzer
from core.apk_installer import ApkInstaller
from core.launcher_detector import LauncherDetector
from core import launcher_builder, launcher_download, adb_binary, app_update
from core.theme_manager import ThemeManager
from core import theme_widgets
from core import preview_check
from core.cleanyourtv_themes import CleanyourtvThemes
from core.clean_suggestions import CleanSuggestionEngine
from core.device_profiles import DeviceProfiles
from core import ai_clean
from core import home_widgets
from core.tv_guard import TvGuard, GuardError
import settings_store
import shutil
import subprocess
import sys
import base64
import json
import os
import re
import tempfile
import threading
import time
import uuid

THEME_APPLY_LOG = os.path.join(adb_client.KEY_DIR, "theme-apply.log")
PLATFORM_CACHE_SECONDS = 5.0
LG_SCAN_PORTS = (3001, 3000)  # secure first; 3000 is the plain WS port of older TVs


def classify_scan_ports(open_ports):
    """Platforms a host *might* be, judged only by which ports answered.

    Ports 3000/3001 are also common development ports, so this is a hint: the user still
    confirms by connecting (LG pairing then proves it is a TV). A host with both families
    open yields two candidates and the user picks.
    """
    open_ports = set(open_ports)
    candidates = []
    if adb_client.PORT in open_ports:
        candidates.append({"platform": "android_tv", "port": adb_client.PORT})
    lg_port = next((p for p in LG_SCAN_PORTS if p in open_ports), None)
    if lg_port:
        candidates.append({"platform": "lg_webos", "port": lg_port})
    return candidates


class Api:
    def __init__(self):
        self._webos_cache = {}
        self._webos_deploying = set()  # "host:port" with a Home deployment in flight
        self._platform_cache = {}
        self._pm_cache = {}
        self._dev_cache = {}
        self._themes = CleanyourtvThemes()
        self._apply_jobs = {}
        self._apply_jobs_lock = threading.Lock()
        self._dev_locks = {}
        # Dedicated light connection for remote key presses: not blocked by long operations
        # and reused (a fresh TCP + auth handshake per key press was slow).
        self._key_devs = {}
        self._key_locks = {}
        self._home_cache = {}
        self._clean_engine = CleanSuggestionEngine()
        self._device_profiles = DeviceProfiles()
        self._identity_cache = {}
        self._update_progress = app_update.Progress()

    def app_version(self):
        """Single source of truth for the version label in the UI (app_brand.APP_VERSION)."""
        return APP_VERSION

    # ---- self-update (core/app_update.py) -------------------------------------------------------
    def check_app_update(self):
        """Newest GitHub release vs this build. Never raises: the UI shows `error` quietly."""
        try:
            info = app_update.check_latest(APP_VERSION)
        except Exception as exc:
            return {"available": False, "current": APP_VERSION, "error": f"Không kiểm tra được bản mới: {exc}"}
        info["error"] = ""
        info["previous_failure"] = app_update.pop_failure()
        return info

    def download_app_update(self):
        """Start downloading the newest release in the background; the UI polls app_update_status()."""
        if self._update_progress.get()["state"] == "downloading":
            return {"started": False}
        try:
            info = app_update.check_latest(APP_VERSION)
        except Exception as exc:
            raise Exception(f"Không kiểm tra được bản mới: {exc}") from exc
        if not info["available"]:
            raise Exception("Đang dùng bản mới nhất.")
        if not info["can_self_update"]:
            raise Exception("Bản cài này không tự cập nhật được (chạy từ mã nguồn hoặc thư mục cài không ghi được).")
        asset = info["asset"]
        self._update_progress.set(state="downloading", done=0, total=asset["size"], error="", path="")

        def run():
            try:
                app_update.cleanup_old()
                path = app_update.download(
                    asset, lambda done, total: self._update_progress.set(done=done, total=total or asset["size"])
                )
                self._update_progress.set(state="ready", path=path)
            except Exception as exc:
                self._update_progress.set(state="error", error=str(exc))

        threading.Thread(target=run, daemon=True).start()
        return {"started": True, "version": info["version"]}

    def app_update_status(self):
        return self._update_progress.get()

    def apply_app_update(self):
        """Start the helper that swaps the files, then quit so it can. The app reopens by itself."""
        st = self._update_progress.get()
        if st["state"] != "ready" or not st["path"] or not os.path.isfile(st["path"]):
            raise Exception("Chưa tải xong bản cập nhật.")
        app_update.prepare_and_launch(st["path"])
        threading.Timer(1.0, lambda: os._exit(0)).start()
        return {"quitting": True}

    def open_release_page(self):
        import webbrowser
        webbrowser.open(app_update.RELEASE_PAGE)
        return True

    def _device_record(self, host):
        """(platform, port) of a saved device. Cached for a few seconds because every key
        press asks for it; connect() and remove() invalidate the entry explicitly."""
        now = time.monotonic()
        hit = self._platform_cache.get(host)
        if hit and now - hit[0] < PLATFORM_CACHE_SECONDS:
            return hit[1], hit[2]
        device = next((d for d in store.load() if d.get("host") == host), None) or {}
        platform = device.get("platform", "android_tv")
        port = device.get("port")
        self._platform_cache[host] = (now, platform, port)
        return platform, port

    def _device_platform(self, host):
        return self._device_record(host)[0]

    def _lg_port(self, host, port=None):
        """Port of a saved LG TV. Callers often pass the Android default (5555), which never
        belongs to an LG TV, so the saved record wins over the argument."""
        saved = self._device_record(host)[1]
        return int(saved or port or 3001)

    def _require_android(self, host):
        if self._device_platform(host) == "lg_webos":
            raise Exception("Chức năng này chỉ hỗ trợ Android TV; không hỗ trợ LG webOS.")

    def _get_webos(self, host, port=3001):
        from core.webos_client import WebOsClient
        key = f"{host}:{int(port)}"
        with self._dev_op_lock(host, port):
            client = self._webos_cache.get(key)
            if client is None:
                client = WebOsClient(host, int(port))
                try:
                    client.connect()
                except Exception:
                    client.close()
                    raise
                self._webos_cache[key] = client
            return client

    def _drop_webos(self, host):
        """Close every cached LG client of this host; returns the ports they used."""
        ports = []
        for key in [k for k in self._webos_cache if k.rpartition(":")[0] == host]:
            self._webos_cache.pop(key).close()
            ports.append(int(key.rpartition(":")[2]))
        return ports

    def _forget_webos_keys(self, host, ports):
        """Delete pairing keys and pinned certificates; True when any record existed."""
        from core.webos_client import WebOsKeyStore, identity_for
        keys = WebOsKeyStore()
        return any([keys.delete(identity_for(host, p)) for p in sorted(set(ports))])

    def forget_webos_pairing(self, host):
        """Drop the saved pairing key and pinned certificate of an LG TV; the next connect pairs
        again. Needed after a firmware update changed the TV certificate."""
        platform, saved_port = self._device_record(host)
        if platform != "lg_webos":
            raise Exception("Chỉ áp dụng cho TV LG webOS.")
        ports = {3000, 3001, *self._drop_webos(host)}
        if saved_port:
            ports.add(int(saved_port))
        return {"ok": True, "removed": self._forget_webos_keys(host, ports)}

    def list_inputs(self, host, port=3001):
        if self._device_platform(host) != "lg_webos":
            raise Exception("Danh sách HDMI này dành cho LG webOS.")
        return self._get_webos(host, self._lg_port(host, port)).list_inputs()

    def switch_input(self, host, port=3001, input_id=""):
        if self._device_platform(host) != "lg_webos":
            raise Exception("Chuyển HDMI này dành cho LG webOS.")
        self._get_webos(host, self._lg_port(host, port)).switch_input(input_id)
        return {"ok": True}

    def _dev_op_lock(self, host, port=5555):
        key = f"{host}:{port}"
        if key not in self._dev_locks:
            self._dev_locks[key] = threading.RLock()
        return self._dev_locks[key]

    def _drop_dev(self, host, port=5555):
        key = f"{host}:{port}"
        dev = self._dev_cache.pop(key, None)
        if dev:
            try:
                dev.close()
            except Exception:
                pass
        pm = self._pm_cache.pop(key, None)
        if pm:
            try:
                pm.device.close()
            except Exception:
                pass

    def shutdown(self):
        """Close every cached ADB session (call when the app exits)."""
        for client in list(self._webos_cache.values()):
            client.close()
        self._webos_cache.clear()
        for kd in list(self._key_devs.values()):
            try:
                kd.close()
            except Exception:
                pass
        self._key_devs.clear()
        keys = set(self._dev_cache.keys()) | set(self._pm_cache.keys())
        for key in list(keys):
            host, _, port_s = key.rpartition(":")
            if not host:
                continue
            try:
                port = int(port_s)
            except ValueError:
                port = 5555
            self._drop_dev(host, port)

    def _ping_cached_dev(self, dev, timeout=None):
        timeout = timeout if timeout is not None else adb_client.QUICK_CHECK_TIMEOUT
        try:
            adb_client.ensure_connected(dev, timeout=timeout)
            return True
        except Exception:
            return False

    def _get_dev(self, host, port=5555):
        self._require_android(host)
        key = f"{host}:{port}"
        if key in self._dev_cache:
            if self._ping_cached_dev(self._dev_cache[key]):
                return self._dev_cache[key]
            self._drop_dev(host, port)
        dev = adb_client.connect(host, int(port))
        self._dev_cache[key] = dev
        return dev

    def _cached_current_home(self, pm: PackageManager, host, port=5555, max_age=45.0):
        key = f"{host}:{port}"
        now = time.monotonic()
        hit = self._home_cache.get(key)
        if hit and (now - hit[0]) < max_age:
            return hit[1]
        home = pm.get_current_home()
        self._home_cache[key] = (now, home)
        return home

    def _get_pm(self, host, port=5555):
        self._require_android(host)
        key = f"{host}:{port}"
        if key in self._pm_cache:
            if self._ping_cached_dev(self._pm_cache[key].device):
                return self._pm_cache[key]
            self._drop_dev(host, port)
        dev = self._get_dev(host, port)
        pm = PackageManager(dev)
        self._pm_cache[key] = pm
        return pm

    def _adb_timeout_error(self, err) -> bool:
        msg = str(err).lower()
        return "timed out" in msg or "tcptimeout" in msg.replace("_", "")

    def _adb_shell_error(self, host, port, err: Exception) -> Exception:
        if self._adb_timeout_error(err):
            return Exception(
                f"ADB timeout — TV {host}:{port} không phản hồi (Wi‑Fi chậm, TV ngủ, hoặc mất kết nối). "
                "Thử bật màn hình TV, tab Thiết bị → Làm mới / Kết nối lại."
            )
        return Exception(str(err))

    def _run_device_shell(self, host, port, command: str) -> str:
        dev = self._get_dev(host, int(port))
        try:
            return adb_client.run_shell(dev, command)
        except Exception as e:
            if self._adb_timeout_error(e):
                self._drop_dev(host, port)
            raise

    def _online_via_cache(self, host, port):
        """Reuse an already-open ADB session instead of a fresh handshake.

        Returns True/False when the cached session answers (or is busy with a real operation,
        which proves it is alive), or None when there is no cached session to ask.
        """
        key = f"{host}:{int(port)}"
        dev = self._dev_cache.get(key)
        if dev is None or not getattr(dev, "available", False):
            return None
        lock = self._dev_op_lock(host, port)
        if not lock.acquire(blocking=False):
            return True  # another operation is using the session right now
        try:
            if self._ping_cached_dev(dev):
                return True
            self._drop_dev(host, port)
            return None  # session was dead: fall back to a fresh check
        finally:
            lock.release()

    def list_devices(self, check="adb"):
        """List saved TVs. check: cache (instant) | port (TCP 5555) | adb (full handshake)."""
        devices = store.load()
        if not devices:
            return []

        mode = (check or "adb").strip().lower() or "adb"
        if mode in ("cache", "false", "0", "no"):
            return [dict(d) for d in devices]
        if mode not in ("port", "adb"):
            mode = "adb"

        def check_one(d):
            host = d["host"]
            port = int(d.get("port", 5555))
            if d.get("platform") == "lg_webos" or mode == "port":
                online = adb_client.port_reachable(host, port)
            else:
                online = self._online_via_cache(host, port)
                if online is None:
                    online = adb_client.quick_check(host, port)
            nd = dict(d)
            nd["online"] = online
            return host, online, nd

        workers = min(8, len(devices))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(check_one, devices))
        store.batch_update_online({host: online for host, online, _ in rows})
        return [nd for _, _, nd in rows]

    def scan_all(self):
        """One sweep for every supported platform: [{host, ports, candidates}] sorted by IP."""
        found = adb_client.scan_ports((adb_client.PORT, *LG_SCAN_PORTS))
        rows = []
        for host in sorted(found, key=lambda ip: tuple(int(p) for p in ip.split("."))):
            candidates = classify_scan_ports(found[host])
            if candidates:
                rows.append({"host": host, "ports": found[host], "candidates": candidates})
        return rows

    def scan(self, platform="android_tv"):
        if platform == "lg_webos":
            import ipaddress
            hosts = [str(h) for net in adb_client._local_subnets()
                     for h in ipaddress.ip_network(net).hosts()]
            with ThreadPoolExecutor(max_workers=48) as pool:
                return sorted(h for h, ok in zip(hosts, pool.map(
                    lambda h: adb_client.port_reachable(h, 3001), hosts)) if ok)
        found = adb_client.scan_subnet()
        # Return all found devices (including already saved) so user can see them
        return found

    def _connect_and_cache(self, host, port):
        with self._dev_op_lock(host, port):
            self._drop_dev(host, port)
            dev = adb_client.connect(host, int(port), timeout=30.0)
            try:
                info = {
                    "model": adb_client.run_shell(dev, "getprop ro.product.model").strip(),
                    "android": adb_client.run_shell(dev, "getprop ro.build.version.release").strip(),
                    "build": adb_client.run_shell(dev, "getprop ro.build.display.id").strip(),
                }
            except Exception:
                try:
                    dev.close()
                except Exception:
                    pass
                raise
            try:  # later calls without explicit timeouts should not inherit the 30s connect wait
                dev._default_transport_timeout_s = adb_client.CONNECT_TIMEOUT
            except Exception:
                pass
            self._dev_cache[f"{host}:{int(port)}"] = dev
            return info

    def connect(self, host, port=5555, name=None, platform=None):
        parsed_host, _parsed_port = adb_client.parse_host_port(host, port)
        platform = platform or self._device_platform(parsed_host)
        if platform not in ("android_tv", "lg_webos"):
            raise Exception("Nền tảng TV không hợp lệ.")
        if platform == "lg_webos":
            host, port = adb_client.parse_host_port(host, 3001 if int(port or 5555) == 5555 else port)
            client = self._get_webos(host, port)
            info = dict(client.get_info())
            info.update(platform="lg_webos", port=port)
            store.upsert(host, port, name or info.get("model") or host, platform="lg_webos")
            self._platform_cache.pop(host, None)
            return info
        # Accept "ip:port" typed into the host field (e.g. 192.168.1.3:44525).
        host, port = adb_client.parse_host_port(host, port)
        try:
            return self._connect_plain(host, port, name)
        except adb_client.WirelessDebuggingError as wd:
            # Port belongs to Wireless debugging: use Google's adb (already paired?) to
            # switch the TV to TCP 5555, then continue with the normal path.
            try:
                adb = adb_binary.ensure_adb()
                adb_binary.switch_to_tcpip(adb, host, port)
            except Exception as e:
                raise Exception(
                    f"{host}:{port} là cổng Gỡ lỗi không dây, cần ghép cặp bằng mã một lần "
                    f"(chi tiết adb: {str(e)[:200]})."
                ) from wd
            time.sleep(2.0)
            return self._connect_plain(host, 5555, name)

    def _connect_plain(self, host, port, name=None):
        try:
            # Timeout dài hơn để kịp bấm "Cho phép" trên TV ở lần kết nối đầu.
            # Kết nối vừa mở được giữ lại trong cache để các thao tác sau dùng tiếp.
            info = self._connect_and_cache(host, int(port))
        except Exception as e:
            if self._adb_timeout_error(e):
                raise Exception(
                    f"Không kết nối được {host}:{port} — TV không trả lời bắt tay ADB. "
                    "Kiểm tra: (1) TV đang bật màn hình, (2) đã bật Gỡ lỗi USB/Gỡ lỗi mạng (ADB over network), "
                    "(3) nếu TV hiện hộp thoại \"Cho phép gỡ lỗi USB?\" thì chọn Luôn cho phép, "
                    "(4) máy tính và TV cùng mạng Wi‑Fi/LAN. Sau đó bấm Kết nối lại."
                ) from e
            raise
        store.upsert(host, int(port), name or info["model"] or host, platform="android_tv")
        self._platform_cache.pop(host, None)
        return info

    def adb_wireless_setup(self, host, pair_port, code, connect_port=None):
        """Pair with Android 11+ Wireless debugging, then switch the TV to TCP 5555.

        Needs Google's `adb` (downloaded once if missing). Afterwards the normal
        connect(host, 5555) path (adb-shell) works.
        """
        host, _ = adb_client.parse_host_port(host)
        code = re.sub(r"\D", "", str(code or ""))
        if len(code) != 6:
            raise Exception("Mã ghép cặp phải gồm 6 chữ số")
        adb = adb_binary.ensure_adb()
        if str(pair_port or "").strip():
            pair_port = int(pair_port)
        else:
            pair_port = adb_binary.find_pair_port(adb, host)
            if pair_port is None:
                raise Exception(
                    "Không tự dò được cổng ghép cặp. Hãy giữ hộp thoại «Ghép nối thiết bị bằng mã» "
                    "mở trên TV rồi thử lại, hoặc nhập cổng ghép cặp thủ công."
                )
        adb_binary.pair(adb, host, pair_port, code)
        cport = int(connect_port) if str(connect_port or "").strip() else None
        if cport is None:
            cport = adb_binary.find_connect_port(adb, host)
        if cport is None:
            raise Exception(
                "Ghép cặp thành công nhưng chưa tự tìm được cổng kết nối. Nhập thêm «cổng kết nối» "
                "(cổng hiển thị ở màn hình chính Gỡ lỗi không dây, ví dụ 44525) rồi bấm lại."
            )
        adb_binary.switch_to_tcpip(adb, host, cport)
        time.sleep(2.0)  # adbd restarts in TCP mode
        return self.connect(host, 5555)

    def rename(self, host, name):
        if not name or not name.strip():
            raise ValueError("Tên không được để trống")
        store.rename(host, name.strip())
        return True

    def remove(self, host):
        platform, saved_port = self._device_record(host)
        cached_ports = self._drop_webos(host)
        if platform == "lg_webos" or cached_ports:
            # The pairing key and pinned certificate live outside devices.json under a hashed
            # name; leaving them would block re-adding the TV after a certificate change.
            ports = {3000, 3001, *cached_ports}
            if saved_port:
                ports.add(int(saved_port))
            self._forget_webos_keys(host, ports)
        devices = store.remove(host)
        self._platform_cache.pop(host, None)
        return devices

    def remote_key(self, host, port=5555, keycode=4):
        if self._device_platform(host) == "lg_webos":
            commands = {3:"home", 4:"back", 19:"up", 20:"down", 21:"left", 22:"right",
                        23:"enter", 66:"enter", 24:"volume_up", 25:"volume_down", 164:"mute",
                        26:"power", 85:"play", 86:"stop", 87:"fast_forward", 88:"rewind",
                        89:"rewind", 90:"fast_forward", 126:"play", 127:"pause",
                        82:"menu", 176:"settings", 178:"input", 166:"channel_up", 167:"channel_down", 183:"red", 184:"green", 185:"yellow", 186:"blue"}
            if 7 <= int(keycode) <= 16:
                command = str(int(keycode) - 7)
            else:
                command = commands.get(int(keycode))
            if not command:
                raise Exception("Phím này chưa được hỗ trợ trên LG webOS.")
            self._get_webos(host, self._lg_port(host, port)).remote(command)
            return {"ok": True}
        keycode = int(keycode)
        cmd = f"input keyevent {keycode}"
        if keycode == 3:
            # `input keyevent 3` is injected, so it bypasses Gathin's HomeKeyService and the
            # firmware routes it to the stock launcher. Open Gathin directly when installed.
            pkgs = " ".join(LauncherDetector.PACKAGES)
            cmd = (
                f"for p in {pkgs}; do pm path $p >/dev/null 2>&1 && "
                f"am start -a android.intent.action.MAIN -c android.intent.category.HOME "
                f"-n $p/com.gathin.tvhome.MainActivity >/dev/null 2>&1 && exit 0; done; input keyevent 3"
            )
        key = f"{host}:{int(port)}"
        lock = self._key_locks.setdefault(key, threading.Lock())
        with lock:
            last = None
            for attempt in range(2):
                dev = self._key_devs.get(key)
                try:
                    if dev is None or not getattr(dev, "available", False):
                        dev = adb_client.connect(host, int(port))
                        self._key_devs[key] = dev
                    dev.shell(cmd, transport_timeout_s=8.0, read_timeout_s=8.0, timeout_s=8.0)
                    adb_client.mark_ok(dev)
                    return {"ok": True}
                except Exception as e:
                    last = e
                    self._key_devs.pop(key, None)
                    try:
                        if dev:
                            dev.close()
                    except Exception:
                        pass
            raise self._adb_shell_error(host, port, last)

    def send_input_text(self, host, port=5555, text=""):
        if self._device_platform(host) == "lg_webos":
            if not str(text).strip():
                raise Exception("Nội dung trống")
            self._get_webos(host, self._lg_port(host, port)).send_text(text)
            return {"ok": True}
        text = (text or "").strip()
        if not text:
            raise Exception("Nội dung trống")
        escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace(" ", "%s")
        with self._dev_op_lock(host, port):
            try:
                self._run_device_shell(host, port, f'input text "{escaped}"')
                return {"ok": True}
            except Exception as e:
                raise self._adb_shell_error(host, port, e) from e

    def device_shell(self, host, port=5555, command=""):
        self._require_android(host)
        command = (command or "").strip()
        if not command:
            raise Exception("Lệnh trống")
        with self._dev_op_lock(host, port):
            try:
                out = self._run_device_shell(host, port, command) or ""
                return {"output": out.strip()}
            except Exception as e:
                raise self._adb_shell_error(host, port, e) from e

    @staticmethod
    def screenshots_dir() -> str:
        d = os.path.join(os.path.expanduser("~"), ".smarttv-manager", "screenshots")
        os.makedirs(d, exist_ok=True)
        return d

    def capture_screenshot(self, host, port=5555):
        """Capture the TV screen, pull the PNG to ~/.smarttv-manager/screenshots and return it.

        Live TV, HDMI inputs and some streaming apps give a black frame: that is the TV, not an error.
        """
        self._require_android(host)
        remote = "/data/local/tmp/smarttvmanager-shot.png"
        name = time.strftime("tv_%Y%m%d_%H%M%S") + ".png"
        local = os.path.join(self.screenshots_dir(), name)
        with self._dev_op_lock(host, port):
            try:
                dev = self._get_dev(host, int(port))
                out = adb_client.run_shell(dev, f"rm -f {remote}; screencap -p {remote} 2>&1; ls -l {remote} 2>&1") or ""
                if "No such file" in out:
                    raise Exception("TV không chụp được màn hình: " + out.strip()[:200])
                timeout = adb_client.transfer_timeout_s(8 * 1024 * 1024)
                dev.pull(remote, local, transport_timeout_s=timeout, read_timeout_s=timeout)
                try:
                    adb_client.run_shell(dev, f"rm -f {remote}")
                except Exception:
                    pass
            except Exception as e:
                if self._adb_timeout_error(e):
                    self._drop_dev(host, port)
                raise self._adb_shell_error(host, port, e) from e
        if not os.path.isfile(local) or os.path.getsize(local) <= 0:
            raise Exception("Không lấy được ảnh về máy (file rỗng).")
        with open(local, "rb") as f:
            data = f.read()
        return {
            "path": local,
            "name": name,
            "bytes": len(data),
            "png_b64": base64.b64encode(data).decode("ascii"),
        }

    @staticmethod
    def theme_shot_path(theme_id: str, host=None, port=5555) -> str:
        """A real-TV capture belongs to one device: the same theme looks different on another TV."""
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(theme_id or ""))[:80] or "theme"
        if host:
            dev = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{host}_{int(port or 5555)}")[:60]
            safe = f"{safe}@{dev}"
        d = os.path.join(os.path.expanduser("~"), ".smarttv-manager", "theme-shots")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, safe + ".jpg")

    def capture_theme_screenshot(self, host, port=5555, theme_id="", delay_s=5):
        """Wait for Home to redraw, capture the TV and keep a 1280x720 JPEG as that theme's real preview."""
        try:
            # A TV in standby captures as a black frame, and shows nothing of the new Home either.
            with self._dev_op_lock(host, port):
                adb_client.run_shell(self._get_dev(host, int(port)), "input keyevent KEYCODE_WAKEUP")
        except Exception:
            pass
        time.sleep(max(0.0, min(float(delay_s), 15.0)))
        shot = self.capture_screenshot(host, port)
        if preview_check.is_black(shot["path"]):
            raise Exception(
                "TV chụp ra ảnh đen (TV đang ở chế độ chờ, hoặc màn hình bị chặn chụp). "
                "Giữ ảnh mẫu của theme, không ghi đè."
            )
        from PIL import Image
        out = self.theme_shot_path(theme_id, host, port)
        with Image.open(shot["path"]) as im:
            im.convert("RGB").resize((1280, 720), Image.LANCZOS).save(out, quality=82, optimize=True)
        with open(out, "rb") as f:
            jpg = base64.b64encode(f.read()).decode("ascii")
        return {"path": out, "full_path": shot["path"], "jpg_b64": jpg}

    def open_screenshots_folder(self):
        d = self.screenshots_dir()
        if sys.platform.startswith("win"):
            os.startfile(d)  # noqa: S606 - a folder the app owns
        elif sys.platform == "darwin":
            subprocess.Popen(["open", d])
        else:
            subprocess.Popen(["xdg-open", d])
        return {"path": d}

    def list_apps(self, host, port=5555):
        if self._device_platform(host) == "lg_webos":
            rows = self._get_webos(host, self._lg_port(host, port)).list_apps()
            return {"apps": [{"package": a["id"], "name": a.get("title") or a["id"],
                     "type": "user", "enabled": True, "can_disable": False,
                     "protected": True, "is_home": False, "icon": a.get("icon"),
                     "disable_reason": "LG webOS chỉ hỗ trợ mở ứng dụng."} for a in rows],
                    "current_home": "", "platform": "lg_webos"}
        with self._dev_op_lock(host, port):
            try:
                pm = self._get_pm(host, port)
                pkgs = pm.get_all_packages()
                current_home = self._cached_current_home(pm, host, port)
            except Exception as e:
                if self._adb_timeout_error(e):
                    self._drop_dev(host, port)
                raise Exception(
                    f"ADB timeout hoặc TV không phản hồi ({host}:{port}). "
                    f"Kiểm tra TV bật, cùng Wi‑Fi, và đã Allow debugging. Chi tiết: {e}"
                ) from e
        # Mark types
        result = []
        user_set = set(pkgs.get("user", []))
        disabled_set = set(pkgs.get("disabled", []))
        for p in pkgs.get("all", []):
            ptype = "system"
            if p in disabled_set:
                ptype = "disabled"
            elif p in user_set:
                ptype = "user"
            allowed, reason = safety.can_disable(p, current_home=current_home, is_only_home=False)
            result.append({
                "package": p,
                "type": ptype,
                "enabled": p not in disabled_set,
                "is_home": p == current_home,
                "protected": safety.is_protected(p),
                "can_disable": allowed,
                "disable_reason": reason,
                "version": None,
                "version_code": None,
            })
        result.sort(key=lambda x: (x["type"] != "user", x["type"] != "disabled", x["package"]))
        # Tag packages worth a look in the main list too (suggestion only; nothing is disabled here).
        try:
            with self._dev_op_lock(host, port):
                ident = self._cached_identity(self._get_pm(host, port), host, port)
            rows, _profile, _quality = self._suggest_for(result, ident)
            tags = {r["package"]: r for r in rows if r.get("tier") in ("recommend", "review")}
            for app in result:
                r = tags.get(app["package"])
                if r:
                    app["suggest"] = {
                        "tier": r["tier"],
                        "reason": r.get("reason") or "",
                        "source": r.get("source") or "local",
                        "match": r.get("profile_match") or "",
                    }
        except Exception:
            pass  # tags are optional; never fail the package list because of them
        return {"apps": result, "current_home": current_home}

    def _cached_identity(self, pm: PackageManager, host, port) -> dict:
        """Device properties are fixed per TV: read them once per host:port."""
        key = f"{host}:{int(port)}"
        ident = self._identity_cache.get(key)
        if not ident or not any(ident.values()):
            ident = self._device_identity(pm)
            if any(ident.values()):
                self._identity_cache[key] = ident
        return ident

    def _suggest_for(self, apps: list, ident: dict):
        """Run the local engine (plus a matched Gathin profile) -> (rows, profile, quality)."""
        manufacturer = ident.get("manufacturer") or ident.get("brand") or ""
        profile, quality = self._device_profiles.match(ident)
        if profile:
            rows = self._clean_engine.analyze(
                apps,
                manufacturer=manufacturer,
                profile_notes=self._device_profiles.package_notes(profile),
                profile_label=profile.get("tv") or profile.get("id") or "",
                profile_quality=quality,
            )
        else:
            rows = self._clean_engine.analyze(apps, manufacturer=manufacturer)
        return rows, profile, quality

    def _device_identity(self, pm: PackageManager) -> dict:
        """Build properties used to match a Gathin per-model profile."""
        keys = {
            "manufacturer": "ro.product.manufacturer",
            "brand": "ro.product.brand",
            "model": "ro.product.model",
            "device": "ro.product.device",
            "name": "ro.product.name",
        }
        out = {k: "" for k in keys}
        try:
            raw = pm._shell(
                "; ".join(f"echo {k}=$(getprop {v})" for k, v in keys.items()),
                timeout=adb_client.SHELL_DEFAULT_TIMEOUT,
            ) or ""
            for line in raw.splitlines():
                k, _, v = line.partition("=")
                if k.strip() in out:
                    out[k.strip()] = v.strip()
        except Exception:
            pass
        return out

    def _device_props(self, pm: PackageManager) -> tuple:
        try:
            prop_timeout = adb_client.SHELL_DEFAULT_TIMEOUT
            brand = (
                pm._shell("getprop ro.product.manufacturer", timeout=prop_timeout) or ""
            ).strip()
            model = (
                pm._shell("getprop ro.product.model", timeout=prop_timeout) or ""
            ).strip()
            return brand, model
        except Exception:
            return "", ""

    def get_app_settings(self):
        return settings_store.public_settings()

    def save_app_settings(
        self,
        openai_api_key=None,
        openai_model=None,
        openai_base_url=None,
    ):
        if openai_api_key is not None:
            stripped = (openai_api_key or "").strip()
            if stripped:
                settings_store.set_openai_api_key(stripped)
            # None / chuỗi rỗng: giữ key đã lưu (tránh xóa khi chỉ cập nhật URL/model)
        if openai_model is not None:
            settings_store.set_openai_model(str(openai_model).strip() or None)
        if openai_base_url is not None:
            settings_store.set_openai_base_url(str(openai_base_url).strip() or None)
        return settings_store.public_settings()

    def test_openai_connection(self, openai_api_key=None, openai_base_url=None):
        typed = (openai_api_key or "").strip() if openai_api_key is not None else ""
        key = typed or settings_store.get_openai_api_key()
        if not key:
            return {
                "ok": False,
                "error": "Chưa có API key — dán vào ô key hoặc bấm Lưu Key trước.",
                "models": [],
            }
        base = (openai_base_url or "").strip() if openai_base_url else ""
        base = base or settings_store.get_openai_base_url()
        try:
            models = ai_clean.fetch_models(api_key=key, base_url=base, max_models=0)
            normalized = ai_clean.normalize_base_url(base)
            return {
                "ok": True,
                "models": models,
                "base_url": normalized,
                "error": None,
                "models_total": len(models),
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "models": []}

    def smart_clean_suggest(
        self,
        host,
        port=5555,
        use_ai=False,
        openai_model=None,
        openai_base_url=None,
    ):
        listed = self.list_apps(host, port)
        apps = listed.get("apps") or []
        pm = self._get_pm(host, port)
        manufacturer, model = self._device_props(pm)
        identity = self._cached_identity(pm, host, port)
        suggestions, profile, quality = self._suggest_for(apps, identity)
        profile_info = None
        if profile:
            matched = sum(1 for s in suggestions if s.get("source") == "profile")
            profile_info = self._device_profiles.describe(profile, quality, matched)
        ai_error = None
        if use_ai:
            key = settings_store.get_openai_api_key()
            if not key:
                ai_error = "Chưa lưu OpenAI API key — dùng gợi ý nhanh (offline) hoặc dán key bên dưới."
            else:
                llm_model = ""
                try:
                    apps_by_pkg = {a.get("package"): a for a in apps if a.get("package")}
                    current_home = listed.get("current_home") or ""
                    launcher_pkgs: set = set()
                    try:
                        launcher_pkgs = pm.get_launcher_package_set()
                    except Exception:
                        pass
                    package_items = []
                    for s in suggestions:
                        if not (
                            s.get("enabled")
                            and s.get("can_disable")
                            and s.get("tier") != "blocked"
                        ):
                            continue
                        pkg = s["package"]
                        app = apps_by_pkg.get(pkg) or {}
                        package_items.append(
                            {
                                "package": pkg,
                                "label": app.get("label") or "",
                                "is_system": app.get("type") == "system",
                                "has_launcher_icon": bool(
                                    app.get("is_home") or pkg in launcher_pkgs
                                ),
                            }
                        )
                    pub = settings_store.public_settings()
                    base_url = (openai_base_url or "").strip() or pub.get("openai_base_url")
                    llm_model = settings_store.resolve_openai_model(
                        explicit=openai_model,
                        base_url=base_url,
                    )
                    if not llm_model:
                        raise ValueError(
                            "Chưa chọn model — bấm Test Ping, tìm model trong ô Model và chọn (hoặc Lưu Key)."
                        )
                    ai_rows = ai_clean.suggest_with_openai(
                        api_key=key,
                        model=llm_model,
                        manufacturer=manufacturer,
                        model_name=model,
                        package_items=package_items,
                        current_home_package=current_home,
                        base_url=base_url,
                    )
                    suggestions = self._clean_engine.merge_ai(suggestions, ai_rows)
                except Exception as e:
                    msg = str(e)
                    model_hint = (llm_model or "").strip()
                    if "HTTP 401" in msg and model_hint and "gpt-4o" in model_hint.lower():
                        msg += " — proxy local thường không hỗ trợ tên OpenAI mặc định; chọn model sau Test Ping và Lưu Key."
                    elif "HTTP 401" in msg and model_hint:
                        msg += f" — kiểm tra API key và model «{model_hint}» trên Base URL đã cấu hình."
                    ai_error = msg
        counts = {"recommend": 0, "review": 0, "skip": 0, "blocked": 0}
        for s in suggestions:
            counts[s.get("tier") or "skip"] = counts.get(s.get("tier") or "skip", 0) + 1
        return {
            "suggestions": suggestions,
            "manufacturer": manufacturer,
            "model": model,
            "current_home": listed.get("current_home"),
            "counts": counts,
            "profile": profile_info,
            "ai_error": ai_error,
        }

    def smart_clean_apply(self, host, port=5555, packages=None):
        self._require_android(host)
        pkgs = [p for p in (packages or []) if p]
        if not pkgs:
            raise Exception("Không có package nào để vô hiệu hóa")
        results = []
        for pkg in pkgs:
            try:
                self.app_action(host, port, "disable", pkg)
                results.append({"package": pkg, "ok": True})
            except Exception as e:
                results.append({"package": pkg, "ok": False, "error": str(e)})
        ok = sum(1 for r in results if r.get("ok"))
        return {"results": results, "ok_count": ok, "fail_count": len(results) - ok}

    def get_apps_info(self, host, port=5555, packages=None, limit=80):
        if not packages:
            return {}
        pkgs = [p for p in packages if p]
        cap = max(1, min(int(limit or 80), 120))
        with self._dev_op_lock(host, port):
            try:
                pm = self._get_pm(host, port)
                return pm.get_packages_info(pkgs, limit=cap)
            except Exception as e:
                if self._adb_timeout_error(e):
                    self._drop_dev(host, port)
                raise Exception(f"Không đọc được thông tin app: {e}") from e

    def app_action(self, host, port=5555, action="", package=""):
        if self._device_platform(host) == "lg_webos":
            if action != "open":
                raise Exception("LG webOS chỉ hỗ trợ mở ứng dụng.")
            self._get_webos(host, self._lg_port(host, port)).launch_app(package)
            return {"ok": True}
        with self._dev_op_lock(host, port):
            try:
                pm = self._get_pm(host, port)
                if action == "open":
                    pm.open_app(package)
                    return {"ok": True}
                elif action == "force_stop":
                    pm.force_stop(package)
                    return {"ok": True}
                elif action == "app_info":
                    pm.open_app_info(package)
                    return {"ok": True}
                elif action == "enable":
                    pm.enable(package)
                    return {"ok": True, "enabled": True}
                elif action == "uninstall" and package in LauncherDetector.PACKAGES:
                    # Gỡ launcher đang làm Home: bật lại launcher gốc TRƯỚC để TV không mất màn hình chính.
                    tm = ThemeManager(pm.device)
                    stock = tm.enable_stock_launcher()
                    if not stock.get("ok"):
                        raise Exception("Không bật lại được launcher gốc nên không gỡ SmartTV Home (tránh TV mất Home).")
                    pm.uninstall(package)
                    return {"ok": True, "uninstalled": True, "stock_restored": True}
                elif action == "uninstall":
                    current_home = self._cached_current_home(pm, host, port)
                    allowed, reason = safety.can_disable(package, current_home=current_home)
                    if not allowed:
                        raise Exception(reason)
                    if package not in set(pm.list_packages("-3")):
                        raise Exception("Chỉ gỡ cài đặt app người dùng; app hệ thống hãy dùng Vô hiệu hóa")
                    pm.uninstall(package)
                    return {"ok": True, "uninstalled": True}
                elif action == "disable":
                    current_home = self._cached_current_home(pm, host, port)
                    allowed, reason = safety.can_disable(package, current_home=current_home)
                    if not allowed:
                        raise Exception(reason)
                    pm.disable_user(package)
                    return {"ok": True, "enabled": False}
                raise Exception("Hành động không hợp lệ")
            except Exception as e:
                if self._adb_timeout_error(e):
                    self._drop_dev(host, port)
                raise

    def analyze_apk(self, filename="", data_base64="", host=None, port=5555):
        if host:
            self._require_android(host)
        if not filename or not data_base64:
            raise Exception("Thiếu file APK")
        try:
            raw = base64.b64decode(data_base64)
        except Exception:
            raise Exception("Dữ liệu file không hợp lệ")
        tmpdir = tempfile.gettempdir()
        safe_name = os.path.basename(filename)
        if not safe_name.lower().endswith(".apk"):
            raise Exception("Chỉ hỗ trợ file .apk")
        path = os.path.join(tmpdir, f"smarttvmanager_{os.getpid()}_{safe_name}")
        with open(path, "wb") as f:
            f.write(raw)
        try:
            analyzer = ApkAnalyzer()
            info = analyzer.analyze(path)
            info["_tmp_path"] = path
            # Try to compare with installed app
            if host and info.get("package"):
                try:
                    pm = self._get_pm(host, port)
                    out = pm.device.shell(f"dumpsys package {info['package']} 2>&1 | grep -E 'versionName|versionCode|signatures|SHA256'")
                    installed = {}
                    for line in out.splitlines():
                        if "versionName" in line and "versionName" not in installed:
                            import re
                            m = re.search(r"versionName=([^\s]+)", line)
                            if m:
                                installed["version_name"] = m.group(1)
                        if "versionCode" in line and "version_code" not in installed:
                            import re
                            m = re.search(r"versionCode=(\d+)", line)
                            if m:
                                installed["version_code"] = m.group(1)
                    if installed:
                        info["installed"] = installed
                        apk_vc = int(info.get("version_code") or 0)
                        ins_vc = int(installed.get("version_code") or 0)
                        if apk_vc < ins_vc:
                            info["warning_downgrade"] = True
                        elif apk_vc == ins_vc:
                            info["warning_same"] = True
                        elif apk_vc > ins_vc:
                            info["warning_upgrade"] = True
                except Exception:
                    pass
            return info
        except Exception as e:
            try:
                os.unlink(path)
            except Exception:
                pass
            raise e

    def install_apk(
        self,
        host,
        port=5555,
        tmp_path="",
        filename="",
        reinstall=True,
        allow_downgrade=False,
        grant_permissions=False,
    ):
        if not tmp_path or not os.path.exists(tmp_path):
            raise Exception("File tạm không tồn tại hoặc đã hết hạn. Hãy chọn lại file APK.")
        try:
            with self._dev_op_lock(host, port):
                dev = self._get_dev(host, port)
                installer = ApkInstaller(dev)
                try:
                    return installer.install(
                        tmp_path,
                        reinstall=bool(reinstall),
                        allow_downgrade=bool(allow_downgrade),
                        grant_permissions=bool(grant_permissions),
                    )
                except Exception:
                    self._drop_dev(host, port)
                    raise
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def get_gathin_build_prereqs(self):
        return launcher_builder.check_prereqs()

    def check_launcher_update(self, host, port=5555):
        """Compare the newest published SmartTV Home APK with the one this app last installed on `host`."""
        try:
            latest = launcher_download.latest_sha()
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:200]}
        recorded = settings_store.get_launcher_sha(host)
        return {"ok": True, "latest": latest, "installed": recorded,
                "update_available": bool(latest) and recorded != latest}

    def prefetch_launcher(self):
        """Fetch the newest APK into the cache in the background, so installing it later is instant."""
        def run():
            try:
                launcher_download.download_apk(lambda *_a: None)
            except Exception:
                pass  # offline or release missing: the install flow reports it when the person asks

        threading.Thread(target=run, daemon=True).start()
        return {"started": True}

    def build_and_install_gathin_async(self, host, port=5555, mode="build"):
        """Clone smtv-home, build bằng Gradle rồi cài lên TV. Tiến trình đọc bằng apply_gathin_theme_job."""
        self._require_android(host)
        job_id = uuid.uuid4().hex
        job = {"id": job_id, "status": "running", "steps": [], "error": None, "result": None,
               "log_path": THEME_APPLY_LOG}
        with self._apply_jobs_lock:
            self._apply_jobs[job_id] = job

        def step(msg, detail=""):
            job["steps"].append({"t": time.time(), "msg": msg, "detail": detail or ""})
            self._append_theme_apply_log(job_id, msg, detail or "")

        def run():
            try:
                tv_sdk = None
                if mode not in ("download", "resync"):
                    step("build_start", "kiểm tra Git / JDK / Android SDK")
                try:
                    with self._dev_op_lock(host, port):
                        out = self._get_pm(host, port)._shell("getprop ro.build.version.sdk")
                    tv_sdk = int(re.sub(r"\D", "", out or "") or 0) or None
                except Exception:
                    tv_sdk = None
                if mode in ("download", "resync"):
                    # resync: fetch the published APK again even when the cached copy looks current, then reinstall it.
                    apk = launcher_download.download_apk(step, force=(mode == "resync"))
                    info = ApkAnalyzer().analyze(apk)
                    if info.get("package") not in LauncherDetector.PACKAGES:
                        raise Exception(f"APK tải về không phải SmartTV Home ({info.get('package')})")
                    apk_sha = launcher_download.cached_sha()
                    step("install_start", "đẩy APK lên TV")
                else:
                    apk = launcher_builder.build_apk(step, tv_sdk=tv_sdk)
                    step("install_start", "đẩy APK vừa build lên TV")
                migrated = False
                with self._dev_op_lock(host, port):
                    dev = self._get_dev(host, port)
                    try:
                        try:
                            res = ApkInstaller(dev).install(
                                apk, progress_cb=lambda m: step("install", m),
                                reinstall=True, allow_downgrade=False, grant_permissions=True,
                            )
                        except Exception as exc:
                            if "Chữ ký khác" not in str(exc):
                                raise
                            # The installed build is signed with another key (CI builds without a stored keystore get a
                            # fresh one). Android refuses the update, so replace it: give Home back to the stock launcher
                            # first (a TV with no Home at all is the one thing this must never cause), then reinstall.
                            migrated = True
                            step("signature_mismatch", "bản cũ ký bằng khóa khác: bật lại launcher gốc, gỡ bản cũ, cài lại")
                            tm = ThemeManager(dev)
                            tm.enable_stock_launcher()
                            from core.launcher_detector import LauncherDetector as _LD
                            for pkg in _LD.PACKAGES:
                                out = (tm._shell(f"pm uninstall {pkg} 2>&1") or "").strip()
                                if "Unknown package" not in out and "Success" not in out and "not installed" not in out.lower():
                                    step("uninstall", out[:200])
                            res = ApkInstaller(dev).install(
                                apk, progress_cb=lambda m: step("install", m),
                                reinstall=True, allow_downgrade=False, grant_permissions=True,
                            )
                            # A fresh install has no data folder and its provider never ran: start it once so the
                            # theme push that follows has somewhere to write.
                            step("warm_up", "khởi động launcher mới một lần")
                            try:
                                tm.restart_launcher()
                                time.sleep(3)
                            except Exception as warm_exc:
                                step("warm_up_failed", str(warm_exc)[:200])
                    except Exception:
                        self._drop_dev(host, port)
                        raise
                if res.get("ok") is False:
                    raise Exception(res.get("output") or "pm install không thành công")
                step("install_done", res.get("output") or "Success")
                if mode in ("download", "resync") and apk_sha:
                    settings_store.set_launcher_sha(host, apk_sha)
                if migrated:
                    # The old install took the theme with it: put the last applied theme back (this also sets Home
                    # and disables the stock launcher again, with the usual Home guard).
                    last = settings_store.get_last_theme(host, port) or settings_store.load().get("last_theme_id")
                    if last:
                        step("reapply_theme", str(last))
                        try:
                            reapply = self._apply_gathin_theme_impl(host, port, last, job_id, job["steps"])
                            step("reapply_done", "đã áp lại theme" if reapply else "")
                        except Exception as re_exc:
                            step("reapply_failed", str(re_exc)[:300])
                            job["warning"] = f"Đã cài lại launcher nhưng chưa áp lại được theme: {re_exc}"
                    else:
                        step("reapply_skipped", "chưa có theme nào từng áp: chọn theme rồi bấm Áp dụng")
                job["result"] = res
                job["status"] = "done"
            except Exception as exc:
                step("error", str(exc)[:300])
                job["error"] = str(exc)
                job["status"] = "failed"

        threading.Thread(target=run, daemon=True).start()
        return {"job_id": job_id}

    def install_apk_async(self, host, port=5555, tmp_path="", filename="",
                          reinstall=True, allow_downgrade=False, grant_permissions=True):
        """Cài APK nền, có tiến trình thật (đẩy file / pm install). Đọc bằng apply_gathin_theme_job."""
        self._require_android(host)
        if not tmp_path or not os.path.exists(tmp_path):
            raise Exception("File tạm không tồn tại hoặc đã hết hạn. Hãy chọn lại file APK.")
        job_id = uuid.uuid4().hex
        job = {"id": job_id, "status": "running", "steps": [], "error": None, "result": None,
               "log_path": THEME_APPLY_LOG}
        with self._apply_jobs_lock:
            self._apply_jobs[job_id] = job

        def step(msg, detail=""):
            job["steps"].append({"t": time.time(), "msg": msg, "detail": detail or ""})

        def run():
            try:
                step("install_start", filename or os.path.basename(tmp_path))
                with self._dev_op_lock(host, port):
                    dev = self._get_dev(host, port)
                    try:
                        res = ApkInstaller(dev).install(
                            tmp_path,
                            progress_cb=lambda m: step("install", m),
                            reinstall=bool(reinstall),
                            allow_downgrade=bool(allow_downgrade),
                            grant_permissions=bool(grant_permissions),
                        )
                    except Exception:
                        self._drop_dev(host, port)
                        raise
                if res.get("ok") is False:
                    raise Exception(res.get("output") or "pm install không thành công")
                step("install_done", (res.get("output") or "Success"))
                job["result"] = res
                job["status"] = "done"
            except Exception as exc:
                job["error"] = str(exc)
                job["status"] = "failed"
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        threading.Thread(target=run, daemon=True).start()
        return {"job_id": job_id}

    def detect_launcher(self, host, port=5555):
        # Phải giữ lock: adb-shell không thread-safe, 2 lệnh song song trên 1 kết nối sẽ làm hỏng stream.
        with self._dev_op_lock(host, port):
            try:
                dev = self._get_dev(host, port)
                det = LauncherDetector(dev)
                info = det.detect_gathin()
                disc = det.discover_config() if info.get("installed") is not None else {"candidates": []}
            except Exception as e:
                if self._adb_timeout_error(e):
                    self._drop_dev(host, port)
                raise self._adb_shell_error(host, port, e) from e
        return {"info": info, "discovery": disc}

    def _backup_root(self, host, port):
        root = os.path.join(store.KEY_DIR, "backups", f"{host}_{int(port)}")
        os.makedirs(root, exist_ok=True)
        return root

    def _launcher_op(self, host, port, fn):
        """Run fn(ThemeManager) under the per-device lock with friendly timeout errors."""
        with self._dev_op_lock(host, port):
            try:
                dev = self._get_dev(host, port)
                return fn(ThemeManager(dev))
            except Exception as e:
                if self._adb_timeout_error(e):
                    self._drop_dev(host, port)
                raise self._adb_shell_error(host, port, e) from e

    def backup_launcher(self, host, port=5555):
        return self._launcher_op(
            host, port, lambda tm: tm.backup_config(self._backup_root(host, port))
        )

    def list_launcher_backups(self, host, port=5555):
        root = self._backup_root(host, port)
        items = []
        for name in sorted(os.listdir(root), reverse=True):
            path = os.path.join(root, name)
            manifest = os.path.join(path, "manifest.json")
            if not os.path.isfile(manifest):
                continue
            try:
                with open(manifest, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            items.append({
                "id": name,
                "time": data.get("time", name),
                "had_config": data.get("had_config", False),
                "wallpapers": len(data.get("wallpapers") or []),
            })
        return items

    def restore_launcher_backup(self, host, port=5555, backup_id=""):
        if not backup_id:
            raise Exception("Chưa chọn bản sao lưu")
        root = self._backup_root(host, port)
        path = os.path.join(root, os.path.basename(backup_id))
        if not os.path.isdir(path):
            raise Exception("Không tìm thấy bản sao lưu")
        return self._launcher_op(host, port, lambda tm: tm.restore_backup(path))

    def reset_launcher(self, host, port=5555):
        def run(tm):
            backup = tm.backup_config(self._backup_root(host, port))
            result = tm.reset()
            result["backup"] = backup
            return result

        return self._launcher_op(host, port, run)

    def restart_launcher(self, host, port=5555):
        return self._launcher_op(host, port, lambda tm: {"ok": tm.restart_launcher()})

    def current_launcher_theme(self, host, port=5555, include_wallpaper=True):
        """Overlay state in one ADB round trip. Raises when the TV is unreachable.

        The wallpaper preview (up to 1.5 MB) is slow: the UI asks for it separately via
        launcher_wallpaper_preview(); include_wallpaper=True keeps the old one-call behaviour.
        An LG TV has no overlay to read: it reports the locally recorded deployment only.
        """
        if self._device_platform(host) == "lg_webos":
            tid = settings_store.get_last_theme(host, self._lg_port(host, port))
            return {"config": {}, "last_theme_id": tid, "has_overlay": bool(tid),
                    "wallpaper_b64": None, "snapshot": True, "verified_on_tv": False}

        def run(tm):
            state = tm.read_state()
            wallpaper_b64 = tm.read_wallpaper_preview_b64() if include_wallpaper else None
            state["wallpaper_b64"] = wallpaper_b64
            state["last_theme_id"] = settings_store.get_last_theme(host, port)
            state["has_overlay"] = (
                bool(state["config"]) or bool(state["revision"]) or bool(wallpaper_b64)
            )
            return state

        return self._launcher_op(host, port, run)

    def set_default_home(self, host, port=5555):
        """Make the installed launcher the default Home (what the remote's HOME key opens) and verify."""
        self._require_android(host)

        def run(tm):
            pkg = tm.pkg
            attempts = [
                f"cmd package set-home-activity {pkg}/com.gathin.tvhome.MainActivity",
                f"cmd role add-role-holder --user 0 android.app.role.HOME {pkg}",
            ]
            log = []
            state = None
            for cmd in attempts:
                try:
                    out = (tm._shell(f"{cmd} 2>&1") or "").strip()
                except Exception as e:
                    out = f"lỗi: {e}"
                log.append({"cmd": cmd, "output": out})
                state = tm.read_state()
                if state["launcher"]["is_default_home"]:
                    return {"ok": True, "log": log, "launcher": state["launcher"], "resumed": None}
            # Last resort: press HOME and see which app comes to the foreground. NB: this is an
            # injected key, so it does NOT go through HomeKeyService (physical remote may differ).
            resumed = None
            try:
                out = tm._shell(
                    "input keyevent 3; sleep 2; "
                    "dumpsys activity activities 2>&1 | grep -E 'ResumedActivity' | head -3",
                    timeout_s=30.0,
                )
                m = re.search(r"([a-zA-Z][\w.]*)/", out or "")
                resumed = m.group(1) if m else None
            except Exception:
                pass
            state = tm.read_state()
            return {
                "ok": bool(state["launcher"]["is_default_home"] or resumed == pkg),
                "log": log,
                "launcher": state["launcher"],
                "resumed": resumed,
            }

        return self._launcher_op(host, port, run)

    def set_stock_launcher(self, host, port=5555, disable=True):
        """Disable (HOME → Gathin) or re-enable (original state) the stock Google TV launcher."""
        self._require_android(host)
        def run(tm):
            return tm.disable_stock_launcher() if disable else tm.enable_stock_launcher()

        return self._launcher_op(host, port, run)

    def get_auto_stock_launcher(self):
        return bool(settings_store.load().get("auto_disable_stock_launcher", True))

    def set_auto_stock_launcher(self, enabled=True):
        data = settings_store.load()
        data["auto_disable_stock_launcher"] = bool(enabled)
        settings_store.save(data)
        return bool(enabled)

    def diagnose_home(self, host, port=5555):
        """Read-only dump to see how HOME is routed on this TV (copyable in the UI)."""
        pkg = "|".join(LauncherDetector.PACKAGES)
        probes = [
            ("HOME candidates", "cmd package query-activities --brief -a android.intent.action.MAIN -c android.intent.category.HOME 2>&1"),
            ("resolve HOME", "cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME 2>&1"),
            ("enabled_accessibility_services", "settings get secure enabled_accessibility_services 2>&1"),
            ("accessibility_enabled", "settings get secure accessibility_enabled 2>&1"),
            ("gathin accessibility services", f"cmd package query-services --brief -a android.accessibilityservice.AccessibilityService 2>&1 | grep -iE '{pkg}'"),
            ("gathin in dumpsys accessibility", f"dumpsys accessibility 2>&1 | grep -iE '{pkg}|requestFilterKeyEvents|FLAG_REQUEST_FILTER' | head -15"),
            ("sdk / brand", "getprop ro.build.version.sdk; getprop ro.product.brand; getprop ro.product.model"),
            ("launcher crashes (logcat -b crash)", "logcat -d -b crash 2>&1 | tail -60"),
            ("launcher log lines", f"logcat -d 2>&1 | grep -E 'AndroidRuntime|FATAL|ANR in|{pkg}' | tail -60"),
            ("installed launchers", "pm list packages --show-versioncode 2>&1 | grep -E 'smtv_manager|gathin'"),
            ("old CleanYourTV files (com.gathin.tvhome)", "ls -la /sdcard/Android/data/com.gathin.tvhome/files 2>&1 | head -20; cat /sdcard/Android/data/com.gathin.tvhome/files/config.json 2>&1 | head -40"),
            ("launcher package", f"dumpsys package {LauncherDetector.SMTV_PKG} 2>&1 | grep -E 'versionName|versionCode|lastUpdateTime|firstInstallTime|enabled=' | head -8"),
            ("launcher build has widget switches (count of show_lunar_header in the APK)", f"unzip -p $(pm path {LauncherDetector.SMTV_PKG} | head -1 | cut -d: -f2) classes.dex 2>&1 | grep -c show_lunar_header"),
            ("launcher startup log (SmtvHome)", "logcat -d -s SmtvHome:I 2>&1 | tail -10"),
            ("focused app", "dumpsys activity activities 2>&1 | grep -E 'mFocusedApp|ResumedActivity' | head -4"),
            ("disabled launchers", "pm list packages -d 2>&1 | grep -i launcher"),
            ("theme files on the TV", f"ls -la /sdcard/Android/data/{LauncherDetector.SMTV_PKG}/files 2>&1 | head -20; cat /sdcard/Android/data/{LauncherDetector.SMTV_PKG}/files/config.json 2>&1 | head -120"),
        ]

        def run(tm):
            lines = []
            for title, cmd in probes:
                try:
                    out = (tm._shell(cmd, timeout_s=30.0) or "").strip()
                except Exception as e:
                    out = f"(lỗi: {e})"
                lines.append(f"### {title}\n{out or '(trống)'}\n")
            return {"text": "\n".join(lines)}

        return self._launcher_op(host, port, run)

    def launcher_wallpaper_preview(self, host, port=5555):
        """Best-effort wallpaper preview pulled from the TV (None when absent)."""
        return {
            "wallpaper_b64": self._launcher_op(
                host, port, lambda tm: tm.read_wallpaper_preview_b64()
            )
        }

    def list_gathin_themes(self, host=None, port=5555):
        """The theme library. A real-TV capture is only offered for the device it was taken on."""
        themes = self._themes.list_themes()
        result = []
        for t in themes:
            screenshot_b64 = None
            live = self.theme_shot_path(t["id"], host, port) if host else ""
            has_live = bool(live) and os.path.isfile(live)
            if has_live and preview_check.is_black(live):
                # A black frame (TV asleep or screen protected) saved by an earlier Apply is no preview: drop it.
                try:
                    os.remove(live)
                except OSError:
                    pass
                has_live = False
            # A capture taken from the real TV after applying the theme beats the bundled preview.
            shot_path = live if has_live else t.get("screenshot")
            if shot_path and os.path.exists(shot_path):
                try:
                    with open(shot_path, "rb") as f:
                        screenshot_b64 = base64.b64encode(f.read()).decode("ascii")
                except Exception:
                    pass
            check = ThemeManager.validate_theme(t)
            result.append({
                "id": t["id"],
                "name": t["name"],
                "has_config": t["has_config"],
                "has_wallpaper": bool(t.get("wallpaper")),
                "wallpapers_count": len(t.get("wallpapers") or []),
                "screenshot": screenshot_b64,
                "screenshot_live": has_live,
                "config": t.get("config") or {},
                "widgets": theme_widgets.resolve(t.get("config"), self._saved_theme_widgets(t["id"])),
                "valid": check["ok"],
                "errors": check["errors"],
                "warnings": check["warnings"],
            })
        return result

    @staticmethod
    def _saved_theme_widgets(theme_id):
        saved = (settings_store.load().get("theme_widgets") or {}).get(str(theme_id))
        return saved if isinstance(saved, dict) else {}

    def get_theme_widgets(self, theme_id=""):
        """Which dashboard widgets of a theme are on (saved choice, else the theme's own default)."""
        theme = next((t for t in self._themes.list_themes() if t["id"] == theme_id), None)
        if not theme:
            raise Exception("Không tìm thấy theme")
        return theme_widgets.resolve(theme.get("config"), self._saved_theme_widgets(theme_id))

    def set_theme_widgets(self, theme_id="", values=None):
        """Save widget switches for a theme; they are written to the TV the next time the theme is applied."""
        theme = next((t for t in self._themes.list_themes() if t["id"] == theme_id), None)
        if not theme:
            raise Exception("Không tìm thấy theme")
        data = settings_store.load()
        all_saved = data.get("theme_widgets") if isinstance(data.get("theme_widgets"), dict) else {}
        merged = {**self._saved_theme_widgets(theme_id), **theme_widgets.clean(theme.get("config"), values)}
        all_saved[str(theme_id)] = merged
        data["theme_widgets"] = all_saved
        settings_store.save(data)
        return theme_widgets.resolve(theme.get("config"), merged)

    def _home_widgets_tv_bundle(self):
        """Launcher patch + sidecar when Widget Home is enabled in settings."""
        cfg = settings_store.get_home_widgets()
        if not cfg.get("enabled"):
            return None, None, None
        prev = home_widgets.preview(cfg)  # wallpaper mode: no ticker text, name only
        board_lines = prev.get("board_lines") or []
        patch = home_widgets.launcher_config_patch(cfg, board_lines=board_lines)
        sidecar = home_widgets.board_payload(cfg, board_lines=board_lines)
        return patch, sidecar, prev

    # Remote buttons of this TCL set that send keycodes Gathin does not know (captured with logcat):
    # Settings = 4077, TV = 4001 → Live TV. Verified on the TV; extendable in settings.json
    # under "remote_keys": {"settings_key_keycodes": [...], "app_keys": [...]}.
    DEFAULT_REMOTE_KEYS = {
        "settings_key_keycodes": [4077],
        "app_keys": [
            "4001:com.tcl.tv",  # TV
            "4062:com.netflix.ninja",
            "4065:com.google.android.youtube.tv",
            "4099:com.amazon.amazonvideo.livingroom",
            "4057:com.tcl.ui_mediaCenter",  # Media
            # 4020 (TCL Channel) is NOT mapped: the system starts com.tcl.partnercustomizer.tkey itself.
        ],
    }

    # Chromecast with Google TV remote (captured with getevent): YouTube = usage 0x000c0077 →
    # BUTTON_3 (190), Netflix = usage 0x000c0078 → BUTTON_4 (191). Gathin has no default for them.
    CHROMECAST_REMOTE_KEYS = {
        "app_keys": [
            "190:com.google.android.youtube.tv",
            "191:com.netflix.ninja",
        ],
    }

    @staticmethod
    def _device_profile(dev):
        """Return "tcl", "chromecast" or "" from the TV's build properties."""
        try:
            raw = adb_client.run_shell(
                dev,
                "getprop ro.product.brand; getprop ro.product.manufacturer; getprop ro.product.model",
            )
        except Exception:
            return ""
        low = (raw or "").lower()
        if "chromecast" in low:
            return "chromecast"
        if "tcl" in low:
            return "tcl"
        return ""

    # Launcher keys the app turns on by default so apps can be rearranged from the remote.
    # Without tile_menu, holding OK on a tile only opens App info; with it, the same gesture
    # offers Move / Remove. A key the theme sets itself always wins.
    LAYOUT_DEFAULTS = {"tile_menu": True}

    def _layout_defaults(self, theme):
        base = {}
        try:
            with open(os.path.join(theme["path"], "config.json"), encoding="utf-8") as f:
                base = json.load(f) or {}
        except Exception:
            pass
        return {k: v for k, v in self.LAYOUT_DEFAULTS.items() if k not in base}

    def _remote_key_overrides(self, theme, profile=""):
        """Config keys that keep the remote's Settings/TV/app buttons working after a theme push.

        Key codes are per remote, so they depend on the TV: TCL codes (4001, 4065...) mean
        nothing on a Chromecast and the other way round. An explicit "remote_keys" in
        settings.json still wins for every TV.
        """
        cfg = settings_store.load().get("remote_keys")
        if isinstance(cfg, dict):
            keys = dict(cfg)
        elif profile == "chromecast":
            keys = {k: list(v) for k, v in self.CHROMECAST_REMOTE_KEYS.items()}
        elif profile == "tcl":
            keys = dict(self.DEFAULT_REMOTE_KEYS)
        else:
            keys = {}
        base = {}
        try:
            with open(os.path.join(theme["path"], "config.json"), encoding="utf-8") as f:
                base = json.load(f) or {}
        except Exception:
            pass
        for k in ("settings_key_keycodes", "app_keys"):
            if k in keys:
                merged = list(base.get(k) or [])
                for v in keys[k]:
                    if v not in merged:
                        merged.append(v)
                keys[k] = merged
        return keys

    def _wants_widget_wallpaper(self, theme=None):
        # A theme with the launcher's own dashboard draws and fetches the cards on the TV: baking them into the
        # wallpaper as well would show every card twice.
        if theme and (theme.get("config") or {}).get("dashboard"):
            return False
        cfg = settings_store.get_home_widgets()
        return home_widgets.wallpaper_mode(cfg)

    @staticmethod
    def _composite_theme_widgets(theme, data, workdir):
        """Copy of `theme` whose wallpaper(s) have the gold/fuel cards drawn on."""
        from core import widget_render

        out = dict(theme)
        bg = None
        try:
            with open(os.path.join(theme["path"], "config.json"), encoding="utf-8") as f:
                bg = (json.load(f) or {}).get("background_color")
        except Exception:
            pass
        wp = theme.get("wallpaper")
        has_collection = any(
            str(p).lower().endswith((".jpg", ".jpeg", ".png"))
            for p in theme.get("wallpapers") or []
        )
        if wp and os.path.exists(wp) or not has_collection:
            dst = os.path.join(workdir, "wallpaper.jpg")
            widget_render.render_to_file(wp if wp and os.path.exists(wp) else None, data, dst, bg_color=bg)
            out["wallpaper"] = dst
        if has_collection:
            subdir = os.path.join(workdir, "wallpapers")
            os.makedirs(subdir, exist_ok=True)
            new_list = []
            for p in theme.get("wallpapers") or []:
                low = str(p).lower()
                if low.endswith((".jpg", ".jpeg", ".png")) and os.path.exists(p):
                    dst = os.path.join(subdir, os.path.basename(p))
                    img = widget_render.render_widgets(p, data)
                    if low.endswith(".png"):
                        img.save(dst, "PNG", optimize=True)
                    else:
                        img.save(dst, "JPEG", quality=88, optimize=True)
                    new_list.append(dst)
                else:
                    new_list.append(p)
            out["wallpapers"] = new_list
        return out

    def _append_theme_apply_log(self, job_id: str, phase: str, detail: str) -> None:
        os.makedirs(adb_client.KEY_DIR, mode=0o700, exist_ok=True)
        line = (
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{job_id[:8]}] {phase}"
            + (f" | {detail}" if detail else "")
            + "\n"
        )
        try:
            with open(THEME_APPLY_LOG, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    def _apply_gathin_theme_impl(self, host, port, theme_id, job_id, steps):
        def on_step(phase, detail=""):
            entry = {"t": time.time(), "msg": phase, "detail": detail or ""}
            steps.append(entry)
            self._append_theme_apply_log(job_id, phase, detail or "")

        if not theme_id:
            raise Exception("Chưa chọn theme")
        themes = self._themes.list_themes()
        theme = next((t for t in themes if t["id"] == theme_id), None)
        if not theme:
            raise Exception("Không tìm thấy theme")

        on_step("start", f"{theme.get('name') or theme_id} → {host}:{port}")
        widget_tmp = None
        widget_skip = None
        if self._wants_widget_wallpaper(theme):
            try:
                on_step("widgets_fetch", "lấy dữ liệu thời tiết, lịch âm, giá cả")
                wdata = home_widgets.widgets_data(settings_store.get_home_widgets())
                if any(wdata.get(k) for k in ("gold", "fuel", "weather", "lunar", "fx")):
                    widget_tmp = tempfile.mkdtemp(prefix="stv-widgets-")
                    on_step("widgets_render", "vẽ widget vào wallpaper")
                    theme = self._composite_theme_widgets(theme, wdata, widget_tmp)
                else:
                    widget_skip = "; ".join((wdata.get("errors") or {}).values()) or "không có dữ liệu"
                    on_step("widgets_skip", widget_skip)
            except Exception as exc:
                widget_skip = str(exc)
                on_step("widgets_error", widget_skip)
        try:
            res = self._apply_gathin_theme_locked(host, port, theme, theme_id, on_step, steps, bool(widget_tmp))
            res["widgets_wallpaper"] = bool(widget_tmp)
            res["widgets_skipped"] = widget_skip
            return res
        finally:
            if widget_tmp:
                shutil.rmtree(widget_tmp, ignore_errors=True)

    def _apply_gathin_theme_locked(self, host, port, theme, theme_id, on_step, steps, widget_drawn=False):
        with self._dev_op_lock(host, port):
            self._drop_dev(host, port)
            on_step("adb_connect", f"{host}:{port}")
            dev = adb_client.connect(host, int(port))
            try:
                adb_client.ensure_connected(dev)
                try:
                    gathin_ok = LauncherDetector(dev).installed_launcher() is not None
                except Exception:
                    gathin_ok = None  # không hỏi được thì không đoán là chưa cài
                if gathin_ok is False:
                    on_step("gathin_missing", LauncherDetector.GATHIN_PKG)
                    raise Exception(
                        "GATHIN_NOT_INSTALLED: TV chưa cài launcher SmartTV Home (com.smtv_manager.home). "
                        "Chưa sao lưu hay ghi gì lên TV."
                    )
                tm = ThemeManager(dev, on_step=on_step)
                backup_root = self._backup_root(host, port)
                on_step("backup", "snapshot config (bỏ qua kéo wallpaper để nhanh hơn)")
                backup = tm.backup_config(backup_root, pull_assets=False)
                on_step("backup_done", backup.get("time") or "")
                widget_patch, widget_sidecar, _widget_prev = self._home_widgets_tv_bundle()
                if widget_patch and (theme.get("config") or {}).get("dashboard"):
                    # The dashboard draws its own numbers; the ticker text must not replace the theme's greeting name.
                    widget_patch = {k: v for k, v in widget_patch.items() if k != "greeting_name"}
                profile = self._device_profile(dev)
                on_step("remote_profile", profile or "mặc định")
                widget_patch = {
                    **self._layout_defaults(theme),
                    **self._remote_key_overrides(theme, profile),
                    **(widget_patch or {}),
                    # The owner's widget switches for this theme win over everything else.
                    **theme_widgets.overrides(theme.get("config"), self._saved_theme_widgets(theme_id)),
                } or None
                if widget_drawn:
                    # Themes like Default ship `"wallpaper": false`; the baked image would never show.
                    widget_patch = {**(widget_patch or {}), "wallpaper": True}
                try:
                    result = tm.apply_theme(
                        theme,
                        config_overlay=widget_patch,
                        restart=False,  # một lần khởi động lại duy nhất ở cuối (sau khi tắt launcher gốc)
                    )
                    if widget_sidecar:
                        on_step("widgets_sidecar", "smarttv_widgets.json")
                        try:
                            tm.write_json_sidecar("smarttv_widgets.json", widget_sidecar)
                        except Exception:
                            pass
                    if widget_patch:
                        result["home_widgets"] = True
                    widgets_off = self._verify_theme_widgets(tm, theme, theme_id, on_step)
                    if widgets_off is not None:
                        result["widgets_off"] = widgets_off
                except Exception as exc:
                    on_step("error", str(exc))
                    on_step("restore_backup", backup.get("path") or "")
                    try:
                        adb_client.reconnect(dev, timeout=15.0)
                        tm.restore_backup(backup["path"])
                        on_step("restore_ok", "")
                    except Exception as restore_exc:
                        on_step("restore_failed", str(restore_exc))
                    raise exc
                if self.get_auto_stock_launcher():
                    try:
                        on_step("stock_launcher", "tắt launcher gốc để phím HOME mở Gathin")
                        res_stock = tm.disable_stock_launcher()
                        result["stock_launcher"] = res_stock.get("ok")
                        if res_stock.get("output"):
                            on_step("stock_launcher_output", str(res_stock.get("output"))[:400])
                        if not res_stock.get("ok"):
                            blockers = ", ".join(res_stock.get("home_blockers") or []) or "không rõ"
                            on_step("stock_launcher_rollback", f"HOME không chuyển sang Gathin — đã bật lại launcher gốc. Ứng dụng đang giữ HOME: {blockers}")
                    except Exception as exc:
                        result["stock_launcher"] = False
                        on_step("stock_launcher_error", str(exc))
                on_step("restart_launcher", "khởi động lại Home để nhận theme")
                try:
                    if not tm.restart_launcher():
                        on_step("restart_failed", "restart_launcher trả về False — thử lại")
                        time.sleep(1.5)
                        adb_client.reconnect(dev, timeout=15.0)
                        if not tm.restart_launcher():
                            raise Exception("Không khởi động lại launcher (adb shell timeout hoặc lỗi am/settings)")
                except Exception as exc:
                    on_step("error", str(exc))
                    raise
                try:
                    settings_store.set_last_theme(host, port, theme_id)
                except Exception:
                    pass
                result["backup"] = backup
                result["steps"] = list(steps)
                result["log_path"] = THEME_APPLY_LOG
                return result
            finally:
                try:
                    dev.close()
                except Exception:
                    pass
                self._drop_dev(host, port)

    @staticmethod
    def _verify_theme_widgets(tm, theme, theme_id, on_step):
        """Read config.json back from the TV and compare it with the widget switches that were meant to be written.

        Returns the labels of the widgets that are off, or None for a theme without switches. A mismatch is logged,
        so the apply log shows whether the TV really got the choice.
        """
        config = theme.get("config")
        widgets = theme_widgets.resolve(config, Api._saved_theme_widgets(theme_id))
        if not widgets:
            return None
        off = [w["label"] for w in widgets if not w["enabled"]]
        try:
            on_tv = tm.read_config()
            wrong = [w["key"] for w in widgets if on_tv.get(w["key"], True) is not w["enabled"]]
        except Exception as exc:
            on_step("verify_widgets", f"không đọc lại được config.json: {exc}")
            return off
        on_step("verify_widgets", ("khớp; đang tắt: " + (", ".join(off) or "không có")) if not wrong else "LỆCH: " + ", ".join(wrong))
        return off

    def apply_gathin_theme(self, host, port=5555, theme_id=""):
        self._require_android(host)
        steps = []
        job_id = uuid.uuid4().hex
        return self._apply_gathin_theme_impl(host, port, theme_id, job_id, steps)

    def apply_gathin_theme_async(self, host, port=5555, theme_id=""):
        self._require_android(host)
        job_id = uuid.uuid4().hex
        job = {
            "id": job_id,
            "status": "running",
            "steps": [],
            "error": None,
            "result": None,
            "log_path": THEME_APPLY_LOG,
        }
        with self._apply_jobs_lock:
            self._apply_jobs[job_id] = job

        def run():
            try:
                result = self._apply_gathin_theme_impl(
                    host, port, theme_id, job_id, job["steps"]
                )
                job["result"] = result
                job["status"] = "done"
            except Exception as exc:
                job["error"] = str(exc)
                job["status"] = "failed"

        threading.Thread(target=run, daemon=True).start()
        return {"job_id": job_id, "log_path": THEME_APPLY_LOG}

    def webos_apply_theme_async(self, host, port=3001, theme_id="", developer_device="lgtv"):
        """Build and deploy a snapshot, keeping saved state unchanged on failure."""
        from core import webos_home
        from core.webos_client import WebOsCommandError
        if self._device_platform(host) != "lg_webos":
            raise Exception("Chỉ áp dụng Home webOS cho TV LG.")
        port = self._lg_port(host, port)
        theme = next((t for t in self._themes.list_themes() if t["id"] == theme_id), None)
        if theme is None:
            raise Exception("Theme không tồn tại trong thư viện SmartTV Manager.")
        job_id = uuid.uuid4().hex
        job = {"id": job_id, "status": "running", "steps": [], "error": None, "result": None}
        target = f"{host}:{port}"
        with self._apply_jobs_lock:
            if target in self._webos_deploying:
                raise Exception("Đang cài Home webOS lên TV này. Chờ hoàn tất rồi áp dụng lại.")
            self._webos_deploying.add(target)
            self._apply_jobs[job_id] = job

        def run():
            # No per-device lock here: packaging and the CLI calls take minutes and would block
            # every remote key and app launch on this TV. WebOsClient serializes its own socket.
            try:
                client = self._get_webos(host, port)
                job["steps"].append({"msg": "snapshot", "detail": "Đọc ứng dụng, HDMI và widget hiện tại"})
                cfg = settings_store.get_home_widgets()
                if not cfg.get("enabled"):
                    cfg["weather_city"] = theme["config"].get("weather_city") or cfg.get("weather_city")
                import copy
                snapshot_theme = copy.deepcopy(theme)
                snapshot_theme["config"].update(home_widgets.launcher_config_patch(cfg, board_lines=[]))
                switches = self._saved_theme_widgets(theme_id)
                data = home_widgets.widgets_data(cfg)
                apps = client.list_apps()
                try:
                    inputs = client.list_inputs()
                except WebOsCommandError:
                    # Newer firmware can deny the input list; Home still works without HDMI tiles.
                    inputs = []
                with tempfile.TemporaryDirectory(prefix="smarttv-lg-home-") as tmp:
                    bundle = webos_home.build_bundle(snapshot_theme, os.path.join(tmp, "app"),
                        apps=apps, inputs=inputs, widget_data=data, widget_switches=switches)
                    job["steps"].append({"msg": "install", "detail": "Đóng gói và cài Home webOS qua Developer Mode"})
                    result = webos_home.deploy(bundle, developer_device, expected_host=host)
                if not result.get("ok"):
                    raise Exception("Cài Home webOS chưa thành công.")
                settings_store.set_last_theme(host, port, theme_id)
                result.update(theme_id=theme_id, snapshot=True, widget_errors=data.get("errors", {}))
                job["result"] = result
                job["steps"].append({"msg": "done", "detail": "Đã triển khai snapshot; Apply lại để cập nhật dữ liệu"})
                job["status"] = "done"
            except Exception as exc:
                job["error"] = str(exc)
                job["status"] = "failed"
            finally:
                with self._apply_jobs_lock:
                    self._webos_deploying.discard(target)

        try:
            threading.Thread(target=run, daemon=True).start()
        except BaseException:
            with self._apply_jobs_lock:
                self._webos_deploying.discard(target)
            raise
        return {"job_id": job_id}

    def apply_gathin_theme_job(self, job_id=""):
        with self._apply_jobs_lock:
            job = self._apply_jobs.get(job_id)
            if not job:
                return {"status": "unknown", "steps": [], "error": "Không tìm thấy job"}
            return {
                "status": job["status"],
                "steps": list(job["steps"]),
                "error": job["error"],
                "result": job["result"],
                "log_path": job.get("log_path"),
            }

    def get_home_widgets_settings(self):
        return settings_store.get_home_widgets()

    def save_home_widgets_settings(self, payload=None):
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise ValueError("Cấu hình widget không hợp lệ")
        return settings_store.set_home_widgets(payload)

    def preview_home_widgets(self, payload=None):
        cfg = settings_store.get_home_widgets()
        if isinstance(payload, dict) and payload:
            cfg = home_widgets.normalize_widgets({**cfg, **payload})
        return home_widgets.preview(cfg)

    def preview_widget_wallpaper(self, theme_id="", payload=None):
        """Exactly what the TV will show: the theme's wallpaper with the cards drawn on it."""
        from core import widget_render

        cfg = settings_store.get_home_widgets()
        if isinstance(payload, dict) and payload:
            cfg = home_widgets.normalize_widgets({**cfg, **payload})
        data = home_widgets.widgets_data(cfg)
        tid = theme_id or settings_store.load().get("last_theme_id") or ""
        theme = next((t for t in self._themes.list_themes() if t["id"] == tid), None)
        wp, n_wp, theme_name = None, 0, None
        if theme:
            theme_name = theme.get("name") or tid
            imgs = [p for p in theme.get("wallpapers") or []
                    if str(p).lower().endswith((".jpg", ".jpeg", ".png")) and os.path.exists(p)]
            if theme.get("wallpaper") and os.path.exists(theme["wallpaper"]):
                wp, n_wp = theme["wallpaper"], 1 + len(imgs)
            elif imgs:
                wp, n_wp = imgs[0], len(imgs)
        gold_items = list((data.get("gold") or {}).get("items") or [])
        fuel_items = list((data.get("fuel") or {}).get("items") or [])
        return {
            "image_b64": widget_render.render_preview_b64(wp, data, width=1280),
            "errors": data.get("errors") or {},
            "generated": data.get("generated"),
            "theme_id": tid,
            "theme_name": theme_name,
            "wallpaper_count": n_wp,
            "has_wallpaper": bool(wp),
            "gold_total": len(gold_items),
            "gold_shown": min(len(gold_items), widget_render.GOLD_MAX),
            "fuel_total": len(fuel_items),
            "fuel_shown": min(len(fuel_items), widget_render.FUEL_MAX),
            "cards": [k for k in ("weather", "lunar", "gold", "fuel", "fx") if data.get(k)],
        }

    def apply_home_widgets_to_tv(self, host, port=5555, restart=True, theme_id=""):
        self._require_android(host)
        patch, sidecar, prev = self._home_widgets_tv_bundle()
        if not patch:
            raise Exception("Bật «Widget Home» trước khi áp dụng lên TV")
        last = theme_id or settings_store.get_last_theme(host, port) or settings_store.load().get("last_theme_id")
        if self._wants_widget_wallpaper():
            if not last:
                raise Exception(
                    "Widget được vẽ vào ảnh nền nên cần chọn theme: bấm «Áp dụng» trên một theme "
                    "(hoặc chọn theme đang dùng) rồi thử lại."
                )
            steps = []
            res = self._apply_gathin_theme_impl(host, port, last, uuid.uuid4().hex, steps)
            if not any(st.get("msg") == "widgets_render" for st in steps):
                raise Exception(
                    "Đã áp dụng theme nhưng KHÔNG vẽ được widget vào ảnh nền: "
                    + "; ".join(f"{st.get('msg')}: {st.get('detail')}" for st in steps
                                if str(st.get("msg", "")).startswith("widgets_"))
                )
            return {
                "ok": True,
                "greeting_name": patch.get("greeting_name"),
                "board_lines": (prev or {}).get("board_lines") or [],
                "errors": prev.get("errors") or {},
                "wallpaper": True,
                "theme_id": last,
                "steps": res.get("steps"),
            }
        board_lines = (prev or {}).get("board_lines") or []
        with self._dev_op_lock(host, port):
            dev = self._get_dev(host, port)
            gathin = LauncherDetector(dev).detect_gathin()
            if not gathin.get("installed"):
                raise Exception(
                    "TV chưa cài launcher SmartTV Home (com.smtv_manager.home). "
                    "Widget Home chỉ áp dụng được khi đã cài launcher này."
                )
            tm = ThemeManager(dev)
            tm.patch_config(patch, restart=bool(restart))
            try:
                tm.write_json_sidecar("smarttv_widgets.json", sidecar)
            except Exception:
                pass
        return {
            "ok": True,
            "greeting_name": patch.get("greeting_name"),
            "board_lines": board_lines,
            "errors": prev.get("errors") or {},
        }


    # ------------------------------------------------------------------
    # TV Guard: screen-time lock enforced by a companion app on the TV
    # ------------------------------------------------------------------
    def _guard_call(self, host, port, fn):
        """Run fn(guard, dev) under the per-device lock and turn failures into plain messages."""
        port = int(port)
        with self._dev_op_lock(host, port):
            try:
                dev = self._get_dev(host, port)
                return fn(TvGuard(dev, host, port), dev)
            except GuardError as e:
                raise Exception(str(e)) from e
            except Exception as e:
                if self._adb_timeout_error(e):
                    self._drop_dev(host, port)
                raise self._adb_shell_error(host, port, e) from e

    def guard_status(self, host, port=5555):
        return self._guard_call(host, port, lambda g, _dev: g.summary())

    def guard_setup_async(self, host, port=5555, pin="", policy=None):
        """Install, pair and configure TV Guard in the background. Poll with guard_job."""
        self._require_android(host)
        port = int(port)
        job_id = uuid.uuid4().hex
        job = {"id": job_id, "status": "running", "steps": [], "error": None, "result": None,
               "log_path": None}
        with self._apply_jobs_lock:
            self._apply_jobs[job_id] = job

        def step(msg, detail=""):
            job["steps"].append({"t": time.time(), "msg": msg, "detail": detail or ""})

        def run():
            try:
                def work(g, dev):
                    return g.setup(ApkInstaller(dev), pin, policy or {}, step)
                job["result"] = self._guard_call(host, port, work)
                job["status"] = "done"
            except Exception as exc:
                job["error"] = str(exc)
                job["status"] = "failed"

        threading.Thread(target=run, daemon=True).start()
        return {"job_id": job_id}

    def guard_job(self, job_id=""):
        return self.apply_gathin_theme_job(job_id)

    def guard_save_policy(self, host, port=5555, policy=None, pin=""):
        from core import tv_guard

        def work(g, _dev):
            pol = tv_guard.normalize_policy(policy or {})
            if not (policy or {}).get("tz"):
                pol["tz"] = g.tv_timezone()
            if pin:
                g.send("set_pin", tv_guard.hash_pin(tv_guard.validate_pin(pin)))
            g.send("set_policy", json.dumps(pol))
            return g.summary()
        return self._guard_call(host, port, work)

    def guard_diagnose(self, host, port=5555):
        """Plain-text report from the TV for troubleshooting (shown under "Chi tiết kỹ thuật")."""
        return {"text": self._guard_call(host, port, lambda g, _dev: g.diagnose())}

    def guard_lock_now(self, host, port=5555, minutes=30):
        def work(g, _dev):
            g.send("lock_now", str(int(minutes)))
            return g.summary()
        return self._guard_call(host, port, work)

    def guard_unlock_now(self, host, port=5555, minutes=0):
        def work(g, _dev):
            g.send("unlock_now", str(int(minutes)))
            return g.summary()
        return self._guard_call(host, port, work)

    def guard_uninstall(self, host, port=5555):
        def work(g, _dev):
            g.uninstall()
            return g.summary()
        return self._guard_call(host, port, work)


if __name__ == "__main__":
    import atexit
    import sys

    api = Api()
    atexit.register(api.shutdown)
    api.prefetch_launcher()
    root = paths.app_root()
    ui_path = os.path.join(root, "ui", "index.html")
    icon_path = os.path.join(root, "ui", "assets", "app-icon.png")
    if os.name == "nt":
        ico = os.path.join(root, "assets", "app-icon.ico")
        if os.path.isfile(ico):
            icon_path = ico
    window = webview.create_window(
        APP_DISPLAY_NAME,
        ui_path,
        js_api=api,
        width=1280,
        height=820,
        resizable=True,
        background_color="#07090E",
    )

    def _on_window_closing():
        api.shutdown()
        return True

    window.events.closing += _on_window_closing
    start_kwargs = {"icon": icon_path} if os.path.isfile(icon_path) else {}
    webview.start(**start_kwargs)
