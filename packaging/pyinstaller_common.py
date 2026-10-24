"""Shared PyInstaller Analysis inputs (imported from *.spec files)."""
import sys

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules


def _androguard_bundle():
    """APK tab uses androguard.misc only — not pentest/frida."""
    datas = collect_data_files("androguard")
    hiddenimports = [
        "androguard.misc",
        "androguard.core.bytecodes.apk",
        "androguard.core.axml",
        "androguard.core.analysis.analysis",
        "androguard.util",
    ]
    return datas, [], hiddenimports


def analysis_bundle(extra_datas=None):
    binaries = []
    datas = [
        ("ui", "ui"),
        ("data", "data"),
    ]
    if extra_datas:
        datas.extend(extra_datas)

    hiddenimports = collect_submodules("adb_shell") + [
        "paths",
        "certifi",
        "core.host_location",
        "cryptography.hazmat.backends.openssl",
        "cryptography.hazmat.bindings._rust",
    ]

    wv_datas, wv_binaries, wv_hidden = collect_all("webview")
    datas += wv_datas
    binaries += wv_binaries
    hiddenimports += wv_hidden

    ag_datas, _, ag_hidden = _androguard_bundle()
    datas += ag_datas
    hiddenimports += ag_hidden

    if sys.platform == "darwin":
        hiddenimports += ["CoreLocation"]

    return datas, binaries, hiddenimports
