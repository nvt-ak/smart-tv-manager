"""Theme apply/backup/reset for the gathin.tvhome launcher.

The launcher overlays `config.json` (plus `wallpaper.jpg` and an optional
`wallpapers/` collection) from its external files directory onto the built-in
`res/values/config.xml`.  `tools/theme.sh` in cleanyourtv is the reference
implementation; this module ports its behaviour to adb-shell:

  * files are staged in /data/local/tmp and written through
    `content://com.gathin.tvhome.theme/...` (the launcher's ThemeProvider, which
    needs WRITE_SECURE_SETTINGS - the adb shell has it).  Writing into
    Android/data directly leaves files owned by the shell, which the launcher
    cannot read on Android 14, so `cp` is only a fallback for firmware without
    the provider.
  * a fresh `theme_revision` invalidates layout/motion choices made on the TV.
  * Home is restarted afterwards, restoring the accessibility services that
    Android drops when an app is force-stopped.
"""
import json
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import adb_client
from adb_shell.adb_device import AdbDeviceTcp

PKG = "com.gathin.tvhome"
HOME_DIR = f"/sdcard/Android/data/{PKG}/files"
THEME_URI = f"content://{PKG}.theme"
STAGE_PREFIX = "/data/local/tmp/tvremotehub-theme"

CONFIG_NAME = "config.json"
WALLPAPER_NAME = "wallpaper.jpg"
COLLECTION = "wallpapers"
CAPTIONS_NAME = "captions.txt"
REVISION_NAME = "theme_revision"

IMAGE_RE = re.compile(r"^[A-Za-z0-9_.-]+\.(jpg|jpeg|png|webp)$", re.IGNORECASE)

# Keys the launcher accepts in config.json (see cleanyourtv themes/README.md).
KNOWN_KEYS = {
    "dock_apps", "fill_dock", "hidden_apps", "columns", "rows_below_dock",
    "animations", "advanced_effects", "reduced_motion", "background_color",
    "wallpaper", "wallpaper_rotation_minutes", "wallpaper_rotation_seconds",
    "wallpaper_order", "wallpaper_dim", "wallpaper_captions", "wallpaper_true_color",
    "dock_opacity", "dock_glass", "dock_row", "dock_title", "top_menu",
    "launcher_settings_button", "reorder_button", "always_show_names",
    "show_network_pill", "show_inputs_pill", "icon_only_buttons", "library_button",
    "app_library", "app_glow", "ambient_glow", "cinematic_home", "focus_overshoot",
    "glow_style", "sky_intensity", "show_stats", "shamsi_date", "greeting_name",
    "module_cards", "boot_to_live_tv", "home_idle_clock_minutes", "tile_menu",
    "live_tv_package", "live_tv_action", "live_tv_input_id", "launch_actions",
    "app_labels", "app_banners", "input_action", "input_uri_scheme",
    "input_key_keycodes", "settings_key_keycodes", "settings_key_panel",
    "restore_key_services", "key_filter", "app_keys", "stock_home_redirect",
    "handle_view_inputs", "coocaa_sources", "source_panel_service",
    "source_panel_action", "source_panel_extra", "festival", "festival_until",
    "greeting", "accent_color", "race_calendar", "vpn_app", "wifi_label_width",
    "show_home_settings_shortcut",
}

COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


