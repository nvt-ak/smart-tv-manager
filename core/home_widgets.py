"""Optional Home screen widgets — fetch on desktop, push via gathin.tvhome config.json.

CleanYourTV shows `greeting_name` beside the clock greeting and `show_stats` under it.
Market snippets are folded into `greeting_name` (short ticker) until the launcher
supports a dedicated board key.
"""
from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timedelta, timezone
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from . import vn_calendar, widget_sources

DEFAULT_WIDGETS: Dict[str, Any] = {
    "enabled": False,
    "display_name": "",
    "show_name": True,
    "show_gold": True,
    "show_fuel": True,
    "show_system_stats": False,
    "always_show_app_names": False,
    "module_cards": True,
    "widget_wallpaper": True,
    "show_weather": True,
    "show_lunar": True,
    "show_fx": True,
    "weather_city": "Hà Nội",
    "widget_layout": "compact",  # "compact" fits the default gap; "tall" is the full reference design
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
        "show_gold",
        "show_fuel",
        "show_system_stats",
        "always_show_app_names",
        "module_cards",
        "widget_wallpaper",
        "show_weather",
        "show_lunar",
        "show_fx",
    ):
        out[b] = bool(out.get(b))
    out["display_name"] = str(out.get("display_name") or "").strip()
    try:
        z = int(out.get("fuel_zone") or 1)
        out["fuel_zone"] = 2 if z == 2 else 1
    except (TypeError, ValueError):
        out["fuel_zone"] = 1
    city = str(out.get("weather_city") or "")
    out["weather_city"] = city if city in widget_sources.CITIES else widget_sources.DEFAULT_CITY
    out["widget_layout"] = "tall" if out.get("widget_layout") == "tall" else "compact"
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


_GOLD_NAME_VI = {
    "World Gold (XAU/USD)": "Vàng thế giới",
    "PNJ Hanoi": "PNJ Hà Nội",
    "PNJ 24K": "PNJ 24K",
    "DOJI Jewelry": "DOJI",
    "DOJI Hanoi": "DOJI Hà Nội",
    "DOJI HCM": "DOJI TP.HCM",
    "Bao Tin 9999": "Bảo Tín 9999",
    "Bao Tin SJC": "Bảo Tín SJC",
    "SJC Ring": "SJC nhẫn",
    "SJC 9999": "SJC 9999",
    "VN Gold SJC": "SJC (VNGold)",
    "Viettin SJC": "Viettin SJC",
}
_VN_TZ = timezone(timedelta(hours=7))


def _num(v: Any) -> Optional[float]:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def fetch_gold_all() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Mọi mục giá vàng vang.today trả về: mua, bán, thay đổi (không lọc)."""
    try:
        data = _http_json(VANG_TODAY_PRICES_URL)
        if not (data or {}).get("success"):
            raise RuntimeError("vang.today trả success=false")
        prices = (data or {}).get("prices") or {}
        items: List[Dict[str, Any]] = []
        world: Optional[Dict[str, Any]] = None
        for code, row in prices.items():
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or code).strip()
            item = {
                "code": code,
                "name": _GOLD_NAME_VI.get(name, name),
                "api_name": name,
                "buy": _num(row.get("buy")),
                "sell": _num(row.get("sell")),
                "change_buy": _num(row.get("change_buy")),
                "change_sell": _num(row.get("change_sell")),
                "currency": str(row.get("currency") or "VND").upper(),
            }
            if item["currency"] == "VND":
                items.append(item)
            else:
                world = world or item
        if not items and not world:
            return None, "vang.today không có mục giá nào"
        d, t = str((data or {}).get("date") or ""), str((data or {}).get("time") or "")
        try:
            d = datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            pass
        return {"updated": f"{t} {d}".strip(), "items": items, "world": world}, None
    except Exception as e:
        return None, f"Không lấy giá vàng (vang.today): {e}"


def _iso_to_vn(text: Any) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00")).astimezone(_VN_TZ)
    except (TypeError, ValueError):
        return None


def fetch_fuel_all(zone: int = 1) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Mọi mặt hàng xăng dầu Petrolimex (vùng 1 và 2); dự phòng VietFuel."""
    zone = 2 if zone == 2 else 1
    err_msgs: List[str] = []
    try:
        rows = _fetch_petrolimex_fuel_items()
        items: List[Dict[str, Any]] = []
        latest: Optional[datetime] = None
        for row in rows:
            if not isinstance(row, dict):
                continue
            p1, p2 = _num(row.get("Zone1Price")), _num(row.get("Zone2Price"))
            title = _fuel_row_title(row).strip()
            if not title or (p1 is None and p2 is None):
                continue
            items.append({"name": title, "price_z1": p1, "price_z2": p2,
                          "price": p2 if zone == 2 else p1})
            lm = _iso_to_vn(row.get("LastModified"))
            if lm and (latest is None or lm > latest):
                latest = lm
        if items:
            return {"zone": zone, "source": "Petrolimex", "items": items,
                    "updated": latest.strftime("%H:%M %d/%m/%Y") if latest else ""}, None
        err_msgs.append("Petrolimex trả danh sách rỗng")
    except Exception as e:
        err_msgs.append(str(e))
    try:
        data = _http_json(VIETFUEL_PRICES_URL)
        if not (data or {}).get("success"):
            raise RuntimeError("VietFuel trả success=false")
        items = []
        for row in (data or {}).get("data") or []:
            if not isinstance(row, dict):
                continue
            p1, p2 = _vietfuel_zone_price(row, 1), _vietfuel_zone_price(row, 2)
            name = _fuel_row_title(row).strip()
            if name and (p1 is not None or p2 is not None):
                items.append({"name": name, "price_z1": p1, "price_z2": p2,
                              "price": p2 if zone == 2 else p1})
        if items:
            meta = (data or {}).get("meta") or {}
            return {"zone": zone, "source": "VietFuel", "items": items,
                    "updated": str(meta.get("priceDateDisplay") or meta.get("priceDate") or "")}, None
        err_msgs.append("VietFuel trả danh sách rỗng")
    except Exception as e:
        err_msgs.append(str(e))
    return None, "Không lấy giá xăng dầu: " + " · ".join(err_msgs)


