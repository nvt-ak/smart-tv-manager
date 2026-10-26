#!/usr/bin/env python3
"""Procedural wallpapers and preview cards for the bundled CleanYourTV themes.

Every picture is drawn from code (numpy + Pillow), so the art is original, reproducible and
has no licensing question. Rules the launcher imposes on wallpapers, enforced here:

  * 1920x1080, dark (text, hero name and dock band are designed for black);
  * under ~300 KB per file (a 1 GB TV decodes the picture on every Home start);
  * a little dither noise, because the launcher decodes RGB_565 by default and would
    otherwise band every dark gradient.

Usage:
    python scripts/make_theme_wallpapers.py            # all themes
    python scripts/make_theme_wallpapers.py halong     # one scene by key
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
MAX_BYTES = 300 * 1024
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)

THEMES_DIR = os.environ.get("THEMES_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "cleanyourtv", "themes",
)

# --------------------------------------------------------------------------- helpers


def rgb(hex_color):
    h = hex_color.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def vgrad(stops):
    """Vertical gradient from [(t, '#rrggbb'), ...] with t in 0..1 of the height."""
    t = np.linspace(0, 1, H, dtype=np.float32)
    ts = [s for s, _ in stops]
    cols = np.array([rgb(c) for _, c in stops])
    col = np.stack([np.interp(t, ts, cols[:, i]) for i in range(3)], axis=1)
    return np.repeat(col[:, None, :], W, axis=1).astype(np.float32)


def screen(img, layer):
    """Screen blend: brightens without clipping hard."""
    return 255.0 - (255.0 - img) * (255.0 - np.clip(layer, 0, 255)) / 255.0


def glow(img, cx, cy, rx, color, strength=1.0, ry=None):
    ry = ry or rx
    d2 = ((XX - cx) / rx) ** 2 + ((YY - cy) / ry) ** 2
    a = np.exp(-d2 * 2.2) * strength
    return screen(img, a[..., None] * rgb(color))


def fbm1d(rng, octaves=5, base=3.0, rough=0.5):
    """Smooth 1-D fractal noise over the width, 0..1."""
    x = np.linspace(0, 1, W, dtype=np.float32)
    total = np.zeros(W, dtype=np.float32)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        k = base * (2 ** o)
        pts = rng.random(int(k) + 3).astype(np.float32)
        pos = x * k
        i = np.floor(pos).astype(int)
        f = pos - i
        f = (1 - np.cos(f * np.pi)) / 2
        total += amp * (pts[i] * (1 - f) + pts[i + 1] * f)
        norm += amp
        amp *= rough
    return total / norm


def fbm2d(rng, scale=6, octaves=4, rough=0.55):
    """Smooth 2-D noise, 0..1, built by upsampling random grids."""
    total = np.zeros((H, W), dtype=np.float32)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        gw, gh = scale * (2 ** o), max(2, int(scale * (2 ** o) * H / W))
        grid = rng.random((gh, gw)).astype(np.float32)
        im = Image.fromarray((grid * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
        total += amp * np.asarray(im, dtype=np.float32) / 255.0
        norm += amp
        amp *= rough
    return total / norm


def layer(img, ycurve, top, bottom, depth=320.0, edge=1.4):
    """Paint everything below `ycurve` (one y per column) with a vertical colour ramp."""
    a = np.clip((YY - ycurve[None, :]) / edge + 0.5, 0, 1)[..., None]
    t = np.clip((YY - float(ycurve.min())) / depth, 0, 1)[..., None]
    col = rgb(top) * (1 - t) + rgb(bottom) * t
    return img * (1 - a) + col * a


def to_image(arr):
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def from_image(im):
    return np.asarray(im.convert("RGB"), dtype=np.float32)


def finish(img, bottom=0.55, corner=0.35, seed=7):
    """Keep the clock and dock readable, then dither."""
    t = np.clip((YY / H - 0.45) / 0.55, 0, 1)
    img = img * (1 - bottom * t ** 1.5)[..., None]
    d = np.sqrt((XX / 760.0) ** 2 + (YY / 420.0) ** 2)
    img = img * (1 - corner * np.clip(1 - d, 0, 1))[..., None]
    rng = np.random.default_rng(seed)
    img = img + rng.normal(0, 1.1, (H, W, 1))
    return img


def save_jpeg(img, path, max_bytes=MAX_BYTES):
    im = to_image(img) if isinstance(img, np.ndarray) else img
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for q in (86, 82, 78, 74, 70, 66, 62, 58):
        im.save(path, "JPEG", quality=q, optimize=True, subsampling=2)
        if os.path.getsize(path) <= max_bytes:
            break
    return os.path.getsize(path)


def stars(img, rng, n, ymax=0.6, bright=(120, 255), size=(0.5, 1.6), tint=None):
    layer_im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(layer_im)
    for _ in range(n):
        x, y = rng.random() * W, rng.random() * H * ymax
        r = rng.uniform(*size)
        v = int(rng.uniform(*bright))
        d.ellipse([x - r, y - r, x + r, y + r], fill=v)
    layer_im = layer_im.filter(ImageFilter.GaussianBlur(0.6))
    s = np.asarray(layer_im, dtype=np.float32)[..., None]
    col = rgb(tint) / 255.0 if tint else np.array([1, 1, 1], dtype=np.float32)
    return screen(img, s * col)


def water_reflection(img, horizon, base_top, base_bottom, strength=0.5, ripple=5.0, seed=3):
    """Replace everything under `horizon` with a rippled, darkened mirror of what is above."""
    rng = np.random.default_rng(seed)
    out = img.copy()
    ys = np.arange(horizon, H)
    src = np.clip(2 * horizon - ys, 0, H - 1)
    phase = rng.random() * 6.28
    ripple = ripple * 0.55
    dx = (ripple * np.sin(ys * 0.07 + phase) + ripple * 0.6 * np.sin(ys * 0.023 + 1.3))
    xs = np.clip(np.arange(W)[None, :] + dx[:, None] * (0.4 + (ys - horizon)[:, None] / (H - horizon)),
                 0, W - 1).astype(int)
    refl = img[src[:, None], xs]
    refl = from_image(to_image(refl).filter(ImageFilter.GaussianBlur(1.6)))
    t =((ys - horizon) / max(1, H - horizon))[:, None, None]
    base = rgb(base_top) * (1 - t) + rgb(base_bottom) * t
    fade = strength * (1 - 0.65 * t)
    out[horizon:] = base * (1 - fade) + refl * fade
    return out


# --------------------------------------------------------------------------- scenes


def scene_halong():
    rng = np.random.default_rng(11)
    hz = 640
    img = vgrad([(0, "#04101f"), (0.30, "#0b2a3f"), (0.50, "#27505c"), (0.592, "#b9805f"), (1, "#b9805f")])
    img = glow(img, 1290, hz - 10, 420, "#ff9a5c", 0.55, ry=220)
    # moon-like low sun
    d = np.sqrt((XX - 1290) ** 2 + (YY - (hz - 120)) ** 2)
    img = screen(img, (np.clip(1 - (d - 46) / 5, 0, 1) * 0.85)[..., None] * rgb("#ffe2bf"))
    img = stars(img, rng, 120, ymax=0.32, bright=(60, 180))

    def karsts(centres, hmin, hmax, wmin, wmax):
        """Tall limestone towers: near-vertical flanks, a rounded crown, a craggy edge."""
        y = np.zeros(W, dtype=np.float32)
        xs_ = np.arange(W)
        for c in centres:
            h = rng.uniform(hmin, hmax)
            w = rng.uniform(wmin, wmax)
            u = (xs_ - c) / w
            a_ = np.abs(u)
            # steep, slightly concave flanks that open toward the foot, a blunt crown
            body = np.clip(1 - a_, 0, 1) ** 0.62
            crown = np.clip(1 - (a_ / 0.32) ** 2, 0, 1) ** 0.5 * 0.06 + 0.94
            prof = np.where(a_ < 1, h * body * np.where(a_ < 0.32, crown, 1.0), 0)
            # a shorter companion spire at the side
            u2 = (xs_ - c - rng.choice([-1, 1]) * w * 0.7) / (w * 0.55)
            prof = np.maximum(prof, np.where(np.abs(u2) < 1, h * rng.uniform(0.35, 0.6) * np.clip(1 - np.abs(u2), 0, 1) ** 0.62, 0))
            y = np.maximum(y, prof)
        crag = (fbm1d(rng, 6, 40, 0.55) - 0.5) * 16
        return hz - np.maximum(y + crag * (y > 4), 0)

    far = karsts(rng.uniform(-100, W + 100, 22), 60, 150, 50, 110)
    mid = karsts(rng.uniform(-100, W + 100, 12), 130, 280, 60, 130)
    near = karsts(list(rng.uniform(-60, 560, 3)) + list(rng.uniform(1560, W + 60, 3)), 260, 470, 80, 150)
    for ycurve, top, bot in ((far, "#456a73", "#b08266"), (mid, "#1f4351", "#8b6d5d"), (near, "#0a1d29", "#2a3d46")):
        a = np.clip((YY - ycurve[None, :]) / 1.4 + 0.5, 0, 1)[..., None] * (YY < hz)[..., None]
        t = np.clip((YY - float(ycurve.min())) / 380.0, 0, 1)[..., None]
        col = rgb(top) * (1 - t) + rgb(bot) * t
        img = img * (1 - a) + col * a
    # mist hugging the horizon
    mist = np.exp(-((YY - hz + 14) / 36.0) ** 2)[..., None] * rgb("#e0a888") * 0.28
    img = screen(img, mist)
    img = water_reflection(img, hz, "#183843", "#04111a", strength=0.5, ripple=4.5, seed=5)
    streak = np.exp(-((XX - 1290) / (60 + (YY - hz) * 0.6)) ** 2) * (YY > hz) * np.exp(-(YY - hz) / 260.0)
    wob = 0.5 + 0.5 * np.sin(YY * 0.9 + XX * 0.02)
    img = screen(img, (streak * wob * 0.7)[..., None] * rgb("#ffb27a"))
    return finish(img, bottom=0.6)


def ridged(rng, octaves=6, base=3.0, rough=0.55):
    """Ridged noise: sharp crests, like a mountain skyline. 0..1, high = peak."""
    return 1 - np.abs(2 * fbm1d(rng, octaves, base, rough) - 1) ** 0.8


def scene_sapa():
    rng = np.random.default_rng(23)
    img = vgrad([(0, "#060a1c"), (0.28, "#15204a"), (0.46, "#5a4272"), (0.60, "#d58376"), (1, "#d58376")])
    img = glow(img, 1330, 650, 560, "#ffb98a", 0.75, ry=250)
    img = stars(img, rng, 150, ymax=0.28, bright=(60, 170))
    # far ranges, lit warm from behind
    for base_y, amp, top, bot, base_f in (
        (610, 120, "#8a6a86", "#d58f82", 2.2),
        (640, 150, "#5a4a78", "#b57d86", 2.8),
    ):
        ycurve = base_y - ridged(rng, 6, base_f, 0.55) * amp
        img = layer(img, ycurve, top, bot, depth=220)
    # sea of clouds, three soft sheets at different depths
    for y0, y1, dens, tint, sc in ((650, 840, 0.9, "#f0b9b0", 4), (720, 920, 0.95, "#c18fa6", 6), (800, 1000, 1.0, "#6f6a9c", 8)):
        n2 = fbm2d(rng, sc, 5, 0.6)
        band = np.clip((YY - y0) / 90, 0, 1) * np.clip(1 - (YY - (y1 - 120)) / 160, 0, 1)
        cloud = np.clip((n2 - 0.33) * 3.0, 0, 1) * band * dens
        img = img * (1 - cloud[..., None] * 0.9) + rgb(tint) * cloud[..., None] * 0.9
    # dark crests poking through the clouds on both sides
    for side in (0, 1):
        n = ridged(rng, 6, 2.0, 0.6)
        xs_ = np.arange(W)
        fall = np.clip(1 - np.abs(xs_ - (130 if side == 0 else 1760)) / 560.0, 0, 1) ** 1.4
        ycurve = 1250 - fall * (640 + 220 * n)
        img = layer(img, ycurve, "#160f2a", "#06070f", depth=260)
    return finish(img, bottom=0.55)


def scene_hoian():
    rng = np.random.default_rng(31)
    hz = 760
    img = vgrad([(0, "#05060f"), (0.4, "#0b1030"), (0.70, "#1b1a3a"), (1, "#0a0b18")])
    img = glow(img, 960, hz - 90, 900, "#6a3b3a", 0.30, ry=260)
    # silhouette of the old town: tiled-roof houses
    base = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(base)
    x = -40
    while x < W + 40:
        w = int(rng.uniform(150, 260))
        h = int(rng.uniform(95, 190))
        roof = int(rng.uniform(34, 62))
        top = hz - h
        d.rectangle([x, top, x + w, hz], fill=255)
        d.polygon([(x - 14, top + 4), (x + w // 2, top - roof), (x + w + 14, top + 4)], fill=255)
        x += w + int(rng.uniform(-8, 12))
    sil = np.asarray(base, dtype=np.float32)[..., None] / 255.0
    img = img * (1 - sil) + rgb("#04050b") * sil
    # warm windows
    win = Image.new("L", (W, H), 0)
    wd = ImageDraw.Draw(win)
    for _ in range(70):
        wx = rng.uniform(0, W)
        wy = rng.uniform(hz - 130, hz - 20)
        wd.rectangle([wx, wy, wx + rng.uniform(8, 14), wy + rng.uniform(12, 20)], fill=int(rng.uniform(120, 230)))
    win = win.filter(ImageFilter.GaussianBlur(0.8))
    sil_inv = 1 - sil
    wa = np.asarray(win, dtype=np.float32)[..., None] / 255.0 * sil
    img = screen(img, wa * rgb("#ffb35c") * 0.8)
    del sil_inv
    # lantern bokeh in three depths
    palette = ["#ff4d36", "#ff8a3c", "#ffc94d", "#e63950", "#ff6b4a", "#ffd98a"]
    bok = np.zeros((H, W, 3), dtype=np.float32)
    for (count, rmin, rmax, blur, ymax, gain) in ((14, 46, 78, 7, 0.52, 0.55), (34, 18, 32, 3, 0.62, 0.8), (70, 7, 14, 1.4, 0.7, 1.0)):
        lay = Image.new("RGB", (W, H), (0, 0, 0))
        dd = ImageDraw.Draw(lay)
        for _ in range(count):
            cx, cy = rng.uniform(0, W), rng.uniform(20, ymax * H)
            r = rng.uniform(rmin, rmax)
            c = rgb(palette[int(rng.integers(len(palette)))]) * gain * rng.uniform(0.55, 1.0)
            dd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=tuple(int(v) for v in c))
        bok = screen(bok, from_image(lay.filter(ImageFilter.GaussianBlur(blur))))
    bok_mask = 1 - sil * 0.85
    img = screen(img, bok * bok_mask * 0.9)
    # river with reflection
    img = water_reflection(img, hz, "#0c1022", "#04050c", strength=0.62, ripple=7.0, seed=9)
    img = to_image(img).filter(ImageFilter.GaussianBlur(0.4))
    return finish(from_image(img), bottom=0.5, corner=0.45)


def scene_mekong():
    rng = np.random.default_rng(41)
    hz = 600
    img = vgrad([(0, "#07102a"), (0.32, "#2a2858"), (0.50, "#a14e62"), (0.555, "#f08a4b"), (1, "#f08a4b")])
    cx = 1280
    img = glow(img, cx, hz, 700, "#ff8a3d", 0.9, ry=330)
    d = np.sqrt((XX - cx) ** 2 + (YY - (hz - 18)) ** 2)
    sun = np.clip(1 - (d - 78) / 4, 0, 1) * (YY < hz)
    img = screen(img, sun[..., None] * rgb("#ffd9a0"))
    img = stars(img, rng, 90, ymax=0.22, bright=(50, 150))
    # far bank
    n = fbm1d(rng, 6, 10, 0.5)
    bank = hz - 6 - n * 14
    a = np.clip((YY - bank[None, :]) / 1.2 + 0.5, 0, 1)[..., None] * (YY < hz + 1)[..., None]
    img = img * (1 - a) + rgb("#2b1b2c") * a
    # water: colour of the sky fading to deep violet
    t = np.clip((YY - hz) / (H - hz), 0, 1)[..., None]
    water = rgb("#d7774d") * (1 - t) ** 1.6 + rgb("#1a1230") * (1 - (1 - t) ** 1.6)
    wm = (YY >= hz)[..., None]
    img = np.where(wm, water, img)
    # sun path shimmer
    sh = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(sh)
    for _ in range(1500):
        y = hz + 4 + (rng.random() ** 1.7) * (H - hz - 10)
        spread = 40 + (y - hz) * 0.55
        x = cx + rng.normal(0, spread * 0.45)
        ln = rng.uniform(10, 26 + (y - hz) * 0.18)
        v = int(max(0, 235 * (1 - (y - hz) / (H - hz) * 0.9) * rng.uniform(0.4, 1.0)))
        sd.line([x - ln, y, x + ln, y], fill=v, width=int(rng.integers(1, 3)))
    sh = sh.filter(ImageFilter.GaussianBlur(0.7))
    img = screen(img, np.asarray(sh, dtype=np.float32)[..., None] * rgb("#ffcf94") / 255.0 * 0.95)
    # palms on the left bank and a boat
    sil = Image.new("L", (W, H), 0)
    pd = ImageDraw.Draw(sil)

    def palm(x0, y0, height, lean):
        pts = []
        for i in range(21):
            tt = i / 20
            pts.append((x0 + lean * tt * tt * height, y0 - tt * height))
        for i in range(len(pts) - 1):
            pd.line([pts[i], pts[i + 1]], fill=255, width=max(2, int(9 - 6 * i / 20)))
        tx, ty = pts[-1]
        for k in range(9):
            ang = -math.pi + k * math.pi / 8 + rng.uniform(-0.08, 0.08)
            ln = rng.uniform(80, 130)
            prev = (tx, ty)
            for j in range(1, 9):
                tt = j / 8
                px = tx + math.cos(ang) * ln * tt
                py = ty + math.sin(ang) * ln * tt * 0.55 + (tt ** 2) * ln * 0.55
                pd.line([prev, (px, py)], fill=255, width=max(1, int(4 - 3 * tt)))
                prev = (px, py)

    for x0, hgt, lean in ((130, 330, 0.18), (250, 260, -0.12), (60, 220, 0.1), (1780, 300, -0.16), (1860, 230, 0.1)):
        palm(x0, hz - 4, hgt, lean)
    # sampan
    bx, by = 560, hz + 120
    pd.polygon([(bx - 120, by - 14), (bx + 130, by - 18), (bx + 90, by + 8), (bx - 80, by + 8)], fill=255)
    pd.line([(bx + 10, by - 16), (bx + 10, by - 78)], fill=255, width=3)
    pd.polygon([(bx - 30, by - 16), (bx - 8, by - 54), (bx + 16, by - 16)], fill=255)
    s = np.asarray(sil.filter(ImageFilter.GaussianBlur(0.6)), dtype=np.float32)[..., None] / 255.0
    img = img * (1 - s) + rgb("#1b0f1d") * s
    return finish(img, bottom=0.55)


def scene_hanoi():
    rng = np.random.default_rng(53)
    hz = 700
    img = vgrad([(0, "#040a14"), (0.40, "#0a2230"), (0.66, "#173a48"), (1, "#173a48")])
    mx, my = 1530, 250
    img = glow(img, mx, my, 520, "#9ccfd8", 0.38, ry=420)
    d = np.sqrt((XX - mx) ** 2 + (YY - my) ** 2)
    img = screen(img, (np.clip(1 - (d - 52) / 3.5, 0, 1) * 0.9)[..., None] * rgb("#e9f5f2"))
    img = stars(img, rng, 130, ymax=0.4, bright=(50, 150), tint="#cfe6ff")
    # distant skyline
    sky = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(sky)
    x = -20
    while x < W + 20:
        w = int(rng.uniform(30, 90))
        h = int(rng.uniform(14, 62))
        sd.rectangle([x, hz - h, x + w, hz], fill=255)
        if rng.random() < 0.3:
            sd.polygon([(x, hz - h), (x + w / 2, hz - h - rng.uniform(10, 24)), (x + w, hz - h)], fill=255)
        x += w + int(rng.uniform(-6, 10))
    sk = np.asarray(sky, dtype=np.float32)[..., None] / 255.0
    img = img * (1 - sk * 0.9) + rgb("#0b2330") * sk * 0.9
    win = Image.new("L", (W, H), 0)
    wd = ImageDraw.Draw(win)
    for _ in range(110):
        wx, wy = rng.uniform(0, W), rng.uniform(hz - 56, hz - 6)
        wd.rectangle([wx, wy, wx + 3, wy + 4], fill=int(rng.uniform(80, 200)))
    img = screen(img, (np.asarray(win, dtype=np.float32)[..., None] / 255.0) * sk * rgb("#ffd89a") * 0.8)
    # the turtle tower on a small island
    tw = Image.new("L", (W, H), 0)
    td = ImageDraw.Draw(tw)
    cx0, by = 1010, hz - 2
    td.ellipse([cx0 - 120, by - 20, cx0 + 120, by + 14], fill=255)
    td.rectangle([cx0 - 52, by - 56, cx0 + 52, by - 6], fill=255)

    def tier(width, y_base, hgt, tip):
        td.polygon([(cx0 - width - 12, y_base), (cx0 - width * 0.55, y_base - hgt * 0.72),
                    (cx0, y_base - hgt - tip), (cx0 + width * 0.55, y_base - hgt * 0.72),
                    (cx0 + width + 12, y_base)], fill=255)

    tier(52, by - 56, 26, 8)
    td.rectangle([cx0 - 38, by - 92, cx0 + 38, by - 56], fill=255)
    tier(38, by - 92, 24, 8)
    td.rectangle([cx0 - 26, by - 124, cx0 + 26, by - 92], fill=255)
    tier(28, by - 124, 22, 14)
    ts = np.asarray(tw.filter(ImageFilter.GaussianBlur(0.5)), dtype=np.float32)[..., None] / 255.0
    img = img * (1 - ts) + rgb("#05121a") * ts
    wl = Image.new("L", (W, H), 0)
    ld = ImageDraw.Draw(wl)
    for ox in (-30, -8, 14):
        ld.rectangle([cx0 + ox, by - 84, cx0 + ox + 8, by - 68], fill=230)
    ld.rectangle([cx0 - 4, by - 118, cx0 + 4, by - 102], fill=230)
    wl = wl.filter(ImageFilter.GaussianBlur(1.2))
    img = screen(img, np.asarray(wl, dtype=np.float32)[..., None] / 255.0 * rgb("#ffc36b") * 0.95)
    # willow strands hanging from the top right
    wil = Image.new("L", (W, H), 0)
    wd2 = ImageDraw.Draw(wil)
    arch = [(1160 + i * 52, 30 + 70 * math.sin(i / 14 * math.pi) * 0.0 + 46 * (1 - math.cos(i / 14 * math.pi * 0.9)) / 2) for i in range(16)]
    wd2.line(arch, fill=255, width=9)
    for i in range(110):
        k = rng.uniform(0, 14.9)
        j0 = int(k)
        x0 = arch[j0][0] + (arch[j0 + 1][0] - arch[j0][0]) * (k - j0)
        y0 = arch[j0][1] + (arch[j0 + 1][1] - arch[j0][1]) * (k - j0)
        length = rng.uniform(110, 360)
        sway = rng.uniform(-26, 10)
        pts = [(x0 + sway * (j / 16) ** 2 + math.sin(j * 0.45 + i) * 2.5, y0 + length * j / 16) for j in range(17)]
        wd2.line(pts, fill=255, width=int(rng.integers(1, 3)))
        # a few leaves along the strand
        for j in range(3, 16, 3):
            lx, ly = pts[j]
            wd2.ellipse([lx - 2, ly - 1, lx + 5, ly + 3], fill=255)
    ws = np.asarray(wil.filter(ImageFilter.GaussianBlur(0.7)), dtype=np.float32)[..., None] / 255.0
    img = img * (1 - ws * 0.92) + rgb("#050d12") * ws * 0.92
    img = water_reflection(img, hz, "#0d2a36", "#040e15", strength=0.6, ripple=5.0, seed=4)
    streak = np.exp(-((XX - mx) / (30 + np.maximum(YY - hz, 0) * 0.25)) ** 2) * (YY > hz) * np.exp(-(YY - hz) / 220.0)
    wob = 0.5 + 0.5 * np.sin(YY * 0.8)
    img = screen(img, (streak * wob * 0.5)[..., None] * rgb("#cfeef0"))
    return finish(img, bottom=0.55)


def scene_dalat():
    rng = np.random.default_rng(67)
    img = vgrad([(0, "#03060f"), (0.5, "#0a1230"), (0.8, "#16254a"), (1, "#0c1630")])
    # milky way: bright diagonal band of unresolved stars
    ang = math.radians(-24)
    u = (XX - 1000) * math.cos(ang) - (YY - 300) * math.sin(ang)
    v = (XX - 1000) * math.sin(ang) + (YY - 300) * math.cos(ang)
    band = np.exp(-(v / 150.0) ** 2) * (0.6 + 0.8 * fbm2d(rng, 7, 5, 0.6))
    img = screen(img, (band * 0.55)[..., None] * rgb("#8da4d9"))
    img = screen(img, (np.exp(-(v / 55.0) ** 2) * 0.18 * np.exp(-(u / 900.0) ** 2))[..., None] * rgb("#e5c9ff"))
    img = stars(img, rng, 700, ymax=0.78, bright=(40, 255), size=(0.4, 1.7), tint="#dfe9ff")
    # ridges of pines
    def pines(y_base, step, hmin, hmax, color, wobble=40):
        n = fbm1d(rng, 4, 3, 0.5)
        lay = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(lay)
        x = -20.0
        while x < W + 20:
            gx = int(min(max(x, 0), W - 1))
            gy = y_base - n[gx] * wobble
            h = rng.uniform(hmin, hmax)
            w = h * 0.34
            for k in range(4):
                tier_y = gy - h * (k * 0.22)
                tw = w * (1 - k * 0.2)
                d.polygon([(x - tw, tier_y), (x, tier_y - h * 0.34), (x + tw, tier_y)], fill=255)
            d.rectangle([x - 2, gy, x + 2, gy + h * 0.1], fill=255)
            x += step * rng.uniform(0.7, 1.25)
        # the hill itself
        hill = np.zeros(W, dtype=np.float32)
        hill = y_base - n * wobble + 10
        a = np.asarray(lay, dtype=np.float32)[..., None] / 255.0
        return a, hill

    out = img
    for y_base, step, hmin, hmax, col in (
        (790, 22, 40, 70, "#0e1b3b"),
        (860, 30, 60, 105, "#0a1530"),
        (950, 40, 90, 150, "#060d1f"),
        (1040, 52, 130, 210, "#03070f"),
    ):
        a, hill = pines(y_base, step, hmin, hmax, col)
        out = layer(out, hill, col, col, depth=1)
        out = out * (1 - a) + rgb(col) * a
    # one lit cabin window in the valley
    wl = Image.new("L", (W, H), 0)
    ImageDraw.Draw(wl).rectangle([1180, 884, 1196, 898], fill=255)
    wl = wl.filter(ImageFilter.GaussianBlur(1.0))
    glow_img = from_image(Image.merge("RGB", (wl, wl, wl))) / 255.0
    out = screen(out, glow_img * rgb("#ffb866"))
    out = glow(out, 1188, 891, 70, "#ff9a3c", 0.35)
    return finish(out, bottom=0.35)


def wall_cinema():
    rng = np.random.default_rng(71)
    img = vgrad([(0, "#0b0a0c"), (1, "#050405")])
    # projector cone from the upper right, with floating dust
    cx, cy = 1850, -80
    ang = np.arctan2(YY - cy, XX - cx)
    centre = math.radians(150)
    cone = np.exp(-((ang - centre) / 0.20) ** 2)
    dist = np.sqrt((XX - cx) ** 2 + (YY - cy) ** 2)
    cone = cone * np.exp(-dist / 1500.0)
    img = screen(img, (cone * 0.34)[..., None] * rgb("#e8c58b"))
    img = glow(img, 1500, 220, 520, "#b78a52", 0.16, ry=300)
    motes = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(motes)
    for _ in range(2600):
        x, y = rng.uniform(0, W), rng.uniform(0, H * 0.85)
        p = cone[int(y), int(x)]
        if rng.random() < p * 1.4:
            r = rng.uniform(0.6, 2.4)
            md.ellipse([x - r, y - r, x + r, y + r], fill=int(rng.uniform(70, 230) * min(1.0, p * 1.5)))
    motes = motes.filter(ImageFilter.GaussianBlur(0.8))
    img = screen(img, np.asarray(motes, dtype=np.float32)[..., None] * rgb("#ffe4b4") / 255.0)
    return finish(img, bottom=0.45, corner=0.55)


def wall_zen():
    rng = np.random.default_rng(83)
    img = vgrad([(0, "#15171a"), (0.55, "#1d2125"), (1, "#0e1012")])
    img = glow(img, 1380, 330, 330, "#9aa3a8", 0.25)
    # enso moon
    ring = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(ring)
    cx, cy, r = 1380, 330, 150
    for i in range(0, 330):
        a0 = math.radians(i * 1.0 - 20)
        w = 3 + 11 * math.sin(math.pi * i / 330) ** 0.6
        x, y = cx + r * math.cos(a0), cy + r * math.sin(a0)
        d.ellipse([x - w, y - w, x + w, y + w], fill=int(120 + 90 * math.sin(math.pi * i / 330)))
    ring = ring.filter(ImageFilter.GaussianBlur(1.6))
    img = screen(img, np.asarray(ring, dtype=np.float32)[..., None] * rgb("#c9cfd2") / 255.0 * 0.9)
    # misty ridges in ink grey
    for base_y, rough, top, bot in ((640, 140, "#3a4045", "#1a1d20"), (730, 120, "#2b3034", "#14171a"), (830, 100, "#1c2023", "#0d0f11")):
        n = fbm1d(rng, 5, 2.6, 0.5)
        img = layer(img, base_y - n * rough, top, bot, depth=240)
        mist = np.exp(-((YY - (base_y + 20)) / 60.0) ** 2)[..., None] * rgb("#6d757a") * 0.18
        img = screen(img, mist)
    return finish(img, bottom=0.4, corner=0.4)


def wall_kids():
    rng = np.random.default_rng(97)
    img = vgrad([(0, "#0c0a2c"), (0.55, "#241447"), (1, "#14102e")])
    img = glow(img, 1500, 300, 620, "#7a3fb8", 0.45, ry=420)
    img = glow(img, 420, 780, 520, "#2d5fc4", 0.30, ry=300)
    img = stars(img, rng, 260, ymax=0.9, bright=(90, 255), size=(0.8, 2.3), tint="#fff1c9")

    def planet(cx, cy, r, c_light, c_dark, bands=None, ring=None):
        nonlocal img
        d = np.sqrt((XX - cx) ** 2 + (YY - cy) ** 2)
        mask = np.clip((r - d) / 1.6, 0, 1)
        lx, ly = cx - r * 0.45, cy - r * 0.5
        shade = np.clip(1 - np.sqrt((XX - lx) ** 2 + (YY - ly) ** 2) / (r * 1.7), 0, 1) ** 0.9
        col = rgb(c_dark) * (1 - shade[..., None]) + rgb(c_light) * shade[..., None]
        if bands:
            for i, bc in enumerate(bands):
                by = cy - r + (i + 0.5) * (2 * r / len(bands))
                bm = np.exp(-((YY - by) / (r * 0.07)) ** 2) * 0.35
                col = col * (1 - bm[..., None]) + rgb(bc) * bm[..., None]
        if ring:
            back = Image.new("L", (W, H), 0)
            ImageDraw.Draw(back).ellipse([cx - r * 1.9, cy - r * 0.45, cx + r * 1.9, cy + r * 0.45], outline=200, width=int(r * 0.12))
            back = back.filter(ImageFilter.GaussianBlur(1.2))
            ringa = np.asarray(back, dtype=np.float32)[..., None] / 255.0
            front = (YY > cy)[..., None]
            behind = (~front) | (d[..., None] > r)
            img = img * (1 - ringa * behind * 0.9) + rgb(ring) * ringa * behind * 0.9
        img = img * (1 - mask[..., None]) + col * mask[..., None]
        img = glow(img, cx, cy, r * 1.6, c_light, 0.18)

    planet(1480, 300, 150, "#ffd08a", "#a2492f", bands=["#c1673c", "#f2b46b", "#b2552f", "#e8a35c"], ring="#ffe3b0")
    planet(1700, 700, 70, "#9be4ff", "#245d9c", bands=["#7fd0f5", "#2b6fb8"])
    planet(300, 330, 54, "#ffc2e0", "#7a2f86")
    # a friendly moon with craters
    d = np.sqrt((XX - 820) ** 2 + (YY - 230) ** 2)
    moon = np.clip((44 - d) / 1.5, 0, 1)[..., None]
    img = img * (1 - moon) + rgb("#f1ecd4") * moon
    for dx, dy, rr in ((-12, -8, 9), (14, 6, 6), (-2, 16, 5)):
        c = np.clip((rr - np.sqrt((XX - 820 - dx) ** 2 + (YY - 230 - dy) ** 2)) / 1.2, 0, 1)[..., None] * moon
        img = img * (1 - c * 0.45) + rgb("#b9b290") * c * 0.45
    return finish(img, bottom=0.5, corner=0.3)


def wall_synthwave():
    rng = np.random.default_rng(101)
    hz = 600
    img = vgrad([(0, "#0a0220"), (0.35, "#2a0b4d"), (0.55, "#7a1f6b"), (0.556, "#12062b"), (1, "#05010f")])
    sx, sy, sr = 960, 470, 190
    img = glow(img, sx, hz - 30, 760, "#ff3d8a", 0.55, ry=300)
    d = np.sqrt((XX - sx) ** 2 + (YY - sy) ** 2)
    disc = np.clip((sr - d) / 1.5, 0, 1) * (YY < hz)
    t = np.clip((YY - (sy - sr)) / (2 * sr), 0, 1)
    sun = rgb("#ffe36b") * (1 - t[..., None]) + rgb("#ff2f8e") * t[..., None]
    # cut horizontal slits that widen toward the bottom
    cut = np.ones_like(t)
    for i in range(9):
        y = sy + 20 + i * 18
        thick = 1.5 + i * 1.5
        cut = np.where(np.abs(YY - y) < thick, 0, cut)
    disc = disc * cut
    img = img * (1 - disc[..., None]) + sun * disc[..., None]
    img = stars(img, rng, 110, ymax=0.4, bright=(70, 220), tint="#ffd7ff")
    # mountains
    n = fbm1d(rng, 6, 4, 0.55)
    ridge = hz - 10 - np.clip(n - 0.28, 0, 1) * 220 * np.clip(np.abs(np.arange(W) - 960) / 500, 0.15, 1.4)
    a = np.clip((YY - ridge[None, :]) / 1.2 + 0.5, 0, 1)[..., None] * (YY < hz)[..., None]
    img = img * (1 - a) + rgb("#12062b") * a
    # perspective grid
    gridim = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(gridim)
    vx = 960
    for i in range(-24, 25):
        x_bottom = vx + i * 190
        gd.line([(vx + i * 8, hz), (x_bottom, H + 40)], fill=210, width=2)
    y = hz
    k = 1.0
    while y < H + 20:
        gd.line([(0, y), (W, y)], fill=int(130 + 110 * min(1, (y - hz) / 300)), width=2)
        k *= 1.28
        y = hz + 9 * k
    gridim = gridim.filter(ImageFilter.GaussianBlur(0.7))
    g = np.asarray(gridim, dtype=np.float32)[..., None] / 255.0
    g = g * np.clip((YY - hz) / 40.0, 0, 1)[..., None]
    img = screen(img, g * rgb("#ff3df0") * 0.9)
    bloom = from_image(to_image(g * rgb("#ff3df0") * 0.9).filter(ImageFilter.GaussianBlur(7)))
    img = screen(img, bloom * 0.7)
    img = glow(img, 960, hz, 900, "#ff2f8e", 0.30, ry=70)
    return finish(img, bottom=0.62, corner=0.3)


def wall_ops():
    rng = np.random.default_rng(113)
    img = vgrad([(0, "#06100b"), (1, "#030705")])
    img = glow(img, 1250, 330, 800, "#0f5a32", 0.7, ry=520)
    # faint dot grid
    grid = ((XX % 48 < 2) & (YY % 48 < 2)).astype(np.float32)
    img = screen(img, grid[..., None] * rgb("#1e8a54") * 0.28)
    # sparse code columns (glyph-like blocks if no mono font is installed)
    code = Image.new("L", (W, H), 0)
    cd = ImageDraw.Draw(code)
    font = None
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "C:/Windows/Fonts/consola.ttf",
              "/System/Library/Fonts/Menlo.ttc"):
        if os.path.exists(p):
            font = ImageFont.truetype(p, 18)
            break
    glyphs = "01{}[]<>/\\=+-*#$%&;:"
    for col in range(0, W, 38):
        if rng.random() < 0.45:
            continue
        top = int(rng.uniform(-200, 500))
        length = int(rng.uniform(8, 26))
        for r in range(length):
            y = top + r * 24
            if not (0 <= y < H):
                continue
            fade = 1 - r / length
            ch = glyphs[int(rng.integers(len(glyphs)))]
            v = int(235 * fade * rng.uniform(0.45, 1.0))
            if font:
                cd.text((col, y), ch, font=font, fill=v)
            else:
                cd.rectangle([col, y, col + 9, y + 14], fill=v)
    code = code.filter(ImageFilter.GaussianBlur(0.5))
    c = np.asarray(code, dtype=np.float32)[..., None] / 255.0
    c = c * (0.35 + 0.65 * np.clip(1 - (YY / H), 0, 1))[..., None]
    img = screen(img, c * rgb("#35d27f") * 0.55)
    return finish(img, bottom=0.55, corner=0.5)


def wall_ruby():
    """Dark crimson backdrop for the dashboard theme: the cards drawn by the app sit on it."""
    img = vgrad([(0, "#140a0d"), (1, "#070506")])
    img = glow(img, 330, 190, 1000, "#7d1620", 0.8, ry=560)
    img = glow(img, 1650, 980, 760, "#3a0b13", 0.45, ry=420)
    return finish(img, bottom=0.45, corner=0.0)


# --------------------------------------------------------------------------- previews

SCENES = {
    "halong": ("viet-scenes", "01-ha-long-dusk.jpg", scene_halong),
    "sapa": ("viet-scenes", "02-sapa-sea-of-clouds.jpg", scene_sapa),
    "hoian": ("viet-scenes", "03-hoi-an-lanterns.jpg", scene_hoian),
    "mekong": ("viet-scenes", "04-mekong-sunrise.jpg", scene_mekong),
    "hanoi": ("viet-scenes", "05-ho-guom-moonlight.jpg", scene_hanoi),
    "dalat": ("viet-scenes", "06-da-lat-stars.jpg", scene_dalat),
    "cinema": ("cinema-noir", "wallpaper.jpg", wall_cinema),
    "zen": ("zen-ink", "wallpaper.jpg", wall_zen),
    "kids": ("kids-cosmos", "wallpaper.jpg", wall_kids),
    "synth": ("synthwave", "wallpaper.jpg", wall_synthwave),
    "ops": ("ops-console", "wallpaper.jpg", wall_ops),
    "ruby": ("dashboard-ruby", "wallpaper.jpg", wall_ruby),
}

# Captions shown under the top-right buttons while viet-scenes rotates (tab-separated).
VIET_CAPTIONS = [
    ("01-ha-long-dusk.jpg", "Vịnh Hạ Long lúc hoàng hôn"),
    ("02-sapa-sea-of-clouds.jpg", "Biển mây Sa Pa"),
    ("03-hoi-an-lanterns.jpg", "Đêm đèn lồng Hội An"),
    ("04-mekong-sunrise.jpg", "Bình minh trên sông Mê Kông"),
    ("05-ho-guom-moonlight.jpg", "Hồ Gươm dưới trăng"),
    ("06-da-lat-stars.jpg", "Đà Lạt, đêm đầy sao"),
]

PREVIEW_SPEC = {
    # theme: (columns, dock count, band alpha, label style)
    "viet-scenes": dict(cols=5, dock=5, band=0.45),
    "cinema-noir": dict(cols=5, dock=5, band=0.55),
    "zen-ink": dict(cols=4, dock=4, band=0.30),
    "kids-cosmos": dict(cols=3, dock=3, band=0.40, big=True),
    "synthwave": dict(cols=5, dock=5, band=0.45),
    "ops-console": dict(cols=6, dock=5, band=0.55, names=True),
    "daylight-sky": dict(cols=5, dock=5, band=0.45),
    "dashboard-ruby": dict(cols=6, dock=6, band=0.0, cards=True, y_band=540, no_grid=True),
}
TILE_COLORS = ["#e5392f", "#1f6feb", "#12a150", "#8a3ffc", "#f2a516", "#0fb5c9", "#d6336c", "#4c6ef5"]


def sky_backdrop():
    """Approximation of the launcher's time-of-day backdrop (evening), for the preview only."""
    img = vgrad([(0, "#05070d"), (0.5, "#0d1a33"), (0.8, "#3a2f4a"), (1, "#5a3a3a")])
    return glow(img, 1500, 1000, 700, "#c8744a", 0.5, ry=260)


