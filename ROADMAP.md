# SmartTV Manager — Product & Implementation Plan

## 1. Mục tiêu

Xây dựng ứng dụng desktop giúp người dùng quản lý Android TV trong mạng nội bộ:

- Tìm và kết nối TV qua ADB.
- Điều khiển TV như remote.
- Quản lý ứng dụng và package an toàn.
- Cài APK từ máy tính.
- Áp dụng theme, wallpaper và bố cục Home cho launcher `com.gathin.tvhome`.
- Sao lưu, khôi phục và dọn dẹp TV theo cơ chế an toàn của `cleanyourtv`.

Ứng dụng phải ưu tiên tính phục hồi: mọi thao tác có thể ảnh hưởng hệ thống đều cần kiểm tra trước, ghi lại trạng thái và có đường hoàn tác.

## 2. Kiến trúc dự kiến

- **Desktop shell:** Python + pywebview.
- **UI:** HTML/CSS/JavaScript chạy trong webview.
- **Device bridge:** `adb-shell`, kết nối trực tiếp TCP tới TV.
- **Local storage:** JSON trong `~/.smarttv-manager/`; có thể chuyển sang SQLite khi dữ liệu và lịch sử thao tác tăng.
- **Nguồn dữ liệu tham khảo:** theme và danh sách debloat từ repo `cleanyourtv`.
- **Bảo mật:** ADB key riêng, lưu với quyền chỉ tài khoản hiện tại được đọc; không mở server ra LAN hoặc Internet.

## 3. Use case chính

### UC-01 — Khám phá và quản lý thiết bị

- Quét tất cả subnet IPv4 cục bộ, mặc định tìm cổng ADB `5555`.
- Thêm thiết bị thủ công bằng IP và port.
- Kết nối, xác thực và đọc model, hãng, Android version, build.
- Lưu, đổi tên và xoá thiết bị.
- Hiển thị trạng thái online/offline và thời điểm thấy thiết bị gần nhất.
- Phân biệt thiết bị Android không phải TV và cảnh báo trước khi lưu.

### UC-02 — Cấp quyền ADB

- Giải thích rõ bước bật Developer options và Wireless/USB debugging.
- Khi kết nối lần đầu, hiển thị trạng thái “Đang chờ bạn chấp nhận trên TV”.
- Cho phép thử lại mà không phải quét lại.
- Hỗ trợ pairing code của Wireless debugging ở giai đoạn sau.

### UC-03 — Điều khiển từ xa

- D-pad: lên, xuống, trái, phải và OK.
- Home, Back, Menu, Settings và Inputs khi firmware hỗ trợ.
- Power, volume up/down/mute và media play/pause.
- Chống gửi lặp ngoài ý muốn; hiển thị lỗi khi key bị firmware chặn.
- Giai đoạn sau: phím tắt mở ứng dụng và remote tuỳ biến.

### UC-04 — Quản lý ứng dụng và package

- Liệt kê app người dùng, app hệ thống và package đang disabled.
- Hiển thị label, package name, version, dung lượng nếu lấy được.
- Tìm kiếm, lọc theo loại và trạng thái.
- Mở app, force-stop, mở App info.
- Enable/disable package với safety guard bắt buộc.
- Không cho disable Android core, System UI, Settings, package installer, permission controller hoặc Home hiện tại.
- Đánh dấu package được `cleanyourtv` xác nhận có thể disable theo model.
- “Gỡ cài đặt” phải phân biệt rõ:
  - App người dùng: có thể uninstall.
  - App hệ thống: mặc định chỉ disable, không giả vờ xoá khỏi firmware.

### UC-05 — Dọn dẹp thông minh

- Phân tích package theo model và đối chiếu danh sách đã kiểm chứng.
- Chia gợi ý thành: an toàn, cần cân nhắc và không được chạm.
- Giải thích ảnh hưởng dự kiến của từng package.
- Cho người dùng xem toàn bộ thay đổi trước khi chạy.
- Lưu snapshot trước thay đổi và hỗ trợ restore.
- Kiểm tra drift sau firmware update.
- Không tự động dọn dẹp nền nếu chưa có xác nhận rõ ràng.

### UC-06 — Cài đặt APK

- Chọn hoặc kéo-thả file APK.
- Đọc package, version, min SDK, chữ ký và quyền trước khi cài.
- Cảnh báo APK đổi signing certificate hoặc xin quyền nhạy cảm.
- Push APK, xác minh checksum, cài đặt và xoá file tạm trên TV.
- Hỗ trợ reinstall/update và báo lỗi dễ hiểu.
- Không xây kho APK không kiểm chứng trong giai đoạn đầu.

### UC-07 — Theme, wallpaper và Home layout

Chỉ bật khi phát hiện `com.gathin.tvhome`:

- Hiển thị theme từ repo `cleanyourtv`, kèm screenshot preview.
- Áp dụng hoặc reset theme.
- Chọn wallpaper riêng; validate định dạng, kích thước và tối ưu ảnh.
- Tạo theme cơ bản từ form.
- Cấu hình columns, rows, dock, app names, motion, background và wallpaper.
- Sắp xếp, ẩn/hiện app trên Home.
- Backup cấu hình hiện tại trước khi ghi.

Nếu TV dùng launcher OEM, UI phải nói rõ tính năng này không tương thích thay vì cố ghi cấu hình.

### UC-08 — Backup, restore và lịch sử

- Snapshot package states, Home owner và launcher config.
- Ghi lịch sử thao tác theo thiết bị.
- Restore toàn bộ hoặc từng thay đổi.
- Export/import cấu hình thiết bị, không export private ADB key mặc định.

