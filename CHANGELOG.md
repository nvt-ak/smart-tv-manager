# Changelog

Mọi thay đổi đáng chú ý của **SmartTV Manager** được ghi tại đây.

Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), phiên bản theo [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Quy ước cập nhật:** mỗi lần làm tính năng / sửa lỗi / đổi build hoặc chuẩn bị tag `v*`, bổ sung mục tương ứng dưới `[Unreleased]`. Khi release, đổi `[Unreleased]` thành `[x.y.z] - YYYY-MM-DD` (tag Git phải khớp: `v1.0.1` → header `## [1.0.1]`) và mở section `[Unreleased]` trống — GitHub Release sẽ trích section đó.

---

## [Unreleased]

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
