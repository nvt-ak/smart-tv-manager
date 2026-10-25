# Changelog

Mọi thay đổi đáng chú ý của **SmartTV Manager** được ghi tại đây.

Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), phiên bản theo [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Quy ước cập nhật:** mỗi lần làm tính năng / sửa lỗi / đổi build hoặc chuẩn bị tag `v*`, bổ sung mục tương ứng dưới `[Unreleased]`. Khi release, đổi `[Unreleased]` thành `[x.y.z] - YYYY-MM-DD` (tag Git phải khớp: `v1.0.1` → header `## [1.0.1]`) và mở section `[Unreleased]` trống — GitHub Release sẽ trích section đó.

---

## [Unreleased]

### Added

- Child lock ("Khoá trẻ em" tab): TV Guard, a small accessibility-service app in `tv-guard/`, enforces a lock schedule on the TV itself, so it still locks when the PC is off. Parent PIN is entered with the TV remote and stored only as a PBKDF2 hash; Settings and app stores always need the PIN. The desktop app installs it, pairs with an HMAC key, sets the PIN and schedule, shows live status, and can lock now, unlock for a while or uninstall. CI builds the APK (`.github/workflows/build-guard.yml`).
- TV Guard diagnostics report with the accessibility service state, app-ops and filtered logcat, selectable and copyable from the tab.
- Landing page: "Child lock" section with a screenshot (English and Vietnamese).

### Fixed

- Switching the active device from the Devices tab left the Apps tab and Smart Clean showing the previous TV's package list and header.
- TV Guard did not start on TCL TVs: TclAppBoot refused to bind the accessibility service (`forbid bind service ... OP_AUTO_START`) and also stalled `am broadcast`. Setup now grants `APP_AUTO_START` and background run, then re-adds the service to the enabled list to force a new bind.

## [1.6.0] - 2026-10-25

### Added

- Wireless debugging (Android 11+, e.g. Chromecast with Google TV): adding a TV on a non-5555 Wireless-debugging port opens a pairing dialog. Enter the 6-digit code; the pairing port is found over mDNS (or typed by hand), Google's platform-tools `adb` is downloaded once, the TV is paired and switched to TCP 5555, then connected as usual.
- Per-model suggestions from Gathin's `examples/` (260 profiles, pinned to the upstream commit in `data/cleanyourtv/device-profiles.json`, regenerate with `scripts/sync_device_profiles.py`). They show as suggestions only: never pre-selected, no one-click disable, and `com.mediatek.*` plus stock launcher packages are never suggested. Shown as a banner and badges in Smart Clean and as tags in the package list. Chromecast is excluded and keeps the app's own flow.
- Remote key profiles per TV: Chromecast with Google TV gets YouTube (`190`) and Netflix (`191`) buttons mapped. TCL key codes are no longer pushed to other TVs.

### Changed

- Stock launcher switch: when HOME does not move to CleanYourTV after disabling `launcherx`, the other known stock Home apps that answer HOME are disabled too (`tvlauncher`, `leanbacklauncher`, and `setupwraith` on Chromecast with Google TV, whose recovery activity otherwise outranks third-party launchers). Everything is re-enabled if HOME still does not switch. Note: disabling `setupwraith` can break phone casting after a reboot (see the Chromecast notes in Gathin's examples).
- Stock launcher status ("Disabled / Enabled") no longer depends on `launcherx` alone.
- Network scan waits longer per host (Wi-Fi TVs answer slowly) and always includes the default-route subnet.
- The version label in the header is read from `APP_VERSION` instead of a hard-coded string.

### Fixed

- Connecting with `ip:port` failed with `gaierror` because the whole string was used as the host name.
- Header label showed `v1.2.0` after newer releases.

## [1.5.0] - 2026-10-25

### Added

- Missing-launcher flow: applying a theme on a TV without CleanYourTV (`com.gathin.tvhome`) is now checked before any backup or write, then offers to install it (replaces the raw "Could not find provider" error). The Launcher panel also gets an "Install CleanYourTV" button.
- Three ways to install CleanYourTV, tried in order: a prebuilt APK (built by the new `Build CleanYourTV launcher APK` GitHub Actions workflow from the upstream commit pinned in `data/cleanyourtv/launcher-pin.json`, downloaded from the rolling `cleanyourtv-launcher` release and verified with SHA-256), a local build (clone + Gradle; needs Git, JDK 17-21 with jlink, Android SDK), or a user-supplied APK file. The upstream MIT license ships with the release.
- Real progress for the install flow (read, download/build, push, `pm install`) in the "Theme apply log" panel.
- App management: "Uninstall" button for user apps (`pm uninstall`, with confirmation). System, protected and the active Home apps are excluded, except CleanYourTV, which re-enables the stock launcher first so the TV never loses Home.

### Fixed

- "Active theme" now shows "Not applied" when CleanYourTV is no longer the default Home (e.g. after resetting the stock launcher) and refreshes right after the reset.
- Literal `\n` shown in the "Reset stock launcher" confirmation.

## [1.4.0] - 2026-10-24

### Added

- Panel **Phát hiện Launcher** gọn lại: trạng thái CleanYourTV / launcher gốc / phím HOME, nút «Đặt lại launcher gốc» (bật lại Google TV Launcher).
- Áp dụng theme **tự tắt launcher gốc** (`com.google.android.apps.tv.launcherx`) để phím HOME vật lý mở Gathin; kiểm tra HOME → Gathin, tự bật lại nếu không được; ô tick «Tự tắt launcher gốc khi áp dụng theme».
- Gán sẵn phím remote TCL: Settings (`4077`), TV (`4001` → `com.tcl.tv`), Netflix, YouTube, Prime Video, Media (`app_keys`); mở rộng qua `remote_keys` trong `settings.json`.
- Widget vàng/xăng: theme không có ảnh nền (VD Default) được vẽ lên nền `background_color` và tự bật `wallpaper: true`; báo lỗi rõ khi không vẽ được.

### Changed

- Áp dụng theme khởi động lại Home đúng một lần ở cuối (sau khi tắt launcher gốc), có thử lại.
- Ô «Theme nền» của widget bám theme đang áp dụng; nhận diện theme đang dùng ưu tiên theme vừa áp dụng.
- Khởi động lại Home luôn bật cả `HomeKeyService` và `InputKeyService` (nút TV / nguồn vào).

### Removed

- Nút «Đặt làm Home mặc định» (firmware TV không cho đổi qua ADB) và nút «Sao chép nội dung trạng thái».

## [1.3.1] - 2026-10-24

### Added

- Màn Ứng dụng: bảng tên thân thiện cho các package phổ biến trên TV (Netflix, Prime Video, TCL Media Center, …) và đoán tên tốt hơn cho package còn lại.
- Màn Ứng dụng: tab lọc **Đang bật**.

### Changed

- Tìm app: khớp «chứa» theo cả tên và package id, nhiều từ khoá, không phân biệt dấu/hoa thường.

### Fixed

- Cài APK: đẩy file vào `/data/local/tmp` thay vì `/sdcard/Download` (SELinux `avc: denied fuse` làm `pm install` không đọc được file trên TV TCL).

## [1.3.0] - 2026-10-24

### Added

- Widget **giá vàng** (đủ mục API vang.today) và **giá xăng dầu** (đủ mục Petrolimex) dạng thẻ kính tối theo thiết kế Stitch (Inter + JetBrains Mono), **vẽ thẳng vào wallpaper** khi áp dụng theme hoặc bấm «Áp dụng lên TV» (cần `pillow`; font trong `assets/fonts`).
- Panel widget gọn: chọn theme nền, vùng xăng, các mục hiển thị; cấu hình tự lưu, giá tự lấy từ API mỗi lần áp dụng.
- Tab **Home & Theme**: nút «Đặt làm Home mặc định», «Chẩn đoán Home», sao chép nhật ký trạng thái.

### Removed

- Widget Home: bỏ hoàn toàn **thời tiết** và **lấy vị trí máy tính** (CoreLocation, Open-Meteo, geocode); gỡ `core/host_location.py`, `pyobjc-framework-CoreLocation`/`libdispatch` và quyền vị trí trong Info.plist macOS.
- Bỏ các ô nhập tay vàng/xăng dự phòng và phần xem trước trong panel widget.

### Changed

- Theme đang dùng được nhận diện bỏ qua các khoá do widget ghi (`greeting_name`, `show_stats`, `always_show_names`, `module_cards`) và nhớ theme áp dụng gần nhất.
- Giảm kết nối ADB thừa: tái dùng phiên đã cache (phím remote, danh sách thiết bị, tab Theme); vẫn kết nối mới khi áp dụng theme.
- Phát hiện launcher / Home mặc định nhanh và chính xác hơn (một lượt shell, không còn báo «chưa cài» sai).

### Fixed

- Build Windows: gói `pythonnet`/`clr_loader` vào PyInstaller, tắt UPX (lỗi khởi động pywebview).
- Lỗi kết nối ADB (TCP timeout) được báo rõ lên giao diện.

## [1.2.0] - 2026-10-24

Smart Clean làm mới danh sách app; cải thiện vô hiệu hóa ADB trên tab Quản lý ứng dụng.

### Added

- Smart Clean: nút **Làm mới app** — đồng bộ `pm list` từ TV, quét lại theo chế độ Offline/AI hiện tại; giữ bộ lọc, tìm kiếm, cấu hình AI và gói đã «Bỏ qua».

### Changed

- Quản lý ứng dụng: sau vô hiệu hóa/bật lại, cập nhật UI ngay; `pm list` chạy nền (không chặn nút); hàng loạt có **Hủy thao tác ADB** (dừng sau gói đang chạy trên TV).

### Fixed

- Quản lý ứng dụng (ADB): `pm disable-user` / `pm enable` dùng `--user 0`, kiểm tra output và xác nhận trạng thái trên TV; danh sách package tính «đã tắt» từ `pm list -e` (tránh lệch sau vô hiệu hóa); hủy đồng bộ phiên bản nền khi tải lại để UI không hiện lại «đang bật».
- Quản lý ứng dụng: bỏ xác minh `pm list -e` toàn máy sau mỗi lần tắt/bật (chỉ khi output `pm` không rõ) — giảm thời gian chờ trên Wi‑Fi.

---

## [1.1.0] - 2026-10-24

Smart Clean / Debloat Advisor, cải thiện ADB & khởi động, sửa build CI PyInstaller.

### Added

- Smart Clean AI: override **Base URL** OpenAI-compatible (`settings.json`), **Test Ping** trả danh sách model và chọn model trong dropdown trước khi quét AI.
- **Smart Clean** (tab Quản lý ứng dụng): gợi ý offline [`data/clean_heuristics.json`](data/clean_heuristics.json), tùy chọn phân tích **OpenAI API key** (lưu `~/.smarttv-manager/settings.json`), chọn và **vô hiệu hóa hàng loạt** qua lớp `safety`.
- UI Smart Clean: Debloat Advisor (titlebar, AI card, metric pills, package cards, footer ADB) theo mock; `smart-clean.css`.

### Changed

- Smart Clean AI: system prompt phân loại package (tier/category/confidence, quy tắc skip cứng); user payload gồm `current_home_package`, `label`, `is_system`, `has_launcher_icon`; parse `results[]`; merge lưu `ai_category` / `ai_confidence`.
- Smart Clean: panel cấu hình AI **lưới gọn** (API key + nút Lưu/Ping; Base URL / Model **50–50**); bỏ khối mô tả trùng; badge model không uppercase.
- Smart Clean: modal **gần full màn hình** (viền 4px); thẻ package, toolbar, footer và panel AI **compact** hơn; panel AI mở có scroll nội bộ để ưu tiên diện tích danh sách.
- Smart Clean: panel «Gợi ý AI & tối ưu thông minh» thu gọn (`<details>`), **mặc định đóng** — danh sách gói chiếm phần lớn màn hình; viền thẻ package gọn (một `border-left`).
- Smart Clean: ô API key và tìm kiếm package — một lớp viền; loại trừ input/button Smart Clean khỏi style global trong `main.css` (tránh viền lồng).

### Fixed

- CI/release: `packaging/pyinstaller_common.py` (tracked) — spec import từ `packaging/` thay `build/` (gitignore) để PyInstaller trên GitHub Actions không lỗi `ModuleNotFoundError`.
- `get_package_info`: lệnh `pm list packages -e` dùng `SHELL_HEAVY_TIMEOUT` (45s) thay 8s trên Wi‑Fi chậm.
- `_device_props`: `getprop` có timeout `SHELL_DEFAULT_TIMEOUT` (25s).
- `store.py`: `upsert` / `rename` / `remove` / `batch_update_online` trả snapshot list (không alias nội bộ); ghi file qua `_write_devices_file` trong lock (không gọi `save()` lồng lock — không deadlock).
- Smart Clean AI: handler lỗi không tham chiếu `llm_model` khi chưa gán; `run_shell` không dùng `assert` cho luồng lỗi.
- Smart Clean: chọn model — state `smartCleanSelectedModelId`, `mousedown` trên dropdown, không autoPick sau Ping; `applyPopulatePick` giữ model user khi locked.
- Smart Clean: logic chọn model tách `smart_clean_model_logic.js` + test Node (`tests/smart_clean_model_logic.test.mjs`); **userLocked** sau khi chọn tay — fetch/sync không nhảy về default.
- Smart Clean: chọn model không bị ghi đè bởi default/settings khi fetch nền hoặc sync; bỏ sync form sau Lưu Key (tránh nhảy model).
- Smart Clean: trạng thái **Đã chọn** model (viền xanh, badge, dòng meta); blur ô tìm sync lại; quét AI chỉ khi model nằm trong danh sách đã tải; **tự fetch model** khi mở modal nếu key đã lưu.
- Smart Clean: Test Ping tải **toàn bộ** model (không cắt 200); combobox **tìm kiếm** model; badge/mode tag hiển thị model đã chọn; proxy/local **không** fallback `gpt-4o-mini` — bắt chọn model sau Ping.
- Smart Clean: quét AI dùng **model + Base URL** từ form (tránh 401 `gpt-4o-mini` trên proxy local); loading danh sách + «đang quét…» trên nút Offline/AI; đổi model tự lưu settings.
- Smart Clean: Test Ping không ghi đè dropdown model sau sync; proxy local (1500+ model) giới hạn ~200 mục (`auto/*` ưu tiên); HTTP localhost không bắt SSL.
- Smart Clean / OpenAI: HTTPS dùng CA bundle `certifi` (hết `SSL: CERTIFICATE_VERIFY_FAILED` trên macOS Python); thông báo lỗi SSL gợi ý cài cert.
- Smart Clean: **Lưu Key** / **Test Ping** — spinner «Đang lưu…» / «Đang ping…»; Test Ping trả `{ok, error}` (không traceback khi thiếu key); lưu settings không xóa key khi ô key trống.
- Smart Clean: `merge_ai` giữ thứ tự tier (recommend → review → skip) như `analyze`.
- Tab Apps: đồng bộ phiên bản theo lô (tối đa 100 gói, 40/lần) thay vì chỉ 20 gói đầu.
- `list_devices`: chuẩn hóa `check` rỗng/khoảng trắng → `adb`; mode lạ fallback `adb`.
- `device_shell` / gõ text remote: timeout shell 25–45s, reconnect một lần, xóa cache ADB khi timeout — message tiếng Việt thay traceback.
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

[Unreleased]: https://github.com/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/releases/tag/v1.0.0