class ThemeManager:
    def __init__(self, device: AdbDeviceTcp):
        self.device = device
        self._provider_supported: Optional[bool] = None

    # ------------------------------------------------------------------ shell

    def _shell(self, cmd: str, timeout_s: Optional[float] = None) -> str:
        timeout = (
            timeout_s if timeout_s is not None else adb_client.CONNECT_TIMEOUT
        )
        last: Optional[Exception] = None
        for attempt in range(3):
            try:
                return (
                    self.device.shell(
                        cmd,
                        transport_timeout_s=timeout,
                        read_timeout_s=timeout,
                        timeout_s=timeout,
                    )
                    or ""
                )
            except Exception as e:
                last = e
                msg = str(e).lower()
                if attempt >= 2 or "timed out" not in msg:
                    break
                try:
                    adb_client.reconnect(self.device)
                except Exception:
                    pass
                time.sleep(0.5)
        raise Exception(f"Shell error: {last}")

    def _push(self, local: str, remote: str) -> None:
        try:
            size = os.path.getsize(local)
        except OSError:
            size = 0
        timeout = adb_client.transfer_timeout_s(size)
        last: Optional[Exception] = None
        for attempt in range(3):
            try:
                self.device.push(
                    local,
                    remote,
                    transport_timeout_s=timeout,
                    read_timeout_s=timeout,
                )
                return
            except Exception as e:
                last = e
                msg = str(e).lower()
                if attempt >= 2 or "timed out" not in msg:
                    break
                try:
                    adb_client.reconnect(self.device)
                except Exception:
                    pass
                time.sleep(0.5)
        raise Exception(
            f"Không đẩy được {os.path.basename(local)} lên TV: {last}"
        )

    # --------------------------------------------------------------- provider

    def provider_supported(self) -> bool:
        """True when the launcher's ThemeProvider accepts writes."""
        if self._provider_supported is not None:
            return self._provider_supported
        try:
            out = self._shell(
                "cmd package resolve-content-provider "
                f"{THEME_URI}/{CONFIG_NAME} 2>&1 || pm list packages {PKG} 2>&1"
            )
            ok = PKG in out and "Unknown" not in out
        except Exception:
            ok = False
        self._provider_supported = ok
        return ok

    # ------------------------------------------------------------ device paths

    def read_config(self) -> Dict[str, Any]:
        """Read the overlay currently on the TV ({} when there is none)."""
        try:
            out = self._shell(f"cat {HOME_DIR}/{CONFIG_NAME} 2>/dev/null")
        except Exception:
            return {}
        text = (out or "").strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            return {}

    def read_revision(self) -> str:
        try:
            return self._shell(f"cat {HOME_DIR}/{REVISION_NAME} 2>/dev/null").strip()
        except Exception:
            return ""

    def list_wallpapers(self) -> List[str]:
        try:
            out = self._shell(f"ls {HOME_DIR}/{COLLECTION} 2>/dev/null")
        except Exception:
            return []
        names = []
        for line in out.splitlines():
            name = line.strip()
            if name and IMAGE_RE.match(name):
                names.append(name)
        return sorted(names)

    # ---------------------------------------------------------------- backup

    def backup_config(self, local_dir: str) -> Dict[str, Any]:
        """Save the current overlay (config + wallpaper names + revision) locally.

        A backup is mandatory before every write, so this never raises for a
        missing config: restoring "no config" is itself a valid backup.
        """
        stamp = time.strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(local_dir, stamp)
        os.makedirs(dest, exist_ok=True)

        config = self.read_config()
        wallpapers = self.list_wallpapers()
        revision = self.read_revision()

        with open(os.path.join(dest, CONFIG_NAME), "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        manifest = {
            "time": stamp,
            "had_config": bool(config),
            "config": config,
            "wallpapers": wallpapers,
            "revision": revision,
            "wallpaper": None,
            "wallpaper_files": [],
        }

        # Keep the actual wallpaper bytes when the shell can read them.
        wp = os.path.join(dest, WALLPAPER_NAME)
        try:
            self.device.pull(f"{HOME_DIR}/{WALLPAPER_NAME}", wp)
            if os.path.exists(wp) and os.path.getsize(wp) > 0:
                manifest["wallpaper"] = WALLPAPER_NAME
            else:
                if os.path.exists(wp):
                    os.unlink(wp)
        except Exception:
            pass

        if wallpapers:
            wp_dir = os.path.join(dest, COLLECTION)
            os.makedirs(wp_dir, exist_ok=True)
            for name in wallpapers:
                target = os.path.join(wp_dir, name)
                try:
                    self.device.pull(f"{HOME_DIR}/{COLLECTION}/{name}", target)
                    if os.path.exists(target) and os.path.getsize(target) > 0:
                        manifest["wallpaper_files"].append(name)
                except Exception:
                    pass

        with open(os.path.join(dest, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        return {"path": dest, "time": stamp, "had_config": bool(config),
                "wallpapers": len(wallpapers)}

    def restore_backup(self, backup_dir: str) -> Dict[str, Any]:
        """Restore a folder produced by backup_config()."""
        manifest_path = os.path.join(backup_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            raise Exception("Bản sao lưu không hợp lệ (thiếu manifest.json)")
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

        if not manifest.get("had_config"):
            return self.reset()

        config_path = os.path.join(backup_dir, CONFIG_NAME)
        if not os.path.exists(config_path):
            raise Exception("Bản sao lưu thiếu config.json")

        self._write_file(config_path, CONFIG_NAME)

        wp_path = os.path.join(backup_dir, WALLPAPER_NAME)
        if manifest.get("wallpaper") and os.path.exists(wp_path):
            self._write_file(wp_path, WALLPAPER_NAME)
        else:
            self._delete_file(WALLPAPER_NAME)

        self._clear_collection()
        wp_dir = os.path.join(backup_dir, COLLECTION)
        for name in manifest.get("wallpaper_files") or []:
            local = os.path.join(wp_dir, name)
            if os.path.exists(local):
                self._write_file(local, f"{COLLECTION}/{name}")

        self._write_revision()
        self.restart_launcher()
        return {"ok": True, "restored": backup_dir}

    # ------------------------------------------------------------- validation

    @staticmethod
    def validate_theme(theme: Dict[str, Any]) -> Dict[str, Any]:
        """Check a theme folder before it can be applied (roadmap: theme validator)."""
        errors: List[str] = []
        warnings: List[str] = []

        config = theme.get("config") or {}
        if not config:
            errors.append("Theme thiếu hoặc có config.json không hợp lệ")

        if len(json.dumps(config).encode("utf-8")) > 64 * 1024:
            errors.append("config.json vượt quá 64 KB (launcher sẽ bỏ qua)")

        unknown = sorted(set(config) - KNOWN_KEYS)
        if unknown:
            warnings.append("Khoá không được launcher hỗ trợ: " + ", ".join(unknown[:8]))

        cols = config.get("columns")
        if cols is not None and (not isinstance(cols, int) or not 1 <= cols <= 8):
            errors.append("columns phải là số nguyên trong khoảng 1-8")

        rows = config.get("rows_below_dock")
        if rows is not None and (not isinstance(rows, int) or not 0 <= rows <= 3):
            errors.append("rows_below_dock phải là số nguyên trong khoảng 0-3")

        color = config.get("background_color")
        if color is not None and not (isinstance(color, str) and COLOR_RE.match(color)):
            errors.append("background_color phải là #RRGGBB")

        for key in ("wallpaper_rotation_minutes", "wallpaper_rotation_seconds"):
            val = config.get(key)
            if val is not None and (not isinstance(val, int) or val < 0):
                errors.append(f"{key} phải là số nguyên không âm")

        dock = config.get("dock_apps")
        if dock is not None and not isinstance(dock, list):
            errors.append("dock_apps phải là mảng package name")

        # Wallpaper collection: the launcher only reads a strict filename shape.
        for path in theme.get("wallpapers") or []:
            name = os.path.basename(path)
            if not IMAGE_RE.match(name):
                errors.append(f"Tên wallpaper không hợp lệ: {name}")

        wallpaper = theme.get("wallpaper")
        if wallpaper:
            size = os.path.getsize(wallpaper) if os.path.exists(wallpaper) else 0
            if size > 12 * 1024 * 1024:
                warnings.append("Wallpaper lớn hơn 12 MB, có thể chậm khi tải trên TV")
            dims = _image_size(wallpaper)
            if dims:
                w, h = dims
                if w < 1280 or h < 720:
                    warnings.append(f"Wallpaper {w}×{h} nhỏ hơn 1280×720, có thể bị mờ")

        return {"ok": not errors, "errors": errors, "warnings": warnings}

    # ----------------------------------------------------------------- apply

    def apply_theme(self, theme: Dict[str, Any]) -> Dict[str, Any]:
        """Write config + wallpapers, bump the revision and restart Home."""
        check = self.validate_theme(theme)
        if not check["ok"]:
            raise Exception("; ".join(check["errors"]))

        self._shell(f"mkdir -p {HOME_DIR} 2>/dev/null")

        config_path = os.path.join(theme["path"], CONFIG_NAME)
        self._write_file(config_path, CONFIG_NAME)

        wallpaper = theme.get("wallpaper")
        if wallpaper and os.path.exists(wallpaper):
            self._write_file(wallpaper, WALLPAPER_NAME)
        else:
            self._delete_file(WALLPAPER_NAME)

        self._clear_collection()
        for local in theme.get("wallpapers") or []:
            if os.path.exists(local):
                self._write_file(local, f"{COLLECTION}/{os.path.basename(local)}")

        captions = None
        for local in theme.get("wallpapers") or []:
            if os.path.basename(local).lower() == CAPTIONS_NAME:
                captions = local
        if captions:
            self._write_file(captions, f"{COLLECTION}/{CAPTIONS_NAME}")
        else:
            self._delete_file(f"{COLLECTION}/{CAPTIONS_NAME}")

        self._write_revision()
        self.restart_launcher()
        return {"ok": True, "warnings": check["warnings"]}

    def reset(self) -> Dict[str, Any]:
        """Remove the overlay: back to the firmware's built-in config.xml."""
        self._delete_file(CONFIG_NAME)
        self._delete_file(WALLPAPER_NAME)
        self._clear_collection()
        self._delete_file(f"{COLLECTION}/{CAPTIONS_NAME}")
        self._write_revision()
        self.restart_launcher()
        return {"ok": True}

    # -------------------------------------------------------------- internals

    def _stage(self, local_path: str, rel: str) -> str:
        staged = STAGE_PREFIX + "-" + rel.replace("/", "-")
        self._push(local_path, staged)
        return staged

    def _write_file(self, local_path: str, rel: str) -> None:
        """Provider write first, `cp` fallback (mirrors theme.sh `put`)."""
        try:
            size = os.path.getsize(local_path)
        except OSError:
            size = 0
        io_timeout = adb_client.transfer_timeout_s(size)
        staged = self._stage(local_path, rel)
        target = f"{HOME_DIR}/{rel}"
        cmd = (
            f"mkdir -p $(dirname {target}) 2>/dev/null; "
            f"rm -f {target} 2>/dev/null; "
            f"o=$(content write --uri {THEME_URI}/{rel} < {staged} 2>&1) && "
            "case \"$o\" in *'Unsupported operation'*) false ;; esac "
            f"|| cp {staged} {target} 2>/dev/null; "
            f"rm -f {staged}; echo \"$o\""
        )
        out = self._shell(cmd, timeout_s=io_timeout).strip()
        exists = self._shell(
            f"[ -f {target} ] && echo yes || echo no", timeout_s=io_timeout
        ).strip()
        if "yes" not in exists:
            hint = out[:240] if out else "content write và cp đều thất bại"
            raise Exception(
                f"Không ghi được {rel} lên TV (firmware chặn Android/data?): {hint}"
            )
        return out

    def _delete_file(self, rel: str) -> None:
        target = f"{HOME_DIR}/{rel}"
        self._shell(
            f"rm -f {target} 2>/dev/null; "
            f"content delete --uri {THEME_URI}/{rel} 2>/dev/null"
        )

    def _clear_collection(self) -> None:
        self._shell(f"mkdir -p {HOME_DIR}/{COLLECTION} 2>/dev/null")
        self._shell(
            f"rm -f {HOME_DIR}/{COLLECTION}/*.jpg {HOME_DIR}/{COLLECTION}/*.jpeg "
            f"{HOME_DIR}/{COLLECTION}/*.png {HOME_DIR}/{COLLECTION}/*.webp "
            f"{HOME_DIR}/{COLLECTION}/*.JPG {HOME_DIR}/{COLLECTION}/*.JPEG "
            f"{HOME_DIR}/{COLLECTION}/*.PNG {HOME_DIR}/{COLLECTION}/*.WEBP 2>/dev/null; "
            f"content delete --uri {THEME_URI}/{COLLECTION} 2>/dev/null"
        )

    def _write_revision(self) -> None:
        token = uuid.uuid4().hex
        tmp = f"{STAGE_PREFIX}-{REVISION_NAME}"
        self._shell(f"printf '%s' '{token}' > {tmp}")
        self._shell(
            f"rm -f {HOME_DIR}/{REVISION_NAME} 2>/dev/null; "
            f"o=$(content write --uri {THEME_URI}/{REVISION_NAME} < {tmp} 2>&1) && "
            "case \"$o\" in *'Unsupported operation'*) false ;; esac "
            f"|| cp {tmp} {HOME_DIR}/{REVISION_NAME} 2>/dev/null; "
            f"rm -f {tmp}"
        )

    def restart_launcher(self) -> bool:
        """Force-stop Home and bring it back, restoring the accessibility list.

        Android drops a force-stopped app's accessibility services, which would
        switch off the launcher's InputKeyService/HomeKeyService, so the list is
        cleared and written back (the service only rebinds when the value
        actually changes).
        """
        script = (
            "a=$(settings get secure enabled_accessibility_services); "
            f"am force-stop {PKG}; "
            "case \"$(cmd package resolve-activity --brief -a android.intent.action.MAIN "
            f"-c android.intent.category.HOME | tail -n 1)\" in {PKG}/*) "
            "am start -a android.intent.action.MAIN -c android.intent.category.HOME >/dev/null ;; "
            f"*) am start -n {PKG}/.MainActivity >/dev/null ;; esac; "
            f"case \"$a\" in *{PKG}*) "
            'sleep 1; settings put secure enabled_accessibility_services "$a"; '
            "settings put secure accessibility_enabled 1; sleep 1; "
            "settings put secure enabled_accessibility_services ''; "
            "settings put secure accessibility_enabled 0; sleep 1; "
            'settings put secure enabled_accessibility_services "$a"; '
            "settings put secure accessibility_enabled 1 ;; esac"
        )
        try:
            self._shell(script, timeout_s=45.0)
            return True
        except Exception:
            return False

    # Kept for callers that only want the restart.
    def force_stop_launcher(self) -> bool:
        return self.restart_launcher()


def _image_size(path: str) -> Optional[Tuple[int, int]]:
    """Best-effort image dimensions (Pillow when installed, else PNG/JPEG header)."""
    try:
        from PIL import Image  # type: ignore

        with Image.open(path) as im:
            return im.size
    except Exception:
        pass
    try:
        with open(path, "rb") as f:
            head = f.read(26)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            import struct

            w, h = struct.unpack(">II", head[16:24])
            return int(w), int(h)
        if head[:2] == b"\xff\xd8":
            with open(path, "rb") as f:
                f.read(2)
                while True:
                    marker = f.read(2)
                    if len(marker) < 2 or marker[0] != 0xFF:
                        break
                    if marker[1] in (0xC0, 0xC1, 0xC2, 0xC3):
                        f.read(3)
                        h, w = __import__("struct").unpack(">HH", f.read(4))
                        return int(w), int(h)
                    length = __import__("struct").unpack(">H", f.read(2))[0]
                    f.seek(length - 2, 1)
    except Exception:
        pass
    return None
