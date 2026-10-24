"""iPhone-style (frosted glass) widgets for gold and fuel prices, drawn onto a wallpaper.

The Gathin launcher has no widget surface, so the widgets are baked into the wallpaper image
that is pushed to the TV. The band between the clock row and the app grid (1920x1080 layout)
is empty on Gathin's Home screen, so that is where the cards go.
"""
from __future__ import annotations

import base64
import io
import os
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE_W, BASE_H = 1920, 1080
# x0, y0, x1, y1 on a 1920x1080 canvas: below the greeting/clock row, above the app grid.
DEFAULT_REGION = (112, 236, 1808, 512)
GAP = 24
GOLD_MAX = 12  # 2 columns x 6 rows
FUEL_MAX = 7

WHITE = (255, 255, 255)
LABEL2 = (235, 235, 245, 150)  # iOS secondaryLabel
UP = (52, 199, 89)
DOWN = (255, 69, 58)
GOLD = (255, 204, 0)
FUEL = (255, 159, 10)


# Stitch palette (Tailwind slate + tv.* tokens)
SLATE300 = (203, 213, 225)
SLATE400 = (148, 163, 184)
SLATE500 = (100, 116, 139)
RED = (239, 68, 68)
GREEN = (52, 199, 89)
PANEL = (17, 21, 30)

# Sans = Inter, numbers = JetBrains Mono (as in the Stitch design).
_FONT_FILES = {
    ("sans", 400): ("Inter-Regular.otf", ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]),
    ("sans", 500): ("Inter-Regular.otf", ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]),
    ("sans", 600): ("Inter-SemiBold.otf", ["seguisb.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"]),
    ("sans", 700): ("Inter-Bold.otf", ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"]),
    ("mono", 500): ("jetbrains-mono-latin-500-normal.woff", ["consola.ttf", "DejaVuSansMono.ttf"]),
    ("mono", 600): ("jetbrains-mono-latin-600-normal.woff", ["consolab.ttf", "DejaVuSansMono-Bold.ttf"]),
    ("mono", 700): ("jetbrains-mono-latin-700-normal.woff", ["consolab.ttf", "DejaVuSansMono-Bold.ttf"]),
}
_font_cache: Dict[Tuple[str, int, int], ImageFont.FreeTypeFont] = {}


def _font_dirs() -> List[str]:
    dirs = []
    try:
        import paths  # type: ignore

        dirs.append(os.path.join(paths.app_root(), "assets", "fonts"))
    except Exception:
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    dirs.append(os.path.join(os.path.dirname(here), "assets", "fonts"))
    dirs += [r"C:\Windows\Fonts", "/System/Library/Fonts/Supplemental", "/usr/share/fonts/truetype/dejavu"]
    return dirs


def _font(weight: int, size: int, family: str = "sans") -> ImageFont.ImageFont:
    key = (family, weight, size)
    if key in _font_cache:
        return _font_cache[key]
    bundled, fallbacks = _FONT_FILES.get((family, weight)) or _FONT_FILES[(family, 700 if weight >= 600 else 500) if family == "mono" else (family, 400)]
    font: Optional[ImageFont.ImageFont] = None
    for d in _font_dirs():
        for name in [bundled] + fallbacks:
            p = os.path.join(d, name)
            if os.path.isfile(p):
                try:
                    font = ImageFont.truetype(p, size)
                    break
                except OSError:
                    continue
        if font:
            break
    font = font or ImageFont.load_default()
    _font_cache[key] = font
    return font


def _mono(weight: int, size: int) -> ImageFont.ImageFont:
    return _font(weight, size, "mono")



def _comma(text: str) -> str:
    return text.replace(".", ",")


def fmt_trieu(v: Optional[float]) -> str:
    return "—" if not v else _comma(f"{v / 1e6:.1f}")


def fmt_vnd(v: Optional[float]) -> str:
    return "—" if v is None else f"{int(round(v)):,}".replace(",", ".")


def fmt_usd(v: Optional[float]) -> str:
    return "—" if not v else f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _delta(v: Optional[float], per: float = 1.0) -> Tuple[str, Tuple[int, int, int]]:
    if v is None or abs(v) < 1e-9:
        return "–", LABEL2[:3]
    txt = _comma(f"{abs(v) / per:.1f}")
    return (("▲" if v > 0 else "▼") + txt), (UP if v > 0 else DOWN)


# ------------------------------------------------------------------ drawing

# ------------------------------------------------------------------ drawing

