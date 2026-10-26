"""App settings in ~/.smarttv-manager/settings.json (API keys, preferences)."""
import json
import os

from adb_client import KEY_DIR

SETTINGS_PATH = os.path.join(KEY_DIR, "settings.json")
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


def load() -> dict:
    if not os.path.isfile(SETTINGS_PATH):
        return {}
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save(data: dict) -> None:
    os.makedirs(KEY_DIR, mode=0o700, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    try:
        os.chmod(SETTINGS_PATH, 0o600)
    except OSError:
        pass


def get_openai_api_key() -> str:
    return (load().get("openai_api_key") or "").strip()


def set_openai_api_key(key: str | None) -> None:
    data = load()
    key = (key or "").strip()
    if key:
        data["openai_api_key"] = key
    else:
        data.pop("openai_api_key", None)
    save(data)


def get_openai_base_url() -> str:
    raw = (load().get("openai_base_url") or "").strip()
    return raw or DEFAULT_OPENAI_BASE_URL


def set_openai_base_url(url: str | None) -> None:
    data = load()
    url = (url or "").strip()
    if url:
        data["openai_base_url"] = url
    else:
        data.pop("openai_base_url", None)
    save(data)


def get_openai_model() -> str:
    """Model đã lưu (có thể rỗng nếu user chưa chọn)."""
    return (load().get("openai_model") or "").strip()


def default_openai_model_for_base(base_url: str | None = None) -> str:
    """Chỉ gợi ý mặc định OpenAI chính thức; proxy/local để trống — bắt chọn sau Test Ping."""
    u = (base_url or get_openai_base_url() or "").strip().lower()
    if "api.openai.com" in u:
        return "gpt-4o-mini"
    return ""


def resolve_openai_model(
    *,
    explicit: str | None = None,
    base_url: str | None = None,
) -> str:
    m = (explicit or "").strip() or get_openai_model()
    if m:
        return m
    return default_openai_model_for_base(base_url)


def set_openai_model(model: str | None) -> None:
    data = load()
    model = (model or "").strip()
    if model:
        data["openai_model"] = model
    else:
        data.pop("openai_model", None)
    save(data)


def get_home_widgets() -> dict:
    from core import home_widgets

    return home_widgets.normalize_widgets(load().get("home_widgets"))


def set_home_widgets(updates: dict | None) -> dict:
    from core import home_widgets

    data = load()
    cur = home_widgets.normalize_widgets(data.get("home_widgets"))
    if updates:
        merged = {**cur, **updates}
        data["home_widgets"] = home_widgets.normalize_widgets(merged)
    else:
        data.pop("home_widgets", None)
    save(data)
    return get_home_widgets()


def public_settings() -> dict:
    data = load()
    key = get_openai_api_key()
    hint = ""
    if len(key) >= 8:
        hint = f"{key[:3]}…{key[-4:]}"
    return {
        "openai_configured": bool(key),
        "openai_key_hint": hint,
        "openai_model": resolve_openai_model(base_url=get_openai_base_url()),
        "openai_base_url": get_openai_base_url(),
        "home_widgets": get_home_widgets(),
    }


def get_launcher_sha(host: str) -> str:
    """SHA-256 of the SmartTV Home APK this app last installed on `host` ('' if never)."""
    rec = load().get("launcher_installed")
    return str(rec.get(host, "")) if isinstance(rec, dict) else ""


def set_launcher_sha(host: str, sha: str) -> None:
    data = load()
    rec = data.get("launcher_installed")
    rec = rec if isinstance(rec, dict) else {}
    rec[host] = sha
    data["launcher_installed"] = rec
    save(data)


def _device_key(host, port=5555) -> str:
    return f"{str(host or '').strip()}:{int(port or 5555)}"


def get_last_theme(host, port=5555) -> str:
    """The theme last applied on this TV. Never falls back to another TV's theme."""
    by_dev = load().get("last_theme_by_device")
    if not isinstance(by_dev, dict):
        return ""
    return str(by_dev.get(_device_key(host, port)) or "")


def set_last_theme(host, port, theme_id) -> None:
    data = load()
    by_dev = data.get("last_theme_by_device")
    if not isinstance(by_dev, dict):
        by_dev = {}
    by_dev[_device_key(host, port)] = str(theme_id or "")
    data["last_theme_by_device"] = by_dev
    # Kept as the default for the widget preview, which is not tied to a TV.
    data["last_theme_id"] = str(theme_id or "")
    save(data)
