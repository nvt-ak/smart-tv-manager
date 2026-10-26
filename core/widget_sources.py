"""Weather and exchange-rate sources for the Home widgets (no API keys).

  * Weather: Open-Meteo forecast + air-quality APIs.
  * USD/VND: Vietcombank's public XML feed, with open.er-api.com as a fallback.

Every function returns (data, error); exactly one of them is None.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from . import vn_calendar

CITIES: Dict[str, Tuple[float, float]] = {
    "Hà Nội": (21.0285, 105.8542),
    "TP.HCM": (10.7769, 106.7009),
    "Đà Nẵng": (16.0544, 108.2022),
    "Hải Phòng": (20.8449, 106.6881),
    "Cần Thơ": (10.0452, 105.7469),
    "Huế": (16.4637, 107.5909),
    "Nha Trang": (12.2388, 109.1967),
    "Đà Lạt": (11.9404, 108.4583),
}
DEFAULT_CITY = "Hà Nội"

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
VCB_URL = "https://portal.vietcombank.com.vn/Usercontrols/TVPortal.TyGia/pXML.aspx"
ER_URL = "https://open.er-api.com/v6/latest/USD"

# WMO weather code -> (Vietnamese text, icon kind)
_WMO: List[Tuple[Tuple[int, ...], str, str]] = [
    ((0,), "Trời quang", "clear"),
    ((1,), "Ít mây", "partly"),
    ((2,), "Có mây", "partly"),
    ((3,), "Nhiều mây", "cloud"),
    ((45, 48), "Sương mù", "fog"),
    ((51, 53, 55, 56, 57), "Mưa phùn", "rain"),
    ((61, 63, 65, 66, 67), "Mưa", "rain"),
    ((71, 73, 75, 77, 85, 86), "Tuyết", "snow"),
    ((80, 81, 82), "Mưa rào", "rain"),
    ((95, 96, 99), "Dông", "storm"),
]


def describe_code(code: Any) -> Tuple[str, str]:
    try:
        c = int(code)
    except (TypeError, ValueError):
        return "Không rõ", "cloud"
    for codes, text, kind in _WMO:
        if c in codes:
            return text, kind
    return "Không rõ", "cloud"


def aqi_label(aqi: Optional[float]) -> str:
    """US AQI band, shortened for a small chip."""
    if aqi is None:
        return "-"
    for limit, text in ((50, "Tốt"), (100, "TB"), (150, "Kém"), (200, "Xấu"), (300, "Rất xấu")):
        if aqi <= limit:
            return text
    return "Nguy hại"


def uv_label(uv: Optional[float]) -> str:
    if uv is None:
        return "-"
    for limit, text in ((2.5, "Thấp"), (5.5, "TB"), (7.5, "Cao"), (10.5, "Rất cao")):
        if uv <= limit:
            return text
    return "Cực cao"


def _get(url: str) -> Any:
    from .home_widgets import _http_json  # shared TLS context and error text

    return _http_json(url)


def _get_text(url: str) -> str:
    from .home_widgets import _FETCH_TIMEOUT, _ssl_context

    req = urllib.request.Request(url, headers={"User-Agent": "SmartTV-Manager/1.8 home-widgets"})
    with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT, context=_ssl_context()) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_weather(city: str = DEFAULT_CITY) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    city = city if city in CITIES else DEFAULT_CITY
    lat, lon = CITIES[city]
    try:
        data = _get(
            f"{FORECAST_URL}?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,weather_code,is_day"
            "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
            "precipitation_probability_max,uv_index_max&timezone=Asia%2FBangkok&forecast_days=6"
        )
        cur, daily = data["current"], data["daily"]
        text, kind = describe_code(cur.get("weather_code"))
        out: Dict[str, Any] = {
            "city": city,
            "temp": cur.get("temperature_2m"),
            "humidity": cur.get("relative_humidity_2m"),
            "text": text,
            "kind": kind,
            "is_day": bool(cur.get("is_day", 1)),
            "high": daily["temperature_2m_max"][0],
            "low": daily["temperature_2m_min"][0],
            "rain_chance": daily["precipitation_probability_max"][0],
            "uv": daily["uv_index_max"][0],
            "aqi": None,
            "forecast": [],
        }
        for i in range(1, min(6, len(daily["time"]))):
            d = datetime.strptime(daily["time"][i], "%Y-%m-%d").date()
            _, k = describe_code(daily["weather_code"][i])
            out["forecast"].append({
                "label": vn_calendar.WEEKDAYS_SHORT[d.weekday()],
                "kind": k,
                "high": daily["temperature_2m_max"][i],
                "low": daily["temperature_2m_min"][i],
            })
    except Exception as e:
        return None, f"Không lấy thời tiết (Open-Meteo): {e}"
    try:  # air quality is a separate endpoint; the card still works without it
        air = _get(f"{AIR_URL}?latitude={lat}&longitude={lon}&current=us_aqi")
        out["aqi"] = air["current"].get("us_aqi")
    except Exception:
        pass
    return out, None


def _num(text: str) -> Optional[float]:
    try:
        return float(text.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def fetch_usd_vnd() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    errs: List[str] = []
    try:
        root = ET.fromstring(re.sub(r"^<!--.*?-->", "", _get_text(VCB_URL), flags=re.S).strip())
        for row in root.iter("Exrate"):
            if row.get("CurrencyCode") == "USD":
                buy, sell = _num(row.get("Buy", "")), _num(row.get("Sell", ""))
                if sell:
                    return {"source": "Vietcombank", "buy": buy, "sell": sell, "rate": sell}, None
        errs.append("VCB không có dòng USD")
    except Exception as e:
        errs.append(f"VCB: {e}")
    try:
        rate = _get(ER_URL)["rates"]["VND"]
        return {"source": "open.er-api.com", "buy": None, "sell": None, "rate": float(rate)}, None
    except Exception as e:
        errs.append(f"er-api: {e}")
    return None, "Không lấy tỷ giá USD/VND: " + " · ".join(errs)
