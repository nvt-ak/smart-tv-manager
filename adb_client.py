"""Minimal ADB-over-TCP client (adb-shell, no adb binary needed).

Key is stored at ~/.smarttv-manager/adbkey, separate from the stock
~/.android/adbkey so this app's "Allow USB debugging?" grant on each TV
is independent of other ADB clients on this machine.
"""
import ipaddress
import os
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor

from adb_shell.adb_device import AdbDeviceTcp
from adb_shell.auth.keygen import keygen
from adb_shell.auth.sign_pythonrsa import PythonRSASigner

from app_brand import user_data_dir

PORT = 5555
CONNECT_TIMEOUT = 8.0
# Most TV shell commands over Wi‑Fi need more than 8s; default read timeout for generic shell.
SHELL_DEFAULT_TIMEOUT = 25.0
# `pm list packages` on a TV over Wi‑Fi can exceed 8s when the link is busy.
SHELL_HEAVY_TIMEOUT = 45.0
# Wi‑Fi ADB on TVs is often << 1 MB/s; 30s is too tight even for ~150 KB wallpapers.
PUSH_TIMEOUT_MIN = 90.0
PUSH_TIMEOUT_MAX = 600.0
# Assumed minimum throughput when scaling timeouts (bytes per second).
PUSH_ASSUMED_BPS = 48 * 1024
SCAN_PORT_TIMEOUT = 0.3
QUICK_CHECK_TIMEOUT = 2.5


def transfer_timeout_s(size_bytes: int) -> float:
    """Wi‑Fi ADB: scale timeout for push/shell that moves ~size_bytes."""
    if size_bytes <= 0:
        return PUSH_TIMEOUT_MIN
    # Base slack for TV shell/filesync + transfer at assumed slow Wi‑Fi.
    needed = 45.0 + (size_bytes / PUSH_ASSUMED_BPS) + 25.0
    return min(PUSH_TIMEOUT_MAX, max(PUSH_TIMEOUT_MIN, needed))


push_timeout_s = transfer_timeout_s  # backwards-compatible alias


def reconnect(device, timeout=CONNECT_TIMEOUT):
    """Re-open TCP ADB after a filesync timeout leaves the session stuck."""
    try:
        device.close()
    except Exception:
        pass
    device.connect(rsa_keys=[get_signer()], auth_timeout_s=timeout)
    if not device.available:
        raise Exception("Không kết nối lại được ADB tới TV (connect thất bại)")


def ensure_connected(device, timeout=CONNECT_TIMEOUT):
    """Raise if the device cannot accept shell/sync (reconnect when needed)."""
    if getattr(device, "available", False):
        try:
            device.shell(
                "echo ok",
                transport_timeout_s=timeout,
                read_timeout_s=timeout,
                timeout_s=timeout,
            )
            return
        except Exception:
            pass
    reconnect(device, timeout=timeout)


def shell_timeout_for(command: str) -> float:
    c = (command or "").lower()
    heavy = (
        "dumpsys",
        "pm list",
        "pm install",
        "pm path",
        "pkg ",
        "logcat",
        " backup",
        "restore",
        "df ",
        "du ",
        "getevent",
        "screenrecord",
        "am start",
    )
    if any(m in c for m in heavy):
        return SHELL_HEAVY_TIMEOUT
    return SHELL_DEFAULT_TIMEOUT


def run_shell(device, command: str, timeout: float | None = None) -> str:
    """Run adb shell with Wi‑Fi-friendly timeouts and one reconnect retry."""
    t = float(timeout if timeout is not None else shell_timeout_for(command))
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            ensure_connected(device, timeout=min(t, 15.0))
            return device.shell(
                command,
                transport_timeout_s=t,
                read_timeout_s=t,
                timeout_s=t,
            )
        except Exception as e:
            last_err = e
            if attempt == 0:
                try:
                    reconnect(device, timeout=min(t, 15.0))
                except Exception:
                    pass
    assert last_err is not None
    raise last_err


KEY_DIR = user_data_dir()
KEY_PATH = os.path.join(KEY_DIR, "adbkey")


