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
    return (load().get("openai_model") or "").strip() or "gpt-4o-mini"


def set_openai_model(model: str | None) -> None:
    data = load()
    model = (model or "").strip()
    if model:
        data["openai_model"] = model
    else:
        data.pop("openai_model", None)
    save(data)


def public_settings() -> dict:
    data = load()
    key = get_openai_api_key()
    hint = ""
    if len(key) >= 8:
        hint = f"{key[:3]}…{key[-4:]}"
    return {
        "openai_configured": bool(key),
        "openai_key_hint": hint,
        "openai_model": get_openai_model(),
        "openai_base_url": get_openai_base_url(),
    }