def _rounded_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    k = 4
    m = Image.new("L", (size[0] * k, size[1] * k), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] * k - 1, size[1] * k - 1), radius * k, fill=255)
    return m.resize(size, Image.Resampling.LANCZOS)


def _glass(canvas: Image.Image, box: Tuple[int, int, int, int], radius: int, s: float) -> None:
    """Stitch `.glass-panel`: rgba(17,21,30,.90) over a blurred backdrop, 1px white/7% border, drop shadow."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    # soft shadow
    pad = round(40 * s)
    sh = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + round(14 * s), pad + w, pad + h + round(14 * s)), radius, fill=170)
    sh = sh.filter(ImageFilter.GaussianBlur(round(22 * s)))
    canvas.paste(Image.new("RGB", sh.size, (0, 0, 0)), (x0 - pad, y0 - pad), sh)
    crop = canvas.crop(box).filter(ImageFilter.GaussianBlur(28 * s))
    crop = Image.blend(crop, Image.new("RGB", crop.size, PANEL), 0.90)
    canvas.paste(crop, (x0, y0), _rounded_mask((w, h), radius))
    border = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bd.rounded_rectangle((0, 0, w - 1, h - 1), radius, outline=(255, 255, 255, 22), width=max(1, round(1.5 * s)))
    bd.line((radius, 1, w - radius, 1), fill=(255, 255, 255, 30), width=max(1, round(s)))  # inset top highlight
    canvas.paste(border, (x0, y0), border)


def _hline(d: ImageDraw.ImageDraw, x0: float, x1: float, y: float, alpha: int, s: float) -> None:
    d.line((x0, y, x1, y), fill=(255, 255, 255, alpha), width=max(1, round(s)))


def _badge(canvas: Image.Image, cx: int, cy: int, r: int, color: Tuple[int, int, int], glyph: str) -> None:
    """Round badge with a soft glow (shadow-[0_0_12px])."""
    glow = Image.new("RGBA", (r * 6, r * 6), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((r * 2, r * 2, r * 4, r * 4), fill=color + (110,))
    glow = glow.filter(ImageFilter.GaussianBlur(r * 0.55))
    canvas.paste(glow, (cx - r * 3, cy - r * 3), glow)
    d = ImageDraw.Draw(canvas, "RGBA")
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    d.text((cx, cy), glyph, font=_font(700, round(r * 0.95)), fill=(0, 0, 0), anchor="mm")


def _arrow(d: ImageDraw.ImageDraw, right: float, cy: float, size: float, up: bool, color) -> float:
    """Filled triangle (▲/▼) with its right edge at `right`; returns its left edge."""
    w, h = size * 0.95, size * 0.8
    x0 = right - w
    if up:
        pts = [(x0, cy + h / 2), (right, cy + h / 2), (x0 + w / 2, cy - h / 2)]
    else:
        pts = [(x0, cy - h / 2), (right, cy - h / 2), (x0 + w / 2, cy + h / 2)]
    d.polygon(pts, fill=color)
    return x0


def _change(d: ImageDraw.ImageDraw, right: float, cy: float, v: Optional[float], per: float, size: int, s: float) -> float:
    """Right-aligned ▲/▼ + number, or a dash. Returns left edge x."""
    f = _mono(600, size)
    if v is None or abs(v) < 1e-9:
        d.text((right, cy), "-", font=f, fill=SLATE500, anchor="rm")
        return right - d.textlength("-", font=f)
    col = GREEN if v > 0 else RED
    txt = _comma(f"{abs(v) / per:.1f}")
    d.text((right, cy), txt, font=f, fill=col, anchor="rm")
    left = right - d.textlength(txt, font=f) - round(3 * s)
    return _arrow(d, left, cy, size * 0.62, v > 0, col)


def _header(canvas, box, s, color, glyph, title) -> Tuple[ImageDraw.ImageDraw, int, int, int, int]:
    x0, y0, x1, y1 = box
    pad = round(26 * s)
    hh = round(52 * s)
    cy = y0 + round(24 * s) + hh // 2 - round(6 * s)
    _badge(canvas, x0 + pad + round(14 * s), cy, round(14 * s), color, glyph)
    d = ImageDraw.Draw(canvas, "RGBA")
    d.text((x0 + pad + round(40 * s), cy), title, font=_font(700, round(27 * s)), fill=WHITE, anchor="lm")
    line_y = y0 + round(24 * s) + hh - round(2 * s)
    _hline(d, x0 + pad, x1 - pad, line_y, 16, s)
    return d, pad, cy, line_y, hh


def _card_gold(canvas: Image.Image, box, gold: Dict[str, Any], s: float) -> None:
    _glass(canvas, box, round(34 * s), s)
    x0, y0, x1, y1 = box
    d, pad, cy, line_y, _ = _header(canvas, box, s, (242, 169, 0), "Au", "Giá vàng")
    world = gold.get("world")
    right = x1 - pad
    if world and world.get("buy"):
        # delta chip: bg red/10, 1px red/20 border
        chg_f = _mono(700, round(15 * s))
        v = world.get("change_buy")
        val = f"{fmt_usd(world['buy'])}$"
        chip_txt = _comma(f"{abs(v):.1f}") if v else "-"
        tw = d.textlength(chip_txt, font=chg_f)
        aw = round(11 * s) if v else 0
        cw, ch = tw + aw + round(18 * s), round(24 * s)
        cx1, cx0 = right, right - cw
        if v:
            col = GREEN if v > 0 else RED
            d.rounded_rectangle((cx0, cy - ch / 2, cx1, cy + ch / 2), round(6 * s), fill=col + (28,), outline=col + (52,), width=max(1, round(s)))
            _arrow(d, cx0 + round(9 * s) + aw, cy, round(15 * s), v > 0, col)
            d.text((cx1 - round(9 * s), cy), chip_txt, font=chg_f, fill=col, anchor="rm")
        else:
            cx0 = cx1
        vf = _mono(600, round(19 * s))
        d.text((cx0 - round(10 * s), cy), val, font=vf, fill=WHITE, anchor="rm")
        lx = cx0 - round(10 * s) - d.textlength(val, font=vf) - round(8 * s)
        d.text((lx, cy), "XAU/USD", font=_mono(500, round(16 * s)), fill=SLATE400, anchor="rm")

    items = list(gold.get("items") or [])[:GOLD_MAX]
    rows_per_col = 6
    cols = 2 if len(items) > rows_per_col else 1
    col_gap = round(44 * s)
    col_w = (x1 - x0 - 2 * pad - (cols - 1) * col_gap) / cols
    foot_y = y1 - round(34 * s)
    head_y = line_y + round(18 * s)
    rows_top = head_y + round(12 * s)
    rh = (foot_y - round(6 * s) - rows_top) / rows_per_col
    hf = _font(600, round(13 * s))
    for c in range(cols):
        cx0 = x0 + pad + c * (col_w + col_gap)
        cx1 = cx0 + col_w
        chg_r = cx1
        sell_r = cx1 - round(72 * s)
        buy_r = sell_r - round(86 * s)
        d.text((buy_r, head_y), "MUA", font=hf, fill=SLATE400, anchor="rm")
        d.text((sell_r, head_y), "BÁN", font=hf, fill=SLATE400, anchor="rm")
        _hline(d, cx0, cx1, head_y + round(10 * s), 8, s)
        for r, it in enumerate(items[c * rows_per_col:(c + 1) * rows_per_col]):
            ry = rows_top + r * rh
            my = ry + rh / 2
            name = it.get("name", "")
            nf = _font(500, round(19 * s))
            maxw = buy_r - round(70 * s) - cx0
            while d.textlength(name, font=nf) > maxw and len(name) > 3:
                name = name[:-2].rstrip() + "…"
            d.text((cx0, my), name, font=nf, fill=SLATE300, anchor="lm")
            d.text((buy_r, my), fmt_trieu(it.get("buy")), font=_mono(500, round(18 * s)), fill=SLATE300, anchor="rm")
            d.text((sell_r, my), fmt_trieu(it.get("sell")), font=_mono(700, round(18 * s)), fill=WHITE, anchor="rm")
            _change(d, chg_r, my, it.get("change_sell"), 1e6, round(15 * s), s)
            if r < rows_per_col - 1 and (c * rows_per_col + r + 1) < len(items):
                _hline(d, cx0, cx1, ry + rh, 6, s)
    upd = gold.get("updated") or ""
    foot = f"Triệu đồng/lượng · cập nhật {upd}" if upd else "Triệu đồng/lượng"
    _hline(d, x0 + pad, x1 - pad, foot_y, 13, s)
    d.text((x0 + pad, y1 - round(14 * s)), foot, font=_font(500, round(14 * s)), fill=SLATE400, anchor="ls")


def _card_fuel(canvas: Image.Image, box, fuel: Dict[str, Any], s: float) -> None:
    _glass(canvas, box, round(34 * s), s)
    x0, y0, x1, y1 = box
    d, pad, cy, line_y, _ = _header(canvas, box, s, (243, 156, 18), "L", "Xăng dầu")
    tag = f"Vùng {fuel.get('zone', 1)}"
    tf = _font(600, round(15 * s))
    tw = d.textlength(tag, font=tf)
    d.rounded_rectangle((x1 - pad - tw - round(20 * s), cy - round(13 * s), x1 - pad, cy + round(13 * s)), round(6 * s),
                        fill=(255, 255, 255, 15), outline=(255, 255, 255, 13), width=max(1, round(s)))
    d.text((x1 - pad - round(10 * s), cy), tag, font=tf, fill=SLATE300, anchor="rm")
    items = list(fuel.get("items") or [])[:FUEL_MAX]
    foot_y = y1 - round(34 * s)
    rows_top = line_y + round(8 * s)
    rh = (foot_y - round(6 * s) - rows_top) / max(1, len(items))
    for r, it in enumerate(items):
        ry = rows_top + r * rh
        my = ry + rh / 2
        nf = _font(500, round(19 * s))
        name = it.get("name", "")
        maxw = (x1 - x0) - 2 * pad - round(120 * s)
        while d.textlength(name, font=nf) > maxw and len(name) > 3:
            name = name[:-2].rstrip() + "…"
        d.text((x0 + pad, my), name, font=nf, fill=SLATE300, anchor="lm")
        d.text((x1 - pad, my + round(1 * s)), "đ", font=_font(500, round(15 * s)), fill=SLATE400, anchor="rm")
        d.text((x1 - pad - round(16 * s), my), fmt_vnd(it.get("price")), font=_mono(700, round(21 * s)), fill=WHITE, anchor="rm")
        if r < len(items) - 1:
            _hline(d, x0 + pad, x1 - pad, ry + rh, 6, s)
    _hline(d, x0 + pad, x1 - pad, foot_y, 13, s)
    foot = f"{fuel.get('source', '')} · cập nhật {fuel.get('updated', '')}".strip(" ·")
    d.text((x0 + pad, y1 - round(14 * s)), foot, font=_font(500, round(14 * s)), fill=SLATE400, anchor="ls")


def _cover(img: Image.Image, size: Tuple[int, int]) -> Image.Image:
    w, h = size
    r = max(w / img.width, h / img.height)
    img = img.resize((max(w, round(img.width * r)), max(h, round(img.height * r))), Image.Resampling.LANCZOS)
    l, t = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((l, t, l + w, t + h))


def _fallback_background(size: Tuple[int, int]) -> Image.Image:
    w, h = size
    bg = Image.new("RGB", size)
    px = bg.load()
    for y in range(h):
        k = y / max(1, h - 1)
        c = (round(24 + 16 * k), round(30 + 26 * k), round(54 + 40 * k))
        for x in range(w):
            px[x, y] = c
    return bg


def render_widgets(
    wallpaper_path: Optional[str],
    data: Dict[str, Any],
    *,
    size: Tuple[int, int] = (BASE_W, BASE_H),
    region: Tuple[int, int, int, int] = DEFAULT_REGION,
) -> Image.Image:
    """Return the wallpaper (cover-fitted to `size`) with the gold and fuel cards drawn on it."""
    s = size[0] / BASE_W
    if wallpaper_path and os.path.isfile(wallpaper_path):
        with Image.open(wallpaper_path) as im:
            canvas = _cover(im.convert("RGB"), size)
    else:
        canvas = _fallback_background(size)
    rx0, ry0, rx1, ry1 = (round(v * s) for v in region)
    gap = round(GAP * s)
    gold, fuel = data.get("gold"), data.get("fuel")
    if gold and fuel:
        gold_w = round((rx1 - rx0 - gap) * 0.60)
        _card_gold(canvas, (rx0, ry0, rx0 + gold_w, ry1), gold, s)
        _card_fuel(canvas, (rx0 + gold_w + gap, ry0, rx1, ry1), fuel, s)
    elif gold:
        _card_gold(canvas, (rx0, ry0, rx0 + round(1000 * s), ry1), gold, s)
    elif fuel:
        _card_fuel(canvas, (rx0, ry0, rx0 + round(672 * s), ry1), fuel, s)
    return canvas


def render_to_file(wallpaper_path: Optional[str], data: Dict[str, Any], out_path: str, **kw) -> str:
    img = render_widgets(wallpaper_path, data, **kw)
    img.save(out_path, "JPEG", quality=88, optimize=True)
    return out_path


def render_preview_b64(wallpaper_path: Optional[str], data: Dict[str, Any], width: int = 960) -> str:
    img = render_widgets(wallpaper_path, data, size=(width, round(width * 9 / 16)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("ascii")
