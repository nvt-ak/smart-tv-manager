"""Load themes from local cleanyourtv/themes."""
import json
import os
from typing import Any, Dict, List


class CleanyourtvThemes:
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cleanyourtv", "themes")
        self.base_dir = base_dir

    def list_themes(self) -> List[Dict[str, Any]]:
        themes = []
        if not os.path.isdir(self.base_dir):
            return themes
        for name in sorted(os.listdir(self.base_dir)):
            path = os.path.join(self.base_dir, name)
            if not os.path.isdir(path):
                continue
            config_path = os.path.join(path, "config.json")
            config = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, encoding="utf-8") as f:
                        config = json.load(f)
                except Exception:
                    config = {}
            screenshot = None
            for fn in ["screenshot.jpg", "screenshot.png"]:
                sp = os.path.join(path, fn)
                if os.path.exists(sp):
                    screenshot = sp
                    break
            wallpaper = None
            for fn in ["wallpaper.jpg", "wallpaper.png"]:
                wp = os.path.join(path, fn)
                if os.path.exists(wp):
                    wallpaper = wp
                    break
            wallpapers_dir = os.path.join(path, "wallpapers")
            wallpapers = []
            if os.path.isdir(wallpapers_dir):
                for fn in sorted(os.listdir(wallpapers_dir)):
                    if fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                        wallpapers.append(os.path.join(wallpapers_dir, fn))
            themes.append({
                "id": name,
                "name": name.replace("-", " ").title(),
                "path": path,
                "config": config,
                "screenshot": screenshot,
                "wallpaper": wallpaper,
                "wallpapers": wallpapers,
                "has_config": bool(config),
            })
        return themes