### UC-09 — Quản lý nhiều TV

- Nhóm TV theo phòng hoặc địa điểm.
- Chạy thao tác hàng loạt với bước preview và xác nhận.
- Không áp một debloat profile cho model khác nếu chưa xác nhận tương thích.

## 4. Roadmap triển khai

### Phase 0 — Foundation — hoàn thành

- Scan subnet cổng 5555.
- Thêm IP thủ công.
- Connect và probe TV.
- Lưu/xoá thiết bị.
- UI desktop cơ bản.

### Phase 1 — Device status và Remote — đã duyệt, ưu tiên hiện tại

- Online/offline badge.
- `last_seen`.
- Đổi tên TV.
- Remote D-pad, OK, Home, Back, Power và Volume.
- Cải thiện lỗi kết nối và trạng thái chờ cấp quyền.

**Acceptance criteria**

- Trạng thái nhiều TV được cập nhật mà không treo UI.
- Poll không làm xuất hiện lại prompt ADB.
- Đổi tên còn nguyên sau khi khởi động lại.
- Mỗi remote key chỉ gửi tới thiết bị đang được chọn.
- Mất kết nối được báo rõ và app vẫn hoạt động.

### Phase 2 — App inventory

- Danh sách app/package.
- Search và filters.
- Mở app, force-stop, App info.
- Enable/disable với protected-package guard.
- Nhận diện launcher/Home đang hoạt động.

**Acceptance criteria**

- Không thể disable package thuộc danh sách bảo vệ.
- Không thể disable Home duy nhất.
- Danh sách app không chặn UI trên TV có nhiều package.
- Sau thao tác, trạng thái package được đọc lại từ TV.

### Phase 3 — APK installer

- File picker và drag/drop.
- Phân tích metadata và chữ ký.
- Push/install/update.
- Progress, cleanup và error mapping.

**Acceptance criteria**

- File tạm luôn được xoá sau thành công hoặc thất bại.
- Cảnh báo trước khi downgrade, đổi chữ ký hoặc cài app quyền nhạy cảm.
- Không chạy shell bằng tên file chưa được kiểm tra.

### Phase 4 — Theme và Home customization

- Phát hiện `com.gathin.tvhome`.
- Theme gallery từ `cleanyourtv`.
- Preview, apply và reset.
- Wallpaper custom.
- Layout editor và app ordering.

**Acceptance criteria**

- Theme lỗi không làm Home mất khả năng khởi động.
- Luôn backup config trước apply.
- Chỉ hiện editor khi launcher tương thích.
- Ảnh được validate và tối ưu trước khi push.

### Phase 5 — Smart cleanup và debloat

- Match model với profile đã kiểm chứng.
- Safety classification và impact preview.
- Snapshot, apply, drift check và restore.
- Port đầy đủ guard từ `disable.sh`; không viết bản guard rút gọn.

**Acceptance criteria**

- Chặn core packages, package installer, TV input quan trọng và Home hiện tại.
- Kiểm tra ownership của Wi-Fi/setup wizard.
- Snapshot thành công trước lệnh thay đổi đầu tiên.
- Restore hoạt động sau khi app desktop bị đóng và mở lại.

### Phase 6 — Advanced operations

- Wake-on-LAN khi phần cứng hỗ trợ.
- Pairing code cho Android Wireless debugging.
- Screenshot viewer.
- Nhóm nhiều TV và batch actions.
- Tray app và thông báo trạng thái.
- Diagnostics: storage, memory, uptime, Wi-Fi.

## 5. Tính năng thông minh đề xuất

- **Device fingerprint:** dùng manufacturer/model/device/build để tránh nhầm TV sau khi DHCP đổi IP.
- **Compatibility score:** đánh giá mức phù hợp của debloat profile thay vì chỉ so tên model.
- **Risk engine:** tính mức rủi ro dựa trên package role, permissions, Home owner và TV input services.
- **Change simulator:** trình bày trước package nào bị disable, app nào biến mất và chức năng nào có thể ảnh hưởng.
- **Health baseline:** ghi dung lượng, RAM và package count trước/sau cleanup để chứng minh tác dụng.
- **Recovery assistant:** nếu Home hoặc network có dấu hiệu lỗi, ưu tiên đề xuất restore thay vì tiếp tục thay đổi.
- **Audit trail:** lưu ai/thiết bị/thời điểm/thao tác/kết quả để hỗ trợ gia đình có nhiều TV.
- **Theme validator:** kiểm tra key, contrast, wallpaper memory cost và launcher compatibility trước khi apply.

## 6. Nguyên tắc an toàn

- ADB chỉ dùng trong LAN hoặc mạng riêng như Tailscale; không hướng dẫn mở cổng 5555 ra Internet.
- Mọi giá trị đưa vào shell phải được whitelist hoặc quote an toàn.
- Disable thay cho uninstall đối với app hệ thống.
- Thao tác phá huỷ cần preview, xác nhận và restore point.
- Không lưu APK hoặc dữ liệu người dùng lên cloud nếu chưa có thiết kế quyền riêng tư riêng.
- Không tự động chạy cleanup trên thiết bị vừa được phát hiện.

## 7. Thứ tự thực hiện đã chốt

1. Hoàn thiện Phase 1.
2. Xây App inventory và safety layer ở Phase 2.
3. Xây APK installer.
4. Xây Theme/Home customization.
5. Chỉ sau khi các phần trên ổn định mới triển khai debloat runner đầy đủ.

Mỗi phase cần unit test cho logic không phụ thuộc TV, integration test với mock ADB và kiểm thử trên ít nhất một TV thật trước khi đánh dấu hoàn thành.
