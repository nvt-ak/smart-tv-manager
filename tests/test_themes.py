"""Checks every bundled CleanYourTV theme before it can be pushed to a TV.

Run from the repo root:  python -m unittest tests.test_themes -v
"""
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.cleanyourtv_themes import CleanyourtvThemes  # noqa: E402
from core.theme_manager import IMAGE_RE, ThemeManager  # noqa: E402

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow is optional for the size checks
    Image = None

MAX_WALLPAPER_BYTES = 300 * 1024
MAX_SCREENSHOT_BYTES = 300 * 1024
THEMES = CleanyourtvThemes().list_themes()


class ThemeFolderTests(unittest.TestCase):
    def test_there_are_themes(self):
        self.assertGreaterEqual(len(THEMES), 1)

    def test_every_theme(self):
        for theme in THEMES:
            with self.subTest(theme=theme["id"]):
                self._check(theme)

    def _check(self, theme):
        config = theme["config"]
        self.assertTrue(config, "config.json is missing or does not parse")

        result = ThemeManager.validate_theme(theme)
        self.assertEqual(result["errors"], [])
        self.assertEqual(
            [w for w in result["warnings"] if w.startswith("Khoá không được")], [],
            "config uses a key the launcher does not know",
        )

        # A screenshot is what the gallery shows; it must be 16:9 and small.
        shot = theme["screenshot"]
        self.assertTrue(shot, "screenshot.jpg is missing")
        self.assertLessEqual(os.path.getsize(shot), MAX_SCREENSHOT_BYTES)
        if Image:
            with Image.open(shot) as im:
                self.assertEqual(im.size, (1280, 720))

        images = [theme["wallpaper"]] if theme["wallpaper"] else []
        images += theme["wallpapers"]
        for path in images:
            name = os.path.basename(path)
            self.assertRegex(name, IMAGE_RE, f"{name}: the launcher only reads simple file names")
            self.assertLessEqual(
                os.path.getsize(path), MAX_WALLPAPER_BYTES,
                f"{name}: over 300 KB is slow to decode on a 1 GB TV",
            )
            if Image:
                with Image.open(path) as im:
                    self.assertEqual(im.size, (1920, 1080), f"{name}: expected 1920x1080")

        if config.get("wallpaper"):
            self.assertTrue(images, '"wallpaper": true but the theme has no image')

        rotating = config.get("wallpaper_rotation_minutes") or config.get("wallpaper_rotation_seconds")
        if rotating:
            self.assertGreaterEqual(len(theme["wallpapers"]), 2, "rotation needs a collection")

        if config.get("wallpaper_captions"):
            self.assertTrue(theme.get("captions"), "wallpaper_captions needs wallpapers/captions.txt")
            self._check_captions(theme)

    def _check_captions(self, theme):
        names = {os.path.basename(p) for p in theme["wallpapers"]}
        with open(theme["captions"], encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f if ln.strip()]
        self.assertTrue(lines)
        for ln in lines:
            self.assertEqual(ln.count("\t"), 1, f"expected NAME<TAB>caption: {ln!r}")
            name, text = ln.split("\t")
            self.assertIn(name, names, f"caption for a picture that does not exist: {name}")
            self.assertTrue(text.strip())


class LoaderTests(unittest.TestCase):
    def test_captions_file_is_exposed_but_not_listed_as_a_picture(self):
        for theme in THEMES:
            cap = os.path.join(theme["path"], "wallpapers", "captions.txt")
            if os.path.isfile(cap):
                with self.subTest(theme=theme["id"]):
                    self.assertEqual(theme["captions"], cap)
                    self.assertNotIn(cap, theme["wallpapers"])


class ConfigRangeTests(unittest.TestCase):
    def test_validator_rejects_bad_values(self):
        bad = {"config": {"columns": 12, "background_color": "red"}, "wallpapers": []}
        result = ThemeManager.validate_theme(bad)
        self.assertFalse(result["ok"])
        self.assertTrue(any("columns" in e for e in result["errors"]))
        self.assertTrue(any("background_color" in e for e in result["errors"]))

    def test_theme_ids_are_safe_folder_names(self):
        for theme in THEMES:
            self.assertRegex(theme["id"], re.compile(r"^[a-z0-9][a-z0-9-]*$"))


if __name__ == "__main__":
    unittest.main()
