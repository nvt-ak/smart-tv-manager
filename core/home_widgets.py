"""Optional Home screen widgets — fetch on desktop, push via gathin.tvhome config.json.

CleanYourTV shows `greeting_name` beside the clock greeting and `show_stats` under it.
Market/weather snippets are folded into `greeting_name` (short ticker) until the launcher
supports a dedicated board key.
"""
from __future__ import annotations

import base64
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_WIDGETS: Dict[str, Any] = {
    "enabled": False,
    "display_name": "",
    "show_name": True,
    "show_weather": True,
    "show_gold": True,
    "show_fuel": True,
    "show_system_stats": False,
    "always_show_app_names": False,
    "module_cards": True,
    "weather_use_location": True,
    "weather_city": "",
    "weather_lat": 21.0285,
    "weather_lon": 105.8542,
    "fuel_zone": 1,
    "fuel_ron95": "",
    "fuel_diesel": "",
    "manual_gold_sjc": "",
    "gold_vang_today_code": "VNGSJC",
}

MAX_GREETING_LEN = 72
_FETCH_TIMEOUT = 12.0
VANG_TODAY_PRICES_URL = "https://www.vang.today/api/prices"
# Ưu tiên mã SJC trên vang.today (JSON `prices.<code>`).
GOLD_VANG_TODAY_CODES = ("VNGSJC", "BTSJC", "VIETTINMSJC", "SJ9999")
VIETFUEL_PRICES_URL = "https://vietfuel-api.tranqui.workers.dev/api/fuel-prices"
PETROLIMEX_FUEL_SEARCH_URL = (
    "https://portals.petrolimex.com.vn/~apis/portals/cms.item/search"
)
PETROLIMEX_FUEL_FILTER: Dict[str, Any] = {
    "FilterBy": {
        "And": [
            {"SystemID": {"Equals": "6783dc1271ff449e95b74a9520964169"}},
            {"RepositoryID": {"Equals": "a95451e23b474fe5886bfb7cf843f53c"}},
            {"RepositoryEntityID": {"Equals": "3801378fe1e045b1afa10de7c5776124"}},
        ]
    }
}


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _friendly_url_error(err: urllib.error.URLError) -> str:
    reason = err.reason if isinstance(err.reason, BaseException) else err.reason
    text = str(reason or err)
    if "CERTIFICATE_VERIFY_FAILED" in text or "certificate verify failed" in text.lower():
        return (
            "Lỗi SSL (không xác minh được chứng chỉ). Trên macOS: "
            "pip install certifi trong venv, khởi động lại app; hoặc chạy "
            "«Install Certificates.command» trong thư mục cài Python."
        )
    return f"Không kết nối API: {err}"


def normalize_widgets(raw: Any) -> Dict[str, Any]:
    out = dict(DEFAULT_WIDGETS)
    if not isinstance(raw, dict):
        return out
    for key in DEFAULT_WIDGETS:
        if key in raw and raw[key] is not None:
            out[key] = raw[key]
    out["enabled"] = bool(out.get("enabled"))
    for b in (
        "show_name",
        "show_weather",
        "show_gold",
        "show_fuel",
        "show_system_stats",
        "always_show_app_names",
        "module_cards",
    ):
        out[b] = bool(out.get(b))
    out["display_name"] = str(out.get("display_name") or "").strip()
    out["weather_use_location"] = bool(
        out.get("weather_use_location", DEFAULT_WIDGETS["weather_use_location"])
    )
    out["weather_city"] = str(out.get("weather_city") or "").strip()
    try:
        out["weather_lat"] = float(out.get("weather_lat") or 21.0285)
        out["weather_lon"] = float(out.get("weather_lon") or 105.8542)
    except (TypeError, ValueError):
        out["weather_lat"], out["weather_lon"] = 21.0285, 105.8542
    try:
        z = int(out.get("fuel_zone") or 1)
        out["fuel_zone"] = 2 if z == 2 else 1
    except (TypeError, ValueError):
        out["fuel_zone"] = 1
    return out


def _http_json(url: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SmartTV-Manager/1.2 home-widgets"},
    )
    open_kw: dict = {"timeout": _FETCH_TIMEOUT}
    if url.startswith("https:"):
        open_kw["context"] = _ssl_context()
    try:
        with urllib.request.urlopen(req, **open_kw) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError as e:
        raise RuntimeError(_friendly_url_error(e)) from e


def _fmt_num(n: float, decimals: int = 1) -> str:
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.{decimals}f}M"
    if abs(n) >= 10_000:
        return f"{n / 1_000:.{decimals}f}k"
    return f"{n:.{decimals}f}"


