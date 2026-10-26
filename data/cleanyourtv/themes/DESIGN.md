# Thiết kế theme cho launcher CleanYourTV

Tài liệu nội bộ cho Smart TV Manager: launcher cho phép tuỳ biến những gì, giới hạn ở đâu, và cách ghép
chúng thành một theme có cá tính. Mọi điều dưới đây lấy từ `README.md` cùng thư mục (bảng khoá) và từ
`core/theme_manager.py`; chỗ nào chưa thử trên TV thật thì ghi rõ "chưa kiểm chứng".

## 1. Theme thực chất là gì

Một theme là **một thư mục** trong `data/cleanyourtv/themes/`. App tự quét, không cần đăng ký:

| File | Bắt buộc | Vai trò |
|---|---|---|
| `config.json` | có | Lớp phủ lên `config.xml` của launcher. Khoá thiếu thì giữ mặc định, khoá lạ bị bỏ qua, file hỏng bị bỏ cả file nên theme không thể làm Home hỏng |
| `wallpaper.jpg` | không | Một ảnh nền |
| `wallpapers/*.jpg\|png\|webp` | không | Bộ sưu tập xoay vòng (tối đa 100 ảnh, mỗi ảnh ≤ 10 MB) |
| `wallpapers/captions.txt` | không | Dòng `tên-file<TAB>chú thích`, hiện dưới các nút góc phải khi bật `wallpaper_captions` |
| `screenshot.jpg` | app dùng để hiện gallery | 1280×720, ≤ 300 KB |

Khi áp dụng (`ThemeManager.apply_theme`): kiểm tra hợp lệ → ghi `config.json` qua `ThemeProvider` của launcher →
ghi ảnh → đổi `theme_revision` (xoá các lựa chọn cột/chuyển động đặt trên TV) → khởi động lại Home.
Hai thứ app tự chèn thêm khi áp dụng, theme không cần lặp lại: `tile_menu: true` (nếu theme không đặt) và
phím remote theo dòng TV (TCL, Chromecast).

## 2. Các "đòn bẩy" thực sự có

Cá tính của một theme đến từ việc ghép các nhóm sau. Tên khoá là khoá thật trong `config.json`.

| Nhóm | Khoá | Tác động nhìn thấy được |
|---|---|---|
| Bố cục | `columns` (1–8), `rows_below_dock` (0–3), `dock_row`, `dock_title`, `always_show_names`, `fill_dock`, `dock_apps`, `hidden_apps` | Mật độ, kích thước ô, có hàng dock riêng hay không, tên app |
| Thanh trên | `top_menu`, `icon_only_buttons`, `show_network_pill`, `show_inputs_pill`, `wifi_label_width`, `library_button`, `launcher_settings_button` | Từ ba nút chữ đến một bánh răng tròn duy nhất |
| Bề mặt | `cinematic_home`, `dock_glass`, `dock_opacity` (30–100), `app_glow`, `ambient_glow`, `glow_style` (`radial`/`horizon`) | Kính mờ, vệt sáng theo màu app, kệ điện ảnh |
| Nền | `background_color`, `wallpaper`, `wallpapers/`, `wallpaper_rotation_*`, `wallpaper_order`, `wallpaper_dim`, `wallpaper_captions`, `wallpaper_true_color`, `sky_intensity` | Ảnh tĩnh, bộ ảnh xoay, bầu trời đổi theo giờ |
| Chuyển động | `focus_overshoot`, `advanced_effects`, `animations`, `reduced_motion` | Nảy vui hay trượt êm |
| Thời gian | `home_idle_clock_minutes`, `show_stats`, `greeting_name` | Màn hình đồng hồ khi nhàn rỗi, dòng CPU/RAM |
| Lễ hội | `festival` + `festival_until` + `accent_color` + `greeting` | Chỉ `dussehra` và `diwali` có sẵn lời chào; kiểu Ấn Độ (đèn diya, chuông, hoa vạn thọ) |
| Thể thao | `race_calendar` | Bảng đếm ngược F1; cần `tools/race_calendar.py` của upstream (không có trong repo này) |

## 3. Giới hạn cứng, phải thiết kế quanh chúng

- **Không đổi được phông chữ, icon, màu chữ hay hình dạng ô.** Chỉ đổi được ảnh nền, màu nền và các công tắc ở trên.
- **`accent_color` và `greeting` chỉ có tác dụng khi `festival` đang bật**, mà bộ `festival` hiện là skin kiểu Ấn Độ. Vì vậy chưa có đường chính thức để làm skin Tết Việt; xem mục 6.
- **Chữ và dock được thiết kế cho nền tối.** Giữ ảnh tối, ảnh sáng sẽ làm chữ trắng khó đọc.
- **Dải màu bị băng (banding).** Mặc định launcher giải mã ảnh RGB_565, nên gradient tối bị vạch. Cách giảm: thêm nhiễu dither nhẹ (script sinh ảnh đã làm), hoặc bật `wallpaper_true_color` cho TV có từ 2 GB RAM.
- **Dung lượng**: ảnh ≤ ~300 KB và 1920×1080; ảnh vượt 4K sau khi giảm mẫu sẽ không hiện.
- **Ảnh không đổi theo giờ.** Cách duy nhất theo giờ trong launcher là `sky_intensity`. Xoay ảnh chỉ theo chu kỳ, không theo giờ trong ngày.
- **Launcher không có Internet** và không tự tải ảnh; mọi thứ động phải do app máy tính đẩy xuống.

