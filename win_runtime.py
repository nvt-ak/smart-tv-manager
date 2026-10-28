"""Windows startup hardening for the packaged (PyInstaller) app.

pywebview's Windows backend loads Python.Runtime.dll through pythonnet/clr_loader.
When the release zip is downloaded and extracted by Explorer, every file carries a
``Zone.Identifier`` alternate data stream (Mark-of-the-Web) and the .NET loader can
refuse the DLL, which surfaces as
"Failed to resolve Python.Runtime.Loader.Initialize". Removing that stream before
the backend loads fixes it without asking the user to run PowerShell.

Everything here is best-effort and never raises.
"""
import os
import sys
import traceback

ZONE_STREAM = ":Zone.Identifier"
LOG_NAME = "startup-error.log"

# Files the Windows backend cannot work without, relative to the bundle root.
REQUIRED_RUNTIME_FILES = (
    os.path.join("pythonnet", "runtime", "Python.Runtime.dll"),
    os.path.join("clr_loader", "ffi", "dlls", "amd64", "ClrLoader.dll"),
)


def unblock_tree(root: str) -> int:
    """Delete the Mark-of-the-Web stream from every file under ``root``.

    Returns the number of files that were unblocked. No-op off Windows.
    """
    if os.name != "nt" or not root or not os.path.isdir(root):
        return 0
    removed = 0
    for folder, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(folder, name)
            try:
                os.remove(path + ZONE_STREAM)
                removed += 1
            except OSError:
                pass  # no stream, locked file or non-NTFS volume
    return removed


def missing_runtime_files(root: str) -> list:
    """Return the required backend files that are absent from the bundle."""
    found = []
    for base in (root, os.path.join(root, "_internal")):
        found = [rel for rel in REQUIRED_RUNTIME_FILES if not os.path.isfile(os.path.join(base, rel))]
        if not found:
            return []
    return found


def explain_failure(exc: BaseException, root: str) -> str:
    """Build a user-facing message (Vietnamese) for a failed backend start."""
    detail = f"{type(exc).__name__}: {exc}"
    lines = ["SmartTV Manager không khởi động được giao diện.", "", detail, ""]
    missing = missing_runtime_files(root)
    if missing:
        lines += ["Thiếu file trong bản cài: " + ", ".join(missing),
                  "-> Tải lại bản zip và giải nén đầy đủ (không chạy trực tiếp trong zip)."]
    else:
        lines += [
            "Cách xử lý:",
            "1. Chuột phải file .zip -> Properties -> tick Unblock -> OK, rồi giải nén lại",
            "   vào đường dẫn ngắn như C:\\Tools\\SmartTVManager.",
            "2. Kiểm tra Windows Security -> Protection history có chặn Python.Runtime.dll không.",
            "3. Cài .NET Framework 4.8 và WebView2 Runtime.",
        ]
    lines += ["", "Nhật ký lỗi đầy đủ: " + log_path()]
    return "\n".join(lines)


def log_path() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "SmartTVManager", LOG_NAME)


def write_log(exc: BaseException) -> str:
    path = log_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    except OSError:
        pass
    return path


def show_fatal(title: str, message: str) -> None:
    """Native message box on Windows; stderr elsewhere."""
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)  # MB_ICONERROR
            return
        except Exception:
            pass
    print(f"{title}\n{message}", file=sys.stderr)


def start_guarded(start, root: str, title: str) -> None:
    """Run ``start`` (webview.start); on failure log it and show actionable guidance."""
    unblock_tree(root)
    try:
        start()
    except Exception as exc:
        write_log(exc)
        show_fatal(title, explain_failure(exc, root))
        raise SystemExit(1)
