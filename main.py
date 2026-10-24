"""SmartTV Manager: desktop app, lists TVs on the LAN and connects over ADB."""
import os
from concurrent.futures import ThreadPoolExecutor

import webview

import adb_client
from app_brand import APP_DISPLAY_NAME
import paths
import store
from core.package_manager import PackageManager
from core.safety import safety
from core.apk_analyzer import ApkAnalyzer
from core.apk_installer import ApkInstaller
from core.launcher_detector import LauncherDetector
from core.theme_manager import ThemeManager
from core.cleanyourtv_themes import CleanyourtvThemes
from core.clean_suggestions import CleanSuggestionEngine
from core import ai_clean
import settings_store
import base64
import json
import os
import tempfile
import threading
import time
import uuid

THEME_APPLY_LOG = os.path.join(adb_client.KEY_DIR, "theme-apply.log")


class Api:
    def __init__(self):
        self._pm_cache = {}
        self._dev_cache = {}
        self._themes = CleanyourtvThemes()
        self._apply_jobs = {}
        self._apply_jobs_lock = threading.Lock()
        self._dev_locks = {}
        self._clean_engine = CleanSuggestionEngine()

    def _dev_op_lock(self, host, port=5555):
        key = f"{host}:{port}"
        if key not in self._dev_locks:
            self._dev_locks[key] = threading.Lock()
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

    def _ping_cached_dev(self, dev, timeout=None):
        timeout = timeout if timeout is not None else adb_client.QUICK_CHECK_TIMEOUT
        try:
            adb_client.ensure_connected(dev, timeout=timeout)
            return True
        except Exception:
            return False

    def _get_dev(self, host, port=5555):
        key = f"{host}:{port}"
        if key in self._dev_cache:
            if self._ping_cached_dev(self._dev_cache[key]):
                return self._dev_cache[key]
            self._drop_dev(host, port)
        dev = adb_client.connect(host, int(port))
        self._dev_cache[key] = dev
        return dev

    def _get_pm(self, host, port=5555):
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
            if mode == "port":
                online = adb_client.port_reachable(host, port)
            else:
                online = adb_client.quick_check(host, port)
            nd = dict(d)
            nd["online"] = online
            return host, online, nd

        workers = min(8, len(devices))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(check_one, devices))
        store.batch_update_online({host: online for host, online, _ in rows})
        return [nd for _, _, nd in rows]

    def scan(self):
        found = adb_client.scan_subnet()
        # Return all found devices (including already saved) so user can see them
        return found

    def connect(self, host, port=5555, name=None):
        info = adb_client.probe(host, int(port))
        store.upsert(host, int(port), name or info["model"] or host)
        return info

    def rename(self, host, name):
        if not name or not name.strip():
            raise ValueError("Tên không được để trống")
        store.rename(host, name.strip())
        return True

    def remove(self, host):
        return store.remove(host)

    def remote_key(self, host, port=5555, keycode=4):
        try:
            adb_client.send_key(host, int(port), int(keycode))
            return {"ok": True}
        except Exception as e:
            raise Exception(str(e))

    def send_input_text(self, host, port=5555, text=""):
        text = (text or "").strip()
        if not text:
            raise Exception("Nội dung trống")
        escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace(" ", "%s")
        dev = self._get_dev(host, int(port))
        try:
            dev.shell(f'input text "{escaped}"')
            return {"ok": True}
        except Exception as e:
            raise Exception(str(e))

    def device_shell(self, host, port=5555, command=""):
        command = (command or "").strip()
        if not command:
            raise Exception("Lệnh trống")
        dev = self._get_dev(host, int(port))
        try:
            out = dev.shell(command) or ""
            return {"output": out.strip()}
        except Exception as e:
            raise Exception(str(e))

    def list_apps(self, host, port=5555):
        with self._dev_op_lock(host, port):
            try:
                pm = self._get_pm(host, port)
                pkgs = pm.get_all_packages()
                current_home = pm.get_current_home()
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
            if p in user_set:
                ptype = "user"
            elif p in disabled_set:
                ptype = "disabled"
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
        return {"apps": result, "current_home": current_home}

    def _device_props(self, pm: PackageManager) -> tuple:
        try:
            brand = (pm._shell("getprop ro.product.manufacturer") or "").strip()
            model = (pm._shell("getprop ro.product.model") or "").strip()
            return brand, model
        except Exception:
            return "", ""

    def get_app_settings(self):
        return settings_store.public_settings()

    def save_app_settings(self, openai_api_key=None, openai_model=None):
        if openai_api_key is not None:
            settings_store.set_openai_api_key(openai_api_key)
        if openai_model:
            data = settings_store.load()
            data["openai_model"] = str(openai_model).strip() or "gpt-4o-mini"
            settings_store.save(data)
        return settings_store.public_settings()

    def test_openai_connection(self):
        key = settings_store.get_openai_api_key()
        if not key:
            raise Exception("Chưa lưu OpenAI API key")
        ai_clean.ping_openai(api_key=key)
        return {"ok": True}

    def smart_clean_suggest(self, host, port=5555, use_ai=False):
        listed = self.list_apps(host, port)
        apps = listed.get("apps") or []
        pm = self._get_pm(host, port)
        manufacturer, model = self._device_props(pm)
        suggestions = self._clean_engine.analyze(apps, manufacturer=manufacturer)
        ai_error = None
        if use_ai:
            key = settings_store.get_openai_api_key()
            if not key:
                ai_error = "Chưa lưu OpenAI API key — dùng gợi ý nhanh (offline) hoặc dán key bên dưới."
            else:
                try:
                    candidates = [
                        s["package"]
                        for s in suggestions
                        if s.get("enabled") and s.get("can_disable") and s.get("tier") != "blocked"
                    ]
                    pub = settings_store.public_settings()
                    ai_rows = ai_clean.suggest_with_openai(
                        api_key=key,
                        model=pub.get("openai_model") or "gpt-4o-mini",
                        manufacturer=manufacturer,
                        model_name=model,
                        packages=candidates,
                    )
                    suggestions = self._clean_engine.merge_ai(suggestions, ai_rows)
                except Exception as e:
                    ai_error = str(e)
        counts = {"recommend": 0, "review": 0, "skip": 0, "blocked": 0}
        for s in suggestions:
            counts[s.get("tier") or "skip"] = counts.get(s.get("tier") or "skip", 0) + 1
        return {
            "suggestions": suggestions,
            "manufacturer": manufacturer,
            "model": model,
            "current_home": listed.get("current_home"),
            "counts": counts,
            "ai_error": ai_error,
        }

    def smart_clean_apply(self, host, port=5555, packages=None):
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
            return {"ok": True}
        elif action == "disable":
            current_home = pm.get_current_home()
            allowed, reason = safety.can_disable(package, current_home=current_home)
            if not allowed:
                raise Exception(reason)
            pm.disable_user(package)
            return {"ok": True}
        raise Exception("Hành động không hợp lệ")

    def analyze_apk(self, filename="", data_base64="", host=None, port=5555):
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

    def detect_launcher(self, host, port=5555):
        dev = self._get_dev(host, port)
        det = LauncherDetector(dev)
        info = det.detect_gathin()
        disc = det.discover_config()
        return {"info": info, "discovery": disc}

    def _backup_root(self, host, port):
        root = os.path.join(store.KEY_DIR, "backups", f"{host}_{int(port)}")
        os.makedirs(root, exist_ok=True)
        return root

    def backup_launcher(self, host, port=5555):
        dev = self._get_dev(host, port)
        tm = ThemeManager(dev)
        return tm.backup_config(self._backup_root(host, port))

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
        dev = self._get_dev(host, port)
        return ThemeManager(dev).restore_backup(path)

    def reset_launcher(self, host, port=5555):
        dev = self._get_dev(host, port)
        tm = ThemeManager(dev)
        backup = tm.backup_config(self._backup_root(host, port))
        result = tm.reset()
        result["backup"] = backup
        return result

    def restart_launcher(self, host, port=5555):
        dev = self._get_dev(host, port)
        tm = ThemeManager(dev)
        return {"ok": tm.restart_launcher()}

    def current_launcher_theme(self, host, port=5555, include_wallpaper=True):
        dev = self._get_dev(host, port)
        tm = ThemeManager(dev)
        config = tm.read_config()
        revision = tm.read_revision()
        wallpapers = tm.list_wallpapers()
        wallpaper_b64 = None
        if include_wallpaper:
            wallpaper_b64 = tm.read_wallpaper_preview_b64()
        return {
            "config": config,
            "revision": revision,
            "wallpapers": wallpapers,
            "provider": tm.provider_supported(),
            "wallpaper_b64": wallpaper_b64,
            "has_overlay": bool(config) or bool(revision) or bool(wallpaper_b64),
        }

    def list_gathin_themes(self):
        themes = self._themes.list_themes()
        result = []
        for t in themes:
            screenshot_b64 = None
            if t.get("screenshot") and os.path.exists(t["screenshot"]):
                try:
                    with open(t["screenshot"], "rb") as f:
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
                "config": t.get("config") or {},
                "valid": check["ok"],
                "errors": check["errors"],
                "warnings": check["warnings"],
            })
        return result

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
        with self._dev_op_lock(host, port):
            self._drop_dev(host, port)
            on_step("adb_connect", f"{host}:{port}")
            dev = adb_client.connect(host, int(port))
            try:
                adb_client.ensure_connected(dev)
                tm = ThemeManager(dev, on_step=on_step)
                backup_root = self._backup_root(host, port)
                on_step("backup", "snapshot config (bỏ qua kéo wallpaper để nhanh hơn)")
                backup = tm.backup_config(backup_root, pull_assets=False)
                on_step("backup_done", backup.get("time") or "")
                try:
                    result = tm.apply_theme(theme)
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

    def apply_gathin_theme(self, host, port=5555, theme_id=""):
        steps = []
        job_id = uuid.uuid4().hex
        return self._apply_gathin_theme_impl(host, port, theme_id, job_id, steps)

    def apply_gathin_theme_async(self, host, port=5555, theme_id=""):
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


if __name__ == "__main__":
    api = Api()
    root = paths.app_root()
    ui_path = os.path.join(root, "ui", "index.html")
    icon_path = os.path.join(root, "ui", "assets", "app-icon.png")
    if os.name == "nt":
        ico = os.path.join(root, "assets", "app-icon.ico")
        if os.path.isfile(ico):
            icon_path = ico
    webview.create_window(
        APP_DISPLAY_NAME,
        ui_path,
        js_api=api,
        width=1280,
        height=820,
        resizable=True,
        background_color="#07090E",
    )
    start_kwargs = {"icon": icon_path} if os.path.isfile(icon_path) else {}
    webview.start(**start_kwargs)
