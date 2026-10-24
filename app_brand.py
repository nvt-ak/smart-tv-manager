"""Display name, build identifiers, and per-user data directory."""

from __future__ import annotations

import os
import shutil

APP_DISPLAY_NAME = "SmartTV Manager"
APP_VERSION = "1.4.0"
APP_EXE_NAME = "SmartTVManager"
APP_MACOS_BUNDLE_NAME = f"{APP_DISPLAY_NAME}.app"
APP_BUNDLE_ID = "com.vinaco.smarttvmanager"

USER_DATA_DIRNAME = ".smarttv-manager"
LEGACY_USER_DATA_DIRNAME = ".tv-remote-hub"


def user_data_dir() -> str:
    """~/.smarttv-manager — copy from legacy ~/.tv-remote-hub on first run if needed."""
    home = os.path.expanduser("~")
    new_dir = os.path.join(home, USER_DATA_DIRNAME)
    legacy_dir = os.path.join(home, LEGACY_USER_DATA_DIRNAME)
    if os.path.isdir(new_dir):
        return new_dir
    if os.path.isdir(legacy_dir):
        try:
            shutil.copytree(legacy_dir, new_dir)
            return new_dir
        except OSError:
            return legacy_dir
    os.makedirs(new_dir, mode=0o700, exist_ok=True)
    return new_dir
