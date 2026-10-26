"""Tells a real capture of the TV from the black frame a sleeping or protected screen gives."""
from __future__ import annotations


def is_black(path: str, threshold: float = 6.0) -> bool:
    """True when the image at ``path`` is (nearly) black: its mean brightness on a 0-255 scale is below ``threshold``.

    An unreadable file counts as black, so it is never kept as a theme's preview.
    """
    try:
        from PIL import Image, ImageStat

        with Image.open(path) as im:
            small = im.convert("L")
            small.thumbnail((160, 90))
            return ImageStat.Stat(small).mean[0] < threshold
    except Exception:
        return True
