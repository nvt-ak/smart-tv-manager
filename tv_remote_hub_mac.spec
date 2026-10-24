# PyInstaller spec — build on macOS (Cocoa + pywebview).
# Usage: pyinstaller tv_remote_hub_mac.spec --noconfirm

import sys

sys.path.insert(0, "build")
from pyinstaller_common import analysis_bundle

block_cipher = None

datas, binaries, hiddenimports = analysis_bundle(
    extra_datas=[("assets/app-icon.icns", "assets")]
)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["androguard.pentest"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TVRemoteHub",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="TVRemoteHub",
)

app = BUNDLE(
    coll,
    name="TV Remote Hub.app",
    icon="assets/app-icon.icns",
    bundle_identifier="com.vinaco.tvremotehub",
)
