"""Resolve application root for dev runs and PyInstaller bundles."""
import os
import sys


def app_root() -> str:
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))
