# TV Remote Hub

Desktop app: lists Android TVs on the LAN, connects over ADB with one click.
Scans every local /24 for open port 5555, or add a TV by IP manually.
Separate from `cleanyourtv`'s own ADB key — grant USB debugging again on
each TV the first time this app connects to it.

## Setup

```bash
python3.11 -m venv venv   # 3.10.8+ OK; avoid 3.10.0–3.10.7 for PyInstaller build
venv/bin/pip install -r requirements.txt
```

## Run

```bash
venv/bin/python main.py
```

## Build bản cài (macOS + Windows)

**PyInstaller không cross-compile:** trên Mac **không** tạo được file `.exe` Windows (và ngược lại). Stack pywebview còn gắn WebView2 (Win) / Cocoa (Mac) — bắt buộc build trên đúng OS.

**Không cần đổi máy tay:** dùng CI hoặc build từng nền tảng trên máy bạn có.

| Bạn đang ở | Build local | Cả hai OS một lần |
|------------|-------------|-------------------|
| **macOS** | `./scripts/build_macos.sh` → `dist/TV Remote Hub.app` | GitHub **Actions → Build release (macOS + Windows) → Run workflow** (hoặc push tag `v*`) → tải 2 artifact |
| **Windows** | `.\scripts\build_windows.ps1` → `dist\TVRemoteHub\` | Cùng workflow trên |

**Windows — máy người dùng:** cần [WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) (Win 10/11 thường đã có).

**macOS — bản unsigned:** lần mở đầu có thể **Right-click → Open**.

Tuỳ chọn: VM Windows (Parallels/UTM) trên Mac nếu bắt buộc build `.exe` offline; vẫn không thay được cross-compile từ một lệnh PyInstaller trên Mac.

User data: `~/.tv-remote-hub/` (Mac) hoặc `%USERPROFILE%\.tv-remote-hub\` (Windows).

## Notes

- Saved devices: `~/.tv-remote-hub/devices.json`.
- ADB key: `~/.tv-remote-hub/adbkey`.
- Only scans for the port being open; it does not probe/authenticate until
  you click Connect, so a scan alone never triggers a TV's debugging prompt.