def fetch_weather(lat: float, lon: float, city: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        q = urllib.parse.urlencode(
            {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code",
                "timezone": "auto",
            }
        )
        data = _http_json(f"https://api.open-meteo.com/v1/forecast?{q}")
        cur = (data or {}).get("current") or {}
        temp = cur.get("temperature_2m")
        if temp is None:
            return None, "Không đọc được nhiệt độ"
        label = city.split(",")[0].strip() or "Thời tiết"
        return f"{label} {float(temp):.0f}°C", None
    except Exception as e:
        return None, str(e)


def geocode_city(city: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    name = (city or "").strip()
    if not name:
        return None, None, "Thiếu tên thành phố"
    try:
        q = urllib.parse.urlencode({"name": name, "count": 1, "language": "vi"})
        data = _http_json(f"https://geocoding-api.open-meteo.com/v1/search?{q}")
        results = (data or {}).get("results") or []
        if not results:
            return None, None, f"Không tìm thấy «{name}»"
        hit = results[0]
        return float(hit["latitude"]), float(hit["longitude"]), None
    except Exception as e:
        return None, None, str(e)


def reverse_geocode(lat: float, lon: float) -> Tuple[str, Optional[str]]:
    """Human label for coordinates (Open-Meteo reverse geocoding)."""
    try:
        q = urllib.parse.urlencode(
            {"latitude": lat, "longitude": lon, "language": "vi", "count": 1}
        )
        data = _http_json(f"https://geocoding-api.open-meteo.com/v1/reverse?{q}")
        results = (data or {}).get("results") or []
        if not results:
            return f"{lat:.2f}°, {lon:.2f}°", None
        hit = results[0]
        name = (hit.get("name") or hit.get("admin1") or "").strip()
        return name or f"{lat:.2f}°, {lon:.2f}°", None
    except Exception as e:
        return f"{lat:.2f}°, {lon:.2f}°", str(e)


def weather_place_label(cfg: Dict[str, Any]) -> str:
    cfg = normalize_widgets(cfg)
    city = (cfg.get("weather_city") or "").strip()
    if city:
        return city.split(",")[0].strip()
    label, _ = reverse_geocode(cfg["weather_lat"], cfg["weather_lon"])
    return label.split(",")[0].strip() or "Thời tiết"


def _format_vnd_per_luong(amount: float) -> str:
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.2f}tr"
    return f"{amount:,.0f}đ".replace(",", ".")


def fetch_gold_sjc(manual: str = "", gold_code: str = "VNGSJC") -> Tuple[Optional[str], Optional[str]]:
    """Giá vàng VN qua https://www.vang.today/api/prices (không cần API key)."""
    manual = (manual or "").strip()
    preferred = (gold_code or "VNGSJC").strip().upper()
    codes: List[str] = []
    if preferred:
        codes.append(preferred)
    for c in GOLD_VANG_TODAY_CODES:
        if c not in codes:
            codes.append(c)
    try:
        data = _http_json(VANG_TODAY_PRICES_URL)
        if not (data or {}).get("success"):
            raise RuntimeError("vang.today trả success=false")
        prices = (data or {}).get("prices") or {}
        for code in codes:
            row = prices.get(code)
            if not isinstance(row, dict):
                continue
            if (row.get("currency") or "").upper() != "VND":
                continue
            sell = row.get("sell") or row.get("buy")
            if sell is None or float(sell) <= 0:
                continue
            label = (row.get("name") or code).strip()
            if "SJC" in code or "sjc" in label.lower():
                short = "SJC"
            else:
                short = label.split()[0] if label else code
            price = float(sell)
            return f"Vàng {short} bán {_format_vnd_per_luong(price)}/l", None
    except Exception as e:
        if manual:
            return f"Vàng SJC {manual}", None
        return None, f"Không lấy giá vàng (vang.today): {e}"
    if manual:
        return f"Vàng SJC {manual}", None
    return None, "Không tìm thấy mã vàng trên vang.today"


def _format_vnd_per_liter(amount: float) -> str:
    return f"{int(round(amount)):,}".replace(",", ".") + "đ"


def _vietfuel_zone_price(row: Dict[str, Any], zone: int) -> Optional[float]:
    if zone == 2:
        raw = row.get("region2", row.get("zone2"))
    else:
        raw = row.get("region1", row.get("zone1"))
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _fuel_row_title(row: Dict[str, Any]) -> str:
    return str(row.get("Title") or row.get("name") or "")


def _pick_fuel_row(items: List[Dict[str, Any]], kind: str) -> Optional[Dict[str, Any]]:
    """kind: ron95 | diesel"""
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        name = _fuel_row_title(row).lower()
        score = 0
        if kind == "ron95":
            if "ron 95-v" in name or "ron95-v" in name:
                score = 100
            elif "e10 ron 95" in name or "ron 95-iii" in name:
                score = 80
            elif "ron 95" in name:
                score = 60
            elif "ron95" in name:
                score = 50
        elif kind == "diesel":
            if "do 0,05" in name or "do 0.05" in name or "0,05s" in name:
                score = 100
            elif "do 0,001" in name or "dầu diezen" in name or "diesel" in name:
                score = 70
            elif name.startswith("do ") or " dầu " in f" {name} ":
                score = 40
        if score > 0:
            scored.append((score, row))
    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    return scored[0][1]


def _petrolimex_x_request_query() -> str:
    """Base64url filter giống lệnh curl Petrolimex (jq | base64 | tr)."""
    raw = json.dumps(PETROLIMEX_FUEL_FILTER, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _petrolimex_zone_price(row: Dict[str, Any], zone: int) -> Optional[float]:
    key = "Zone2Price" if zone == 2 else "Zone1Price"
    raw = row.get(key)
    if raw is None:
        return _vietfuel_zone_price(row, zone)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _fetch_petrolimex_fuel_items() -> List[Dict[str, Any]]:
    q = urllib.parse.urlencode({"x-request": _petrolimex_x_request_query()})
    url = f"{PETROLIMEX_FUEL_SEARCH_URL}?{q}"
    data = _http_json(url)
    items = (data or {}).get("Objects") or []
    if not isinstance(items, list):
        return []
    return sorted(
        items,
        key=lambda x: (x.get("DIsplayOrder") if isinstance(x, dict) else 0)
        or (x.get("DisplayOrder") if isinstance(x, dict) else 0)
        or 0,
    )


def fetch_fuel_petrolimex(zone: int = 1) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    try:
        items = _fetch_petrolimex_fuel_items()
        if not items:
            return None, "Petrolimex trả danh sách rỗng"
        return items, None
    except Exception as e:
        return None, str(e)


def _fuel_line_from_items(
    items: List[Dict[str, Any]],
    zone: int,
    *,
    source_label: str,
    date_hint: str = "",
) -> Optional[str]:
    zone = 2 if zone == 2 else 1
    parts: List[str] = []
    ron_row = _pick_fuel_row(items, "ron95")
    die_row = _pick_fuel_row(items, "diesel")
    if ron_row:
        p = _petrolimex_zone_price(ron_row, zone)
        if p is not None:
            parts.append(f"RON95 {_format_vnd_per_liter(p)}/l")
    if die_row:
        p = _petrolimex_zone_price(die_row, zone)
        if p is not None:
            parts.append(f"Diesel {_format_vnd_per_liter(p)}/l")
    if not parts:
        return None
    suffix = f" (V{zone}"
    if date_hint:
        suffix += f", {date_hint}"
    suffix += f", {source_label})"
    return "Xăng dầu · " + " · ".join(parts) + suffix


def fetch_fuel_vietfuel(
    zone: int = 1,
    *,
    manual_ron: str = "",
    manual_diesel: str = "",
) -> Tuple[Optional[str], Optional[str]]:
    """Giá xăng dầu Petrolimex (tổng hợp) — VietFuelAPI, không cần key."""
    manual_ron = (manual_ron or "").strip()
    manual_diesel = (manual_diesel or "").strip()
    zone = 2 if zone == 2 else 1
    try:
        data = _http_json(VIETFUEL_PRICES_URL)
        if not (data or {}).get("success"):
            raise RuntimeError("VietFuel trả success=false")
        items = (data or {}).get("data") or []
        if not isinstance(items, list):
            items = []
        parts: List[str] = []
        ron_row = _pick_fuel_row(items, "ron95")
        die_row = _pick_fuel_row(items, "diesel")
        if ron_row:
            p = _vietfuel_zone_price(ron_row, zone)
            if p is not None:
                parts.append(f"RON95 {_format_vnd_per_liter(p)}/l")
        if die_row:
            p = _vietfuel_zone_price(die_row, zone)
            if p is not None:
                parts.append(f"Diesel {_format_vnd_per_liter(p)}/l")
        if parts:
            meta = (data or {}).get("meta") or {}
            date = meta.get("priceDateDisplay") or meta.get("priceDate") or ""
            suffix = f" (V{zone}" + (f", {date})" if date else ")")
            return "Xăng dầu · " + " · ".join(parts) + suffix, None
        raise RuntimeError("Không parse được mặt hàng xăng/dầu trong JSON")
    except Exception as e:
        fallback: List[str] = []
        if manual_ron:
            fallback.append(f"RON95 {manual_ron}")
        if manual_diesel:
            fallback.append(f"Diesel {manual_diesel}")
        if fallback:
            return "Xăng dầu · " + " · ".join(fallback), None
        return None, f"Không lấy giá xăng (VietFuel): {e}"


def fetch_fuel(
    zone: int = 1,
    *,
    manual_ron: str = "",
    manual_diesel: str = "",
) -> Tuple[Optional[str], Optional[str]]:
    """Petrolimex CMS (chính thống), fallback VietFuelAPI."""
    zone = 2 if zone == 2 else 1
    items, plx_err = fetch_fuel_petrolimex(zone)
    if items:
        date_hint = ""
        for row in items:
            if isinstance(row, dict) and row.get("LastModified"):
                date_hint = str(row.get("LastModified"))[:10]
                break
        line = _fuel_line_from_items(
            items, zone, source_label="Petrolimex", date_hint=date_hint
        )
        if line:
            return line, None
    line, vf_err = fetch_fuel_vietfuel(
        zone, manual_ron=manual_ron, manual_diesel=manual_diesel
    )
    if line:
        return line, None
    err = plx_err or vf_err or "Không lấy được giá xăng dầu"
    manual_ron = (manual_ron or "").strip()
    manual_diesel = (manual_diesel or "").strip()
    fallback: List[str] = []
    if manual_ron:
        fallback.append(f"RON95 {manual_ron}")
    if manual_diesel:
        fallback.append(f"Diesel {manual_diesel}")
    if fallback:
        return "Xăng dầu · " + " · ".join(fallback), None
    return None, err


def build_board_lines(cfg: Dict[str, Any]) -> Tuple[List[str], Dict[str, str]]:
    """Return display lines and per-source errors."""
    cfg = normalize_widgets(cfg)
    lines: List[str] = []
    errors: Dict[str, str] = {}

    if cfg["show_weather"]:
        line, err = fetch_weather(
            cfg["weather_lat"],
            cfg["weather_lon"],
            weather_place_label(cfg),
        )
        if line:
            lines.append(line)
        elif err:
            errors["weather"] = err

    if cfg["show_gold"]:
        line, err = fetch_gold_sjc(
            str(cfg.get("manual_gold_sjc") or ""),
            gold_code=str(cfg.get("gold_vang_today_code") or "VNGSJC"),
        )
        if line:
            lines.append(line)
        elif err:
            errors["gold"] = err

    if cfg["show_fuel"]:
        line, err = fetch_fuel(
            int(cfg.get("fuel_zone") or 1),
            manual_ron=str(cfg.get("fuel_ron95") or ""),
            manual_diesel=str(cfg.get("fuel_diesel") or ""),
        )
        if line:
            lines.append(line)
        elif err:
            errors["fuel"] = err

    return lines, errors


def build_greeting_name(cfg: Dict[str, Any], board_lines: Optional[List[str]] = None) -> str:
    cfg = normalize_widgets(cfg)
    parts: List[str] = []
    if cfg["show_name"] and cfg["display_name"]:
        parts.append(cfg["display_name"])
    if board_lines is None:
        board_lines, _ = build_board_lines(cfg)
    ticker = " · ".join(board_lines)
    if ticker:
        parts.append(ticker)
    text = " · ".join(parts).strip()
    if len(text) > MAX_GREETING_LEN:
        text = text[: MAX_GREETING_LEN - 1].rstrip() + "…"
    return text


def launcher_config_patch(cfg: Dict[str, Any], board_lines: Optional[List[str]] = None) -> Dict[str, Any]:
    cfg = normalize_widgets(cfg)
    patch: Dict[str, Any] = {}
    if not cfg["enabled"]:
        return patch

    greeting = build_greeting_name(cfg, board_lines=board_lines)
    if greeting:
        patch["greeting_name"] = greeting
    else:
        patch["greeting_name"] = None

    patch["show_stats"] = bool(cfg["show_system_stats"])
    patch["always_show_names"] = bool(cfg["always_show_app_names"])
    patch["module_cards"] = bool(cfg["module_cards"])
    return patch


def board_payload(cfg: Dict[str, Any], board_lines: Optional[List[str]] = None) -> Dict[str, Any]:
    if board_lines is None:
        board_lines, errors = build_board_lines(cfg)
    else:
        _, errors = build_board_lines(cfg)
    return {
        "version": 1,
        "lines": board_lines,
        "greeting_name": build_greeting_name(cfg, board_lines=board_lines),
        "errors": errors,
    }


def preview(cfg: Dict[str, Any]) -> Dict[str, Any]:
    cfg = normalize_widgets(cfg)
    board_lines, errors = build_board_lines(cfg)
    patch = launcher_config_patch(cfg, board_lines=board_lines)
    return {
        "board_lines": board_lines,
        "greeting_name": patch.get("greeting_name") or "",
        "launcher_patch": {k: v for k, v in patch.items() if v is not None},
        "errors": errors,
        "note": (
            "Trên TV (CleanYourTV): ticker hiện gộp vào dòng chào (`greeting_name`). "
            "Thời tiết chi tiết: cài add-on Weather trên TV và bật Module cards."
        ),
    }