def font(size, bold=False):
    for p in ("/usr/share/fonts/opentype/inter/Inter-SemiBold.otf" if bold else "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/segoeui.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _draw_sample_cards(img):
    """Weather, lunar and price cards with fixed sample data, drawn like the app does."""
    from datetime import date

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core import vn_calendar, widget_cards

    data = {
        "layout": "compact",
        "weather": {"city": "Hà Nội", "temp": 29.2, "humidity": 73, "text": "Trời quang", "kind": "clear",
                    "is_day": True, "high": 33.4, "low": 25.1, "rain_chance": 12, "uv": 7.1, "aqi": 91, "forecast": []},
        "lunar": vn_calendar.lunar_card(date(2026, 10, 23)),
        "gold": {"items": [{"code": "SJL1L10", "api_name": "SJC 9999", "buy": 139e6, "sell": 142e6},
                           {"code": "SJ9999", "api_name": "SJC Ring", "buy": 138e6, "sell": 141e6}]},
        "fuel": {"zone": 1, "items": [{"name": "Xăng E10 RON 95-III", "price": 24910},
                                      {"name": "Xăng E5 RON 92-II", "price": 25060},
                                      {"name": "Dầu DO 0,05S-II", "price": 29250}]},
        "fx": {"source": "Vietcombank", "rate": 26040},
        "generated": "09:12 23/10/2026",
    }
    widget_cards.draw_dashboard(img, data, 1.0)


def make_preview(theme, wallpaper, out_path):
    """A rendered mock of Home (clock, pills, dock, tile grid). NOT a capture of a real TV."""
    spec = PREVIEW_SPEC[theme]
    w, h = 1280, 720
    if wallpaper is None:
        base = to_image(sky_backdrop()).resize((w, h), Image.LANCZOS)
    else:
        full = Image.open(wallpaper).convert("RGB").resize((1920, 1080), Image.LANCZOS)
        if spec.get("cards"):
            _draw_sample_cards(full)
        base = full.resize((w, h), Image.LANCZOS)
    im = base.convert("RGBA")
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.text((56, 38), "18:00", font=font(64, True), fill=(255, 255, 255, 245))
    d.text((60, 112), "Chủ nhật, 25 tháng 10", font=font(20), fill=(255, 255, 255, 190))
    for i, label in enumerate(("Settings", "Wi-Fi", "Inputs")):
        x1 = w - 56 - i * 130
        d.rounded_rectangle([x1 - 112, 40, x1, 80], 20, fill=(255, 255, 255, 38))
        d.text((x1 - 56, 60), label, font=font(16), fill=(255, 255, 255, 215), anchor="mm")
    big = spec.get("big")
    n = spec["dock"]
    tile = 150 if big else 112
    gap = 28 if big else 22
    total = n * tile + (n - 1) * gap
    x0 = (w - total) // 2
    y_band = spec.get("y_band", 330)
    d.rounded_rectangle([x0 - 30, y_band - 22, x0 + total + 30, y_band + tile + 22], 28, fill=(10, 12, 20, int(255 * spec["band"])))
    for i in range(n):
        x = x0 + i * (tile + gap)
        c = TILE_COLORS[i % len(TILE_COLORS)]
        col = tuple(int(c[j:j + 2], 16) for j in (1, 3, 5))
        d.rounded_rectangle([x, y_band, x + tile, y_band + tile], 20, fill=col + (235,))
        if i == 1:
            d.rounded_rectangle([x - 5, y_band - 5, x + tile + 5, y_band + tile + 5], 24, outline=(255, 255, 255, 235), width=3)
    if spec.get("names") or big:
        d.text((x0 + (tile + gap) + tile // 2, y_band + tile + 46), "YouTube", font=font(20, True), fill=(255, 255, 255, 235), anchor="mm")
    cols = spec["cols"]
    if spec.get("no_grid"):
        cols = 0
    t2 = int(tile * 0.78)
    g2 = 18
    tot2 = cols * t2 + (cols - 1) * g2
    xs = (w - tot2) // 2
    for i in range(cols):
        x = xs + i * (t2 + g2)
        c = TILE_COLORS[(i + 3) % len(TILE_COLORS)]
        col = tuple(int(c[j:j + 2], 16) for j in (1, 3, 5))
        d.rounded_rectangle([x, 560, x + t2, 560 + t2], 16, fill=col + (150,))
    d.text((w - 18, h - 14), "rendered preview, not a TV capture", font=font(13), fill=(255, 255, 255, 120), anchor="rd")
    im = Image.alpha_composite(im, ov).convert("RGB")
    im.save(out_path, "JPEG", quality=84, optimize=True)


def build(keys=None):
    todo = keys or list(SCENES)
    sizes = {}
    for key in todo:
        theme, fname, fn = SCENES[key]
        if theme == "viet-scenes":
            path = os.path.join(THEMES_DIR, theme, "wallpapers", fname)
        else:
            path = os.path.join(THEMES_DIR, theme, fname)
        sizes[key] = save_jpeg(fn(), path)
        print(f"{key:8s} -> {os.path.relpath(path, THEMES_DIR)}  {sizes[key] // 1024} KB")
    if keys is None or any(SCENES[k][0] == "viet-scenes" for k in keys):
        cap = os.path.join(THEMES_DIR, "viet-scenes", "wallpapers", "captions.txt")
        with open(cap, "w", encoding="utf-8", newline="\n") as f:
            for name, text in VIET_CAPTIONS:
                f.write(f"{name}\t{text}\n")
    # previews
    for theme in PREVIEW_SPEC:
        tdir = os.path.join(THEMES_DIR, theme)
        if theme == "viet-scenes":
            wp = os.path.join(tdir, "wallpapers", "03-hoi-an-lanterns.jpg")
        elif theme == "daylight-sky":
            wp = None
        else:
            wp = os.path.join(tdir, "wallpaper.jpg")
        if wp is None or os.path.exists(wp):
            os.makedirs(tdir, exist_ok=True)
            make_preview(theme, wp, os.path.join(tdir, "screenshot.jpg"))


if __name__ == "__main__":
    build(sys.argv[1:] or None)