def widgets_data(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Dữ liệu đầy đủ cho widget (vàng + xăng dầu), kèm lỗi theo nguồn."""
    cfg = normalize_widgets(cfg)
    out: Dict[str, Any] = {"gold": None, "fuel": None, "errors": {},
                           "generated": datetime.now(_VN_TZ).strftime("%H:%M %d/%m/%Y")}
    out.update({"weather": None, "lunar": None, "fx": None, "layout": cfg["widget_layout"]})
    if cfg["show_weather"]:
        out["weather"], err = widget_sources.fetch_weather(cfg["weather_city"])
        if err:
            out["errors"]["weather"] = err
    if cfg["show_lunar"]:
        try:
            out["lunar"] = vn_calendar.lunar_card(datetime.now(_VN_TZ).date(), 2)
        except Exception as e:  # the calendar is offline, so this is a bug rather than an outage
            out["errors"]["lunar"] = f"Không tính được lịch âm: {e}"
    if cfg["show_fx"]:
        out["fx"], err = widget_sources.fetch_usd_vnd()
        if err:
            out["errors"]["fx"] = err
    if cfg["show_gold"]:
        out["gold"], err = fetch_gold_all()
        if err:
            out["errors"]["gold"] = err
    if cfg["show_fuel"]:
        out["fuel"], err = fetch_fuel_all(int(cfg.get("fuel_zone") or 1))
        if err:
            out["errors"]["fuel"] = err
    return out


def build_board_lines(cfg: Dict[str, Any]) -> Tuple[List[str], Dict[str, str]]:
    """Return display lines and per-source errors."""
    cfg = normalize_widgets(cfg)
    lines: List[str] = []
    errors: Dict[str, str] = {}

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
    # The launcher's own weather card reads the city and its position from the config.
    coords = widget_sources.CITIES.get(cfg.get("weather_city"))
    if coords:
        patch["weather_city"] = cfg["weather_city"]
        patch["weather_lat"], patch["weather_lon"] = coords
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


def wallpaper_mode(cfg: Dict[str, Any]) -> bool:
    """True when gold/fuel are drawn into the wallpaper instead of the greeting text."""
    cfg = normalize_widgets(cfg)
    cards = ("show_gold", "show_fuel", "show_weather", "show_lunar", "show_fx")
    return bool(cfg["enabled"] and cfg["widget_wallpaper"] and any(cfg[k] for k in cards))


def preview(cfg: Dict[str, Any]) -> Dict[str, Any]:
    cfg = normalize_widgets(cfg)
    if wallpaper_mode(cfg):
        board_lines, errors = [], {}
    else:
        board_lines, errors = build_board_lines(cfg)
    patch = launcher_config_patch(cfg, board_lines=board_lines)
    return {
        "board_lines": board_lines,
        "greeting_name": patch.get("greeting_name") or "",
        "launcher_patch": {k: v for k, v in patch.items() if v is not None},
        "errors": errors,
        "note": (
            "Các thẻ widget (thời tiết, lịch âm, giá cả) được vẽ vào ảnh nền (xem ảnh bên dưới); dòng chào chỉ giữ tên."
            if wallpaper_mode(cfg)
            else "Trên TV (SmartTV Home): ticker hiện gộp vào dòng chào (`greeting_name`)."
        ),
    }
