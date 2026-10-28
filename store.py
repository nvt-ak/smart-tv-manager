"""Saved device list: ~/.smarttv-manager/devices.json."""
import json
import os
import threading
import uuid
from datetime import datetime

from adb_client import KEY_DIR

PATH = os.path.join(KEY_DIR, "devices.json")
_lock = threading.Lock()


def _normalize_devices(devices):
    for d in devices:
        if "last_seen" not in d:
            d["last_seen"] = None
        if "online" not in d:
            d["online"] = False
        d.setdefault("platform", "android_tv")
        if "port" not in d:
            d["port"] = 3001 if d["platform"] == "lg_webos" else 5555
    return devices


def _snapshot_devices(devices):
    """Bản sao nông — caller không giữ reference list đang dùng nội bộ store."""
    return [dict(d) for d in devices]


def load():
    with _lock:
        if not os.path.exists(PATH):
            return []
        try:
            with open(PATH, encoding="utf-8") as f:
                return _normalize_devices(json.load(f))
        except Exception:
            return []


def _write_devices_file(devices):
    """Ghi devices.json — caller phải đang giữ `_lock`."""
    os.makedirs(KEY_DIR, mode=0o700, exist_ok=True)
    tmp = os.path.join(KEY_DIR, f"devices.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(devices, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, PATH)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def save(devices):
    with _lock:
        _write_devices_file(devices)


def batch_update_online(status_by_host: dict):
    """Update online flags for many hosts in one read/write (thread-safe)."""
    if not status_by_host:
        return load()
    with _lock:
        if not os.path.exists(PATH):
            devices = []
        else:
            try:
                with open(PATH, encoding="utf-8") as f:
                    devices = _normalize_devices(json.load(f))
            except Exception:
                devices = []
        changed = False
        now = datetime.now().isoformat()
        for d in devices:
            host = d.get("host")
            if host not in status_by_host:
                continue
            online = bool(status_by_host[host])
            prev_online = bool(d.get("online"))
            if prev_online == online:
                continue
            d["online"] = online
            if online:
                d["last_seen"] = now
            changed = True
        if changed:
            _write_devices_file(devices)
        return _snapshot_devices(devices)


def upsert(host, port, name, platform=None, **metadata):
    with _lock:
        devices = []
        if os.path.exists(PATH):
            try:
                with open(PATH, encoding="utf-8") as f:
                    devices = _normalize_devices(json.load(f))
            except Exception:
                devices = []
        previous = next((d for d in devices if d["host"] == host), {})
        devices = [d for d in devices if d["host"] != host]
        previous.update({k: v for k, v in metadata.items() if k not in ("client_key", "secret", "private_key")})
        previous.update({
            "platform": platform or previous.get("platform", "android_tv"),
            "name": name,
            "host": host,
            "port": int(port),
            "last_seen": datetime.now().isoformat(),
            "online": True,
        })
        devices.append(previous)
        _write_devices_file(devices)
    return _snapshot_devices(devices)


def update_status(host, online=True, last_seen=None):
    return batch_update_online({host: online})


def rename(host, name):
    with _lock:
        if not os.path.exists(PATH):
            return []
        try:
            with open(PATH, encoding="utf-8") as f:
                devices = _normalize_devices(json.load(f))
        except Exception:
            return []
        changed = False
        for d in devices:
            if d["host"] == host:
                d["name"] = name
                changed = True
                break
        if not changed:
            return _snapshot_devices(devices)
        _write_devices_file(devices)
        return _snapshot_devices(devices)


def remove(host):
    with _lock:
        if not os.path.exists(PATH):
            return []
        try:
            with open(PATH, encoding="utf-8") as f:
                devices = _normalize_devices(json.load(f))
        except Exception:
            devices = []
        devices = [d for d in devices if d["host"] != host]
        _write_devices_file(devices)
    return _snapshot_devices(devices)
