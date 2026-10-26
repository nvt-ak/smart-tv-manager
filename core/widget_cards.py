"""Dashboard cards (weather, lunar calendar, prices) drawn onto the Home wallpaper.

Layout follows the reference design: three dark panels in one row. The launcher has no widget
surface, so these are pixels in the wallpaper: the data is as fresh as the last time the app
pushed a theme, and the cards are not clickable.

Two sizes share one code path:
  * tall    (region 460 px high): weather with forecast, three upcoming events, full price list;
  * compact (region 276 px high): what fits between the clock row and the app row on a TV that
    leaves less room; fonts stay the same size, so less content is shown.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

from . import widget_render as wr

TALL_REGION = (97, 246, 1823, 706)
COMPACT_REGION = (112, 236, 1808, 512)
WEIGHTS = {"weather": 1.5, "lunar": 1.0, "prices": 1.0}
GAP = 33

WHITE = (255, 255, 255)
MUTED = (148, 156, 170)
MUTED2 = (112, 120, 134)
ACCENT = (255, 84, 70)
CHIP = (255, 255, 255, 16)
LINE = 22


GLASS_TINT = (24, 14, 20)  # dark, slightly warm so crimson wallpapers glow through
GLASS_OPACITY = 0.46       # lower = more see-through; text stays readable down to ~0.35


def _diagonal(w: int, h: int) -> Image.Image:
    """Ramp from 0 at the top-left corner to 255 at the bottom-right, edge to edge.

    Rotating a gradient by 45 degrees instead leaves a rotated square: its empty corners show up as dark
    triangles across every card.
    """
    down = Image.linear_gradient("L").resize((w, h)).point(lambda v: v // 2)
    right = Image.linear_gradient("L").rotate(90).resize((w, h)).point(lambda v: v // 2)
    return ImageChops.add(down, right)


def _frosted(canvas: Image.Image, box, radius: int, s: float) -> None:
    """Glassmorphism panel: blurred and saturated backdrop, translucent tint, diagonal sheen,
    and a light-catching border that is brighter at the top-left edge."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    mask = wr._rounded_mask((w, h), radius)

    # Soft drop shadow so the pane lifts off the wallpaper.
    pad = round(44 * s)
    sh = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    ImageDraw.Draw(sh).rounded_rectangle(
        (pad, pad + round(16 * s), pad + w, pad + h + round(16 * s)), radius, fill=120)
    sh = sh.filter(ImageFilter.GaussianBlur(round(26 * s)))
    canvas.paste(Image.new("RGB", sh.size, (0, 0, 0)), (x0 - pad, y0 - pad), sh)

    # Backdrop: blur, then boost colour so the wallpaper reads through the frosting.
    back = canvas.crop(box).filter(ImageFilter.GaussianBlur(20 * s))
    back = ImageEnhance.Color(back).enhance(1.5)
    back = ImageEnhance.Brightness(back).enhance(1.12)
    pane = Image.blend(back, Image.new("RGB", back.size, GLASS_TINT), GLASS_OPACITY)

    # Diagonal sheen: white fading from the top-left corner, like light on a glass edge.
    sheen = _diagonal(w, h)
    sheen = sheen.point(lambda v: int(max(0, 255 - v * 1.7) * 0.15))
    pane = Image.composite(Image.new("RGB", pane.size, (255, 255, 255)), pane, sheen)
    canvas.paste(pane, (x0, y0), mask)

    # Border: bright top-left to faint bottom-right.
    k = 4
    ring = Image.new("L", (w * k, h * k), 0)
    rd = ImageDraw.Draw(ring)
    bw = max(1, round(2 * s)) * k
    rd.rounded_rectangle((0, 0, w * k - 1, h * k - 1), radius * k, fill=255)
    rd.rounded_rectangle((bw, bw, w * k - 1 - bw, h * k - 1 - bw), max(1, radius * k - bw), fill=0)
    ring = ring.resize((w, h), Image.LANCZOS)
    fall = _diagonal(w, h).point(lambda v: 40 + int((255 - v) * 0.45))
    ring = ImageChops.multiply(ring, fall)
    canvas.paste(Image.new("RGB", (w, h), (255, 255, 255)), (x0, y0), ring)