def get_signer():
    os.makedirs(KEY_DIR, mode=0o700, exist_ok=True)
    if not os.path.exists(KEY_PATH):
        keygen(KEY_PATH)
        os.chmod(KEY_PATH, 0o600)
    with open(KEY_PATH) as f:
        priv = f.read()
    with open(KEY_PATH + ".pub") as f:
        pub = f.read()
    return PythonRSASigner(pub, priv)


def connect(host, port=PORT, timeout=CONNECT_TIMEOUT):
    """Authenticate to one TV. Raises on failure (including a first-time
    grant that the person hasn't accepted on the TV's screen yet)."""
    dev = AdbDeviceTcp(host, port, default_transport_timeout_s=timeout)
    dev.connect(rsa_keys=[get_signer()], auth_timeout_s=timeout)
    return dev


def probe(host, port=PORT, timeout=CONNECT_TIMEOUT):
    """Connect and return {model, android, build}."""
    dev = connect(host, port, timeout)
    try:
        model = dev.shell("getprop ro.product.model").strip()
        android = dev.shell("getprop ro.build.version.release").strip()
        build = dev.shell("getprop ro.build.display.id").strip()
        return {"model": model, "android": android, "build": build}
    finally:
        dev.close()


def quick_check(host, port=PORT, timeout=QUICK_CHECK_TIMEOUT):
    """Lightweight online check without full probe. Returns True/False."""
    try:
        dev = AdbDeviceTcp(host, int(port), default_transport_timeout_s=timeout)
        dev.connect(rsa_keys=[get_signer()], auth_timeout_s=timeout)
        try:
            dev.shell("echo ok")
            return True
        finally:
            try:
                dev.close()
            except Exception:
                pass
    except Exception:
        return False


def send_key(host, port=PORT, keycode=4, timeout=CONNECT_TIMEOUT):
    """Send keyevent to device."""
    dev = connect(host, int(port), timeout)
    try:
        dev.shell(f"input keyevent {int(keycode)}")
        return True
    finally:
        try:
            dev.close()
        except Exception:
            pass


def _local_subnets():
    """/24 networks for every non-loopback IPv4 interface, best-effort."""
    nets = set()
    try:
        out = subprocess.run(
            ["ifconfig"] if os.name != "nt" else ["ipconfig"],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except Exception:
        out = ""
    for line in out.splitlines():
        line = line.strip()
        ip = None
        if line.startswith("inet ") and "127.0.0.1" not in line:
            ip = line.split()[1].split("/")[0]
        elif "IPv4" in line and ":" in line:
            ip = line.split(":")[-1].strip()
        if ip:
            try:
                nets.add(str(ipaddress.ip_network(f"{ip}/24", strict=False)))
            except ValueError:
                pass
    if not nets:
        # Fallback: ask the OS which local address it would use to reach the
        # internet, then assume that /24 (no traffic is actually sent).
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            nets.add(str(ipaddress.ip_network(f"{ip}/24", strict=False)))
        except OSError:
            pass
    return nets


def _port_open(host, port, timeout):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def port_reachable(host, port=PORT, timeout=None):
    """Fast TCP check — does not authenticate ADB (use quick_check for that)."""
    t = float(timeout if timeout is not None else SCAN_PORT_TIMEOUT)
    return _port_open(host, int(port), t)


def scan_subnet(progress=None):
    """Scan every local /24 for hosts with ADB's port 5555 open.
    Returns a list of IP strings. Does not authenticate."""
    from concurrent.futures import as_completed

    hosts = set()
    for net in _local_subnets():
        try:
            hosts.update(str(h) for h in ipaddress.ip_network(net).hosts())
        except Exception:
            pass
    found = []
    if not hosts:
        return []
    with ThreadPoolExecutor(max_workers=96) as pool:
        futures = {
            pool.submit(_port_open, h, PORT, SCAN_PORT_TIMEOUT): h for h in hosts
        }
        done = 0
        total = len(futures)
        for fut in as_completed(futures):
            done += 1
            if progress:
                try:
                    progress(done, total)
                except Exception:
                    pass
            try:
                if fut.result():
                    found.append(futures[fut])
            except Exception:
                pass
    return sorted(set(found), key=lambda ip: tuple(int(p) for p in ip.split(".")))
