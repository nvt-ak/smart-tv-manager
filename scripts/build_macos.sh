#!/usr/bin/env bash
# Build TV Remote Hub .app on macOS (must run on a Mac).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
"$PYTHON" - <<'PY'
import sys
v = sys.version_info
if v < (3, 10, 8) and v[:2] == (3, 10):
    sys.exit(
        "Python 3.10.0–3.10.7 breaks PyInstaller (dis IndexError). "
        "Use 3.10.8+ or 3.11+: e.g. python3.11 -m venv venv && source venv/bin/activate"
    )
if v < (3, 10):
    sys.exit("Need Python 3.10 or newer for build.")
PY

"$PYTHON" -m pip install -r requirements.txt -r requirements-build.txt
"$PYTHON" -m PyInstaller tv_remote_hub_mac.spec --noconfirm --clean

echo ""
echo "Build OK: $ROOT/dist/TV Remote Hub.app"
echo "Tip: zip the .app for distribution; first open may need Right-click → Open (unsigned)."
