# Changelog

Mọi thay đổi đáng chú ý của **SmartTV Manager** được ghi tại đây.

Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), phiên bản theo [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Quy ước cập nhật:** mỗi lần làm tính năng / sửa lỗi / đổi build hoặc chuẩn bị tag `v*`, bổ sung mục tương ứng dưới `[Unreleased]`. Khi release, đổi `[Unreleased]` thành `[x.y.z] - YYYY-MM-DD` (tag Git phải khớp: `v1.0.1` → header `## [1.0.1]`) và mở section `[Unreleased]` trống — GitHub Release sẽ trích section đó.

---

## [Unreleased]

### Added

- **Smart Clean** (tab Quản lý ứng dụng): gợi ý offline [`data/clean_heuristics.json`](data/clean_heuristics.json), tùy chọn phân tích **OpenAI API key** (lưu `~/.smarttv-manager/settings.json`), chọn và **vô hiệu hóa hàng loạt** qua lớp `safety`.
- UI Smart Clean: Debloat Advisor (titlebar, AI card, metric pills, package cards, footer ADB) theo mock; `smart-clean.css`.

### Changed

- Smart Clean: ô API key và tìm kiếm package — một lớp viền; loại trừ input/button Smart Clean khỏi style global trong `main.css` (tránh viền lồng).

### Fixed

- Smart Clean: `merge_ai` giữ thứ tự tier (recommend → review → skip) như `analyze`.
- Tab Apps: đồng bộ phiên bản theo lô (tối đa 100 gói, 40/lần) thay vì chỉ 20 gói đầu.
- `list_devices`: chuẩn hóa `check` rỗng/khoảng trắng → `adb`; mode lạ fallback `adb`.
- `list_devices` song song: ghi `devices.json` một lần (`batch_update_online`) + khóa/temp file riêng — hết `FileNotFoundError` khi thay `.tmp`.
- Khởi động nhanh hơn: mở thẳng `index.html` + overlay boot (không splash riêng), `list_devices('cache'|'port'|'adb')` — lần đầu không chặn pywebview bằng ADB; tải phiên bản app trì hoãn (tối đa 20 gói).
- ADB Wi‑Fi: `PackageManager` dùng timeout/reconnect (tới 45s cho `pm list packages`), gộp 3 lệnh list trong một shell; timeout → xóa cache kết nối và báo lỗi tiếng Việt thay vì traceback `TcpTimeoutException`.

---

## [1.0.0] - 2026-10-24

Phát hành công khai đầu tiên — **SmartTV Manager** (desktop, Android TV qua ADB).

### Added

- Quét LAN / thêm TV thủ công, kết nối ADB TCP (5555), lưu thiết bị (`store.py`, thư mục dữ liệu người dùng).
- **Điều khiển ảo:** keyevent, mở app, gõ text, trackpad, chụp màn hình TV.
- **Quản lý app:** danh sách, bật/tắt, gỡ ([`core/safety.py`](core/safety.py)).
- **Cài APK:** phân tích manifest, preset cài, lịch sử ([`core/apk_installer.py`](core/apk_installer.py), [`core/apk_analyzer.py`](core/apk_analyzer.py)).
- **Theme Home (Gathin / cleanyourtv):** gallery, apply/backup, nhật ký apply ([`data/cleanyourtv/themes/`](data/cleanyourtv/themes/), [`core/theme_manager.py`](core/theme_manager.py)).
- **Hướng dẫn Developer / USB debugging:** tour modal, ảnh theo hãng TV (`ui/assets/guide/`).
- Màn hình **splash** trước UI chính; nền tối tránh flash khi mở app.
- [`CHANGELOG.md`](CHANGELOG.md), [`app_brand.py`](app_brand.py) (tên **SmartTV Manager**, binary `SmartTVManager`).
- Build PyInstaller (macOS / Windows), GitHub Actions: artifact + **Release** khi push tag `v*` (`SmartTVManager-macos.dmg`, `SmartTVManager-windows-x64.zip`).

### Changed

- Thư mục dữ liệu: `~/.smarttv-manager/` (lần đầu **copy** từ `~/.tv-remote-hub/` nếu đã có bản dev cũ).
- [`README.md`](README.md): build, publish, credit [cleanyourtv](https://github.com/Gathin23/cleanyourtv).

### Removed

- `PLAN.md` khỏi repo (giữ local qua `.gitignore` nếu cần).

### Fixed

- Cài APK: timeout push/install theo kích thước, reconnect ADB; UI tiến trình không kẹt 92%.
- Theme / ADB trên Wi‑Fi chậm: timeout co giãn, reconnect session.

---

[Unreleased]: https://github.com/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/releases/tag/v1.0.0