def _fit(d: ImageDraw.ImageDraw, text: str, font, maxw: float) -> str:
    while d.textlength(text, font=font) > maxw and len(text) > 2:
        text = text[:-2].rstrip() + "…"
    return text


def _num(v: Optional[float], digits: int = 0) -> str:
    if v is None:
        return "-"
    return f"{v:.{digits}f}".replace(".", ",")


def _vnd(v: Optional[float]) -> str:
    return "-" if v is None else f"{int(round(v)):,}".replace(",", ".")


def _trieu(v: Optional[float]) -> str:
    return "-" if not v else f"{v / 1e6:.1f}".replace(".", ",")


# ------------------------------------------------------------------ icons


def _cloud(d: ImageDraw.ImageDraw, cx: float, cy: float, w: float, fill) -> None:
    r = w * 0.26
    d.ellipse((cx - w * 0.5, cy - r * 0.2, cx - w * 0.5 + 2 * r, cy - r * 0.2 + 2 * r), fill=fill)
    d.ellipse((cx + w * 0.5 - 2 * r, cy - r * 0.2, cx + w * 0.5, cy - r * 0.2 + 2 * r), fill=fill)
    R = w * 0.30
    d.ellipse((cx - R * 0.95, cy - R * 1.15, cx + R * 0.35, cy + R * 0.15 + R * 0.4), fill=fill)
    R2 = w * 0.22
    d.ellipse((cx - R2 * 0.1, cy - R2 * 1.5, cx + R2 * 1.9, cy + R2 * 0.5), fill=fill)
    d.rounded_rectangle((cx - w * 0.5 + r * 0.6, cy + r * 0.2, cx + w * 0.5 - r * 0.6, cy - r * 0.2 + 2 * r), r, fill=fill)


