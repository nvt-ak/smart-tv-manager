"""Per-theme switches for the dashboard widgets of the smtv-home launcher.

A theme whose config draws the launcher's own dashboard (``"dashboard": true``) can have each widget
turned off before it is applied. The choice is saved per theme in the app settings and written to the
TV as ``show_<name>`` keys in config.json; the launcher shows everything that is not switched off.
"""
from __future__ import annotations

# key -> (label, hint)
_WEATHER = ("show_weather", "Thời tiết", "Nhiệt độ, độ ẩm, gió, chất lượng không khí")
_GOLD = ("show_gold", "Giá vàng", "Vàng SJC, kèm mức tăng giảm")
_FUEL = ("show_fuel", "Giá xăng", "Xăng RON 95-III, kèm mức tăng giảm")
_PRICES = ("show_prices", "Giá vàng và xăng dầu", "Thẻ giá vàng, nhẫn, xăng, dầu")
_CALENDAR_MONTH = ("show_calendar", "Lịch tháng", "Lịch tháng và ngày âm lịch hôm nay")
_CALENDAR_LUNAR = ("show_calendar", "Lịch âm", "Thẻ lịch âm: can chi, giờ hoàng đạo")
_LUNAR_HEADER = ("show_lunar_header", "Âm lịch cạnh đồng hồ", "Ngày âm lịch và nhãn Hoàng Đạo")
_QUOTE = ("show_quote", "Câu chữ chủ đề", "Câu chào hoặc câu trích của theme")
_FOOTER = ("show_footer", "Chữ ở góc màn hình", "Các dòng chữ nhỏ cuối màn hình")

_BY_PROFILE = {
    "aurora": (_WEATHER, _CALENDAR_LUNAR, _PRICES, _QUOTE, _FOOTER),
    "hanoi": (_WEATHER, _CALENDAR_LUNAR, _PRICES, _QUOTE, _FOOTER),
    "hanoi2": (_WEATHER, _GOLD, _FUEL, _CALENDAR_MONTH, _LUNAR_HEADER, _QUOTE, _FOOTER),
}

KEYS = sorted({w[0] for ws in _BY_PROFILE.values() for w in ws})


def available(config: dict | None) -> list[dict]:
    """The switchable widgets of a theme config; empty when the theme has no dashboard of its own."""
    config = config or {}
    if not config.get("dashboard"):
        return []
    widgets = _BY_PROFILE.get(str(config.get("design_profile") or "").strip().lower(), ())
    return [{"key": k, "label": label, "hint": hint} for k, label, hint in widgets]


def resolve(config: dict | None, saved: dict | None) -> list[dict]:
    """available() plus ``enabled``: the saved choice, else what the theme's own config says, else on."""
    config = config or {}
    saved = saved if isinstance(saved, dict) else {}
    out = []
    for w in available(config):
        enabled = saved[w["key"]] if isinstance(saved.get(w["key"]), bool) else config.get(w["key"], True) is not False
        out.append({**w, "enabled": bool(enabled)})
    return out


def overrides(config: dict | None, saved: dict | None) -> dict:
    """The ``show_*`` keys to write on top of the theme's config; every switchable widget is spelled out."""
    return {w["key"]: w["enabled"] for w in resolve(config, saved)}


def clean(config: dict | None, values: dict | None) -> dict:
    """Only the booleans for widgets this theme really has."""
    allowed = {w["key"] for w in available(config)}
    return {k: v for k, v in (values or {}).items() if k in allowed and isinstance(v, bool)}
