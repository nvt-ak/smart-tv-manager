"""Saved device list: ~/.smarttv-manager/devices.json."""
import json
import os
from datetime import datetime

from adb_client import KEY_DIR

PATH = os.path.join(KEY_DIR, "devices.json")


def load():
    if not os.path.exists(PATH):
        return []
    try:
        with open(PATH, encoding="utf-8") as f:
            devices = json.load(f)
        # Backward compatibility: ensure all fields exist
        for d in devices:
            if "last_seen" not in d:
                d["last_seen"] = None
            if "online" not in d:
                d["online"] = False
            if "port" not in d:
                d["port"] = 5555
        return devices
    except Exception:
        return []


def save(devices):
    os.makedirs(KEY_DIR, mode=0o700, exist_ok=True)
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(devices, f, indent=2, ensure_ascii=False)
    os.replace(tmp, PATH)


def upsert(host, port, name):
    devices = [d for d in load() if d["host"] != host]
    devices.append({
        "name": name,
        "host": host,
        "port": int(port),
        "last_seen": datetime.now().isoformat(),
        "online": True,
    })
    save(devices)
    return devices


def update_status(host, online=True, last_seen=None):
    devices = load()
    changed = False
    for d in devices:
        if d["host"] == host:
            d["online"] = bool(online)
            if online:
                d["last_seen"] = last_seen or datetime.now().isoformat()
            changed = True
            break
    if changed:
        save(devices)
    return devices


def rename(host, name):
    devices = load()
    changed = False
    for d in devices:
        if d["host"] == host:
            d["name"] = name
            changed = True
            break
    if changed:
        save(devices)
    return devices


def remove(host):
    devices = [d for d in load() if d["host"] != host]
    save(devices)
    return devices