def weather_icon(canvas: Image.Image, cx: int, cy: int, size: int, kind: str, is_day: bool = True) -> None:
    k = 4
    n = size * k
    lay = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    c = n / 2
    sun = (255, 196, 40, 255)
    cloud = (226, 231, 240, 255)
    dark_cloud = (170, 180, 196, 255)

    def sun_at(x, y, r):
        d.ellipse((x - r, y - r, x + r, y + r), fill=sun)
        for i in range(8):
            a = i * math.pi / 4
            d.line((x + math.cos(a) * r * 1.45, y + math.sin(a) * r * 1.45,
                    x + math.cos(a) * r * 1.95, y + math.sin(a) * r * 1.95), fill=sun, width=max(2, int(r * 0.28)))

    def moon_at(x, y, r):
        d.ellipse((x - r, y - r, x + r, y + r), fill=(238, 232, 190, 255))
        cut = Image.new("L", (n, n), 0)
        ImageDraw.Draw(cut).ellipse((x - r * 0.55, y - r * 1.1, x + r * 1.45, y + r * 0.9), fill=255)
        lay.paste((0, 0, 0, 0), (0, 0), cut)

    if kind == "clear":
        (sun_at if is_day else moon_at)(c, c, n * 0.22)
    elif kind == "partly":
        (sun_at if is_day else moon_at)(c - n * 0.14, c - n * 0.14, n * 0.15)
        _cloud(d, c + n * 0.06, c + n * 0.14, n * 0.72, cloud)
    elif kind == "fog":
        for i, y in enumerate((0.36, 0.5, 0.64)):
            w = (0.7, 0.82, 0.6)[i]
            d.rounded_rectangle((c - n * w / 2, n * y - n * 0.03, c + n * w / 2, n * y + n * 0.03), n * 0.03, fill=(176, 186, 198, 255))
    else:
        _cloud(d, c, c - n * 0.06, n * 0.78, dark_cloud if kind in ("rain", "storm") else cloud)
        if kind == "rain":
            for i in range(3):
                x = c - n * 0.2 + i * n * 0.2
                d.line((x, c + n * 0.2, x - n * 0.07, c + n * 0.38), fill=(96, 176, 255, 255), width=max(2, int(n * 0.045)))
        elif kind == "storm":
            d.polygon([(c + n * 0.02, c + n * 0.12), (c - n * 0.1, c + n * 0.34), (c, c + n * 0.34),
                       (c - n * 0.06, c + n * 0.5), (c + n * 0.14, c + n * 0.26), (c + n * 0.04, c + n * 0.26)],
                      fill=(255, 208, 56, 255))
        elif kind == "snow":
            for i in range(3):
                x = c - n * 0.2 + i * n * 0.2
                d.ellipse((x - n * 0.035, c + n * 0.26, x + n * 0.035, c + n * 0.33), fill=WHITE + (255,))
    lay = lay.resize((size, size), Image.Resampling.LANCZOS)
    canvas.paste(lay, (cx - size // 2, cy - size // 2), lay)


def _pin(d: ImageDraw.ImageDraw, x: float, y: float, h: float, color) -> None:
    r = h * 0.36
    d.ellipse((x - r, y - h / 2, x + r, y - h / 2 + 2 * r), outline=color, width=max(2, round(h * 0.11)))
    d.polygon([(x - r * 0.78, y - h / 2 + r * 1.55), (x + r * 0.78, y - h / 2 + r * 1.55), (x, y + h / 2)], outline=None, fill=color)
    d.ellipse((x - r * 0.35, y - h / 2 + r * 0.65, x + r * 0.35, y - h / 2 + r * 1.35), fill=(20, 22, 28))


# ------------------------------------------------------------------ cards


def card_weather(canvas: Image.Image, box, w: Dict[str, Any], s: float, tall: bool) -> None:
    _frosted(canvas, box, round(36 * s), s)
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(canvas, "RGBA")
    S = lambda v: round(v * s)  # noqa: E731
    pad = S(36)
    cy = y0 + S(40)
    _pin(d, x0 + pad + S(8), cy, S(26), WHITE)
    d.text((x0 + pad + S(32), cy), w.get("city", ""), font=wr._font(600, S(26)), fill=WHITE, anchor="lm")
    d.text((x1 - pad, cy), "Thời tiết", font=wr._font(400, S(22)), fill=MUTED, anchor="rm")

    row_cy = y0 + (S(116) if tall else S(112))
    icon = S(84 if tall else 80)
    weather_icon(canvas, x0 + pad + icon // 2, row_cy, icon, w.get("kind", "cloud"), w.get("is_day", True))
    temp = f"{_num(w.get('temp'))}°"
    tf = wr._font(400, S(100 if tall else 92))
    tx = x0 + pad + icon + S(18)
    d.text((tx, row_cy + S(4)), temp, font=tf, fill=WHITE, anchor="lm")
    cx = tx + d.textlength(temp, font=tf) + S(24)
    avail = x1 - pad - cx
    d.text((cx, row_cy - S(16)), _fit(d, w.get("text", ""), wr._font(600, S(36)), avail), font=wr._font(600, S(36)), fill=WHITE, anchor="lm")
    hl = f"Cao {_num(w.get('high'))}° · Thấp {_num(w.get('low'))}°"
    d.text((cx, row_cy + S(24)), _fit(d, hl, wr._font(400, S(24)), avail), font=wr._font(400, S(24)), fill=MUTED, anchor="lm")

    chip_h = S(66 if tall else 62)
    chip_y = y0 + S(192) if tall else y1 - S(24) - chip_h
    aqi, uv = w.get("aqi"), w.get("uv")
    chips = [
        ("Khả năng mưa", f"{_num(w.get('rain_chance'))}%"),
        ("Độ ẩm", f"{_num(w.get('humidity'))}%"),
        ("Không khí AQI", f"{_num(aqi)} · {_aqi_text(aqi)}" if aqi is not None else "-"),
        ("Chỉ số UV", f"{_num(uv)} · {_uv_text(uv)}" if uv is not None else "-"),
    ]
    gap = S(12)
    cw = (x1 - x0 - 2 * pad + S(0) - 3 * gap) / 4
    lf, vf = wr._font(400, S(19)), wr._font(600, S(26))
    for i, (label, value) in enumerate(chips):
        cx0 = x0 + pad + i * (cw + gap)
        d.rounded_rectangle((cx0, chip_y, cx0 + cw, chip_y + chip_h), S(14), fill=CHIP)
        d.text((cx0 + S(12), chip_y + chip_h * 0.30), _fit(d, label, lf, cw - S(20)), font=lf, fill=MUTED, anchor="lm")
        d.text((cx0 + S(12), chip_y + chip_h * 0.72), _fit(d, value, vf, cw - S(20)), font=vf, fill=WHITE, anchor="lm")

    if tall and w.get("forecast"):
        fy = y0 + S(284)
        wr._hline(d, x0 + pad, x1 - pad, fy, LINE, s)
        days = w["forecast"][:5]
        colw = (x1 - x0 - 2 * pad) / max(1, len(days))
        for i, f in enumerate(days):
            fx = x0 + pad + i * colw
            if i:
                d.line((fx, fy + S(14), fx, y1 - S(24)), fill=(255, 255, 255, 12), width=max(1, S(1)))
            mid = fx + colw / 2
            d.text((fx + S(2), fy + S(36)), f["label"], font=wr._font(600, S(22)), fill=MUTED, anchor="lm")
            weather_icon(canvas, round(mid), fy + S(86), S(40), f.get("kind", "cloud"))
            hi = f"{_num(f['high'])}°"
            lo = f" / {_num(f['low'])}°"
            hf, lf2 = wr._font(600, S(25)), wr._font(400, S(25))
            total = d.textlength(hi, font=hf) + d.textlength(lo, font=lf2)
            sx = mid - total / 2
            d.text((sx, fy + S(134)), hi, font=hf, fill=WHITE, anchor="lm")
            d.text((sx + d.textlength(hi, font=hf), fy + S(134)), lo, font=lf2, fill=MUTED, anchor="lm")


def _aqi_text(aqi: Optional[float]) -> str:
    from .widget_sources import aqi_label

    return aqi_label(aqi)


def _uv_text(uv: Optional[float]) -> str:
    from .widget_sources import uv_label

    return uv_label(uv)


def card_lunar(canvas: Image.Image, box, lc: Dict[str, Any], s: float, tall: bool) -> None:
    _frosted(canvas, box, round(36 * s), s)
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(canvas, "RGBA")
    S = lambda v: round(v * s)  # noqa: E731
    pad = S(36)
    d.text((x0 + pad, y0 + S(40)), "Lịch âm", font=wr._font(400, S(22)), fill=MUTED, anchor="lm")
    big = wr._font(700, S(112 if tall else 78))
    num = str(lc["lunar_day"])
    big_cy = y0 + (S(122) if tall else S(94))
    d.text((x0 + pad, big_cy), num, font=big, fill=ACCENT, anchor="lm")
    tx = x0 + pad + d.textlength(num, font=big) + S(26)
    month = f"Tháng {lc['lunar_month']}" + (" nhuận" if lc.get("leap") else "")
    d.text((tx, big_cy - S(14 if tall else 12)), month, font=wr._font(600, S(36 if tall else 30)), fill=WHITE, anchor="lm")
    d.text((tx, big_cy + S(24 if tall else 20)), _fit(d, f"Năm {lc['year_name']}", wr._font(400, S(24 if tall else 21)), x1 - pad - tx),
           font=wr._font(400, S(24 if tall else 21)), fill=MUTED, anchor="lm")

    line_y = y0 + (S(196) if tall else S(144))
    wr._hline(d, x0 + pad, x1 - pad, line_y, LINE, s)
    events: List[Dict[str, Any]] = list(lc.get("events") or [])[: 3 if tall else 2]
    pitch = S(80 if tall else 60)
    nf, sf, pf = wr._font(600, S(24 if tall else 23)), wr._font(400, S(20 if tall else 19)), wr._font(600, S(20 if tall else 19))
    for i, ev in enumerate(events):
        top = line_y + S(2) + i * pitch
        mid = top + pitch / 2
        pill = ev["relative"]
        pw, ph = d.textlength(pill, font=pf) + S(26), S(38 if tall else 34)
        d.rounded_rectangle((x1 - pad - pw, mid - ph / 2, x1 - pad, mid + ph / 2), ph / 2,
                            fill=ACCENT + (255,) if ev.get("soon") else (255, 255, 255, 24))
        d.text((x1 - pad - pw / 2, mid), pill, font=pf, fill=WHITE if ev.get("soon") else (225, 228, 235), anchor="mm")
        room = pw + S(14)
        d.text((x0 + pad, mid - S(12 if tall else 11)), _fit(d, ev["name"], nf, x1 - x0 - 2 * pad - room), font=nf, fill=WHITE, anchor="lm")
        d.text((x0 + pad, mid + S(17 if tall else 15)), ev["label"], font=sf, fill=MUTED, anchor="lm")
        if i < len(events) - 1:
            wr._hline(d, x0 + pad, x1 - pad, top + pitch, 12, s)


def _pick_gold(gold: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    items = list(gold.get("items") or [])
    by_code = {it.get("code"): it for it in items}
    out: List[Tuple[str, Dict[str, Any]]] = []
    sjc = by_code.get("SJL1L10") or next((i for i in items if "sjc" in str(i.get("api_name", "")).lower()), None)
    if sjc:
        out.append(("Vàng miếng SJC", sjc))
    ring = by_code.get("SJ9999") or next((i for i in items if "ring" in str(i.get("api_name", "")).lower() or "9999" in str(i.get("api_name", ""))
                                          and i is not sjc), None)
    if ring and ring is not sjc:
        out.append(("Vàng nhẫn 9999", ring))
    return out


def _pick_fuel(fuel: Dict[str, Any], count: int) -> List[Dict[str, Any]]:
    items = list(fuel.get("items") or [])

    def first(*needles):
        for it in items:
            n = str(it.get("name", "")).lower()
            if all(x in n for x in needles):
                return it
        return None

    picks = [first("ron 95"), first("ron 92"), first("do 0,05") or first("do 0.05") or first("dầu do")]
    picks = [p for p in picks if p]
    if len(picks) < count:
        picks += [it for it in items if it not in picks][: count - len(picks)]
    return picks[:count]


def card_prices(canvas: Image.Image, box, data: Dict[str, Any], s: float, tall: bool) -> None:
    _frosted(canvas, box, round(36 * s), s)
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(canvas, "RGBA")
    S = lambda v: round(v * s)  # noqa: E731
    pad = S(36)
    gold, fuel, fx = data.get("gold"), data.get("fuel"), data.get("fx")
    d.text((x0 + pad, y0 + S(40)), "Giá cả hôm nay", font=wr._font(400, S(22)), fill=MUTED, anchor="lm")
    stamp = str(data.get("generated") or "").split(" ")[0]
    if stamp:
        d.text((x1 - pad, y0 + S(40)), f"Cập nhật {stamp}", font=wr._font(400, S(20)), fill=MUTED, anchor="rm")
    wr._hline(d, x0 + pad, x1 - pad, y0 + S(66), LINE, s)

    right = x1 - pad
    buy_r = right - S(92)
    nf, vf, bf = wr._font(400, S(26 if tall else 24)), wr._font(600, S(27 if tall else 25)), wr._font(400, S(26 if tall else 24))
    sub = wr._font(400, S(19))
    pitch = S(42 if tall else 36)

    def row(y, name, *values, bold_last=True):
        name_room = (buy_r - S(70) if len(values) > 1 else right - S(120)) - x0 - pad
        d.text((x0 + pad, y), _fit(d, name, nf, name_room), font=nf, fill=WHITE, anchor="lm")
        cols = [right, buy_r][: len(values)] if len(values) > 1 else [right]
        for col, val in zip(cols, reversed(values)):
            last = col == right
            d.text((col, y), val, font=vf if last and bold_last else bf, fill=WHITE if last else (205, 210, 220), anchor="rm")

    y = y0 + S(94)
    if tall:
        if gold:
            d.text((x0 + pad, y), "Vàng · triệu đ/lượng", font=sub, fill=MUTED, anchor="lm")
            d.text((buy_r, y), "Mua", font=sub, fill=MUTED, anchor="rm")
            d.text((right, y), "Bán", font=sub, fill=MUTED, anchor="rm")
            y += S(40)
            for name, it in _pick_gold(gold):
                row(y, name, _trieu(it.get("buy")), _trieu(it.get("sell")))
                y += pitch
            wr._hline(d, x0 + pad, x1 - pad, y - pitch / 2 + S(2), 12, s)
            y += S(10)
        if fuel:
            d.text((x0 + pad, y), "Xăng dầu · đ/lít", font=sub, fill=MUTED, anchor="lm")
            d.text((right, y), f"Vùng {fuel.get('zone', 1)}", font=sub, fill=MUTED, anchor="rm")
            y += S(40)
            for it in _pick_fuel(fuel, 3):
                row(y, str(it.get("name", "")), _vnd(it.get("price")))
                y += pitch
        if fx:
            fy = y1 - S(52)
            wr._hline(d, x0 + pad, x1 - pad, fy - S(26), LINE, s)
            d.text((x0 + pad, fy), "USD/VND (VCB)" if fx.get("source") == "Vietcombank" else "USD/VND", font=wr._font(600, S(27)), fill=WHITE, anchor="lm")
            d.text((right, fy), _vnd(fx.get("rate")), font=wr._font(700, S(28)), fill=WHITE, anchor="rm")
    else:
        y = y0 + S(98)
        if gold:
            for name, it in _pick_gold(gold):
                row(y, name, _trieu(it.get("buy")), _trieu(it.get("sell")))
                y += pitch
        if fuel:
            fuels = _pick_fuel(fuel, 3)
            for it in (fuels[::2] if gold and len(fuels) == 3 else fuels):
                row(y, str(it.get("name", "")), _vnd(it.get("price")))
                y += pitch
        if fx:
            row(y, "USD/VND", _vnd(fx.get("rate")))


# ------------------------------------------------------------------ layout


def draw_dashboard(canvas: Image.Image, data: Dict[str, Any], s: float) -> List[str]:
    """Draw the cards that have data, side by side. Returns the names drawn."""
    tall = data.get("layout") == "tall"
    region = TALL_REGION if tall else COMPACT_REGION
    cards: List[Tuple[str, Any]] = []
    if data.get("weather"):
        cards.append(("weather", data["weather"]))
    if data.get("lunar"):
        cards.append(("lunar", data["lunar"]))
    if data.get("gold") or data.get("fuel") or data.get("fx"):
        cards.append(("prices", data))
    if not cards:
        return []
    rx0, ry0, rx1, ry1 = (round(v * s) for v in region)
    gap = round((GAP if tall else 24) * s)
    total_w = sum(WEIGHTS[n] for n, _ in cards)
    usable = rx1 - rx0 - gap * (len(cards) - 1)
    x = rx0
    for i, (name, payload) in enumerate(cards):
        w = round(usable * WEIGHTS[name] / total_w) if i < len(cards) - 1 else rx1 - x
        box = (x, ry0, x + w, ry1)
        {"weather": card_weather, "lunar": card_lunar, "prices": card_prices}[name](canvas, box, payload, s, tall)
        x += w + gap
    return [n for n, _ in cards]