## 4. Vùng an toàn khi vẽ wallpaper

Trên màn 1920×1080, các vùng sau luôn có chữ hoặc dock đè lên:

```
+-----------------------------------------------+
| đồng hồ, lời chào      (0-35% x, 0-25% y)  [pill] |  <- góc trái trên tối nhất có thể
|                                               |
|        dải dock + tên app  (khoảng 40-75% y)  |  <- đừng đặt chi tiết sáng gắt ở đây
|                                               |
|   hàng ô app phía dưới     (75-100% y)        |  <- tối dần xuống đáy
+-----------------------------------------------+
```

Quy tắc đang dùng trong `scripts/make_theme_wallpapers.py::finish()`: tối dần 55-60% ở đáy, tối góc trái
trên ~35%, rồi dither. Chủ thể (mặt trăng, hành tinh, mặt trời) đặt ở nửa phải, phần giữa-trên.

## 5. Bộ theme đi kèm của app (đợt này)

| Theme | Ý tưởng | Đòn bẩy chính | Ảnh |
|---|---|---|---|
| `viet-scenes` | Sáu cảnh Việt Nam vẽ bằng code, đổi mỗi 30 phút, có chú thích tiếng Việt | xoay ảnh `sequential` + `wallpaper_captions` + kính mờ | Hạ Long, Sa Pa, Hội An, Mê Kông, Hồ Gươm, Đà Lạt |
| `cinema-noir` | Phòng chiếu tối, chùm sáng máy chiếu | `cinematic_home` + `top_menu` + `dock_title` + `app_glow` | 1 |
| `zen-ink` | Tối giản, mực tàu, chỉ 3 app trong dock | `fill_dock: false` + `top_menu` + tắt glow và overshoot | 1 |
| `kids-cosmos` | Vũ trụ vui cho trẻ: ô lớn, 3 cột, tên app luôn hiện, ẩn Play Store | `columns: 3` + `always_show_names` + `hidden_apps` + overshoot nảy | 1 |
| `synthwave` | Hoàng hôn neon, lưới phối cảnh | `glow_style: horizon` + `app_glow` + `advanced_effects` | 1 |
| `ops-console` | Bảng điều khiển cho người hay vọc: 6 cột, CPU/RAM, thư viện app | `columns: 6` + `show_stats` + `always_show_names` + `app_library` | 1 |
| `daylight-sky` | Không ảnh; bầu trời đổi theo giờ | `sky_intensity: 70` + kính mờ | 0 |

`kids-cosmos` ẩn Play Store khỏi Home nhưng **không phải cơ chế khoá**: app vẫn mở được bằng cách khác. Khoá thật
là việc của TV Guard.

Các `screenshot.jpg` của đợt này là **ảnh dựng** (đồng hồ, nút, ô app vẽ lại), có ghi "rendered preview" ở
góc. Chúng chưa phải ảnh chụp từ TV. Theo quy ước của upstream, hãy thay bằng ảnh chụp thật sau khi đẩy theme:
`adb shell screencap -p /sdcard/s.png`, rồi kéo về và đổi sang JPEG 1280×720.

## 6. Hướng phát triển tiếp (chưa làm)

1. **Kiểm chứng trên TV thật**: tổ hợp khoá nào chưa chắc tương tác tốt (ví dụ `cinematic_home` cùng `dock_row`, hay `top_menu` cùng `icon_only_buttons`) chưa được thử. Đẩy từng theme, chụp màn hình, ghi lại kết quả.
2. **Theme Tết/lễ hội Việt**: chưa có khoá chính thức; có hai hướng. Một, đề xuất upstream thêm `festival: tet`. Hai, làm bằng ảnh (wallpaper hoa đào, mai, câu đối) cộng `greeting_name`, nghĩa là không có skin riêng cho nút.
3. **Đổi theme theo lịch từ app máy tính**: vì launcher không đổi ảnh theo giờ, app có thể gọi `ThemeManager.patch_config` theo lịch. Một ý hay: theo khung giờ của TV Guard, ban ngày dùng `kids-cosmos`, tối dùng `cinema-noir`.
4. **Theme F1/thể thao**: dùng `race_calendar`; cần kéo `tools/race_calendar.py` từ upstream hoặc viết lại phần gọi API Jolpica trong app.
5. **Trình tạo theme trong UI** (mục UC-07 trong ROADMAP): form chọn mood, màu chủ đạo rồi sinh `config.json` và ảnh nền từ cùng bộ vẽ procedural.
6. **Mở rộng validator** (mục Phase 5 trong ROADMAP): kiểm độ tương phản vùng đồng hồ/dock trên ảnh, ước lượng bộ nhớ giải mã, `sky_intensity` và `wallpaper_dim` trong khoảng cho phép.
7. **Sinh thêm cảnh**: `scripts/make_theme_wallpapers.py` mỗi cảnh là một hàm; thêm hàm, đăng ký vào `SCENES`, chạy lại.

## 7. Quy trình thêm một theme

1. Tạo thư mục `data/cleanyourtv/themes/<id>/` (chữ thường, số, dấu gạch ngang).
2. Viết `config.json` chỉ với các khoá cần đổi.
3. Vẽ ảnh bằng script hoặc tự đưa vào (1920×1080, tối, ≤ 300 KB).
4. Chạy `python -m unittest tests.test_themes -v`.
5. Đẩy lên TV từ tab Theme của app, chụp màn hình thật, thay `screenshot.jpg`.
