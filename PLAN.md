# TV Remote Hub - Detailed Plan & Task Tracking

> **Mục tiêu:** Theo dõi tiến độ triển khai theo ROADMAP.md. Mỗi task đều có trạng thái để dễ theo dõi.

**Cập nhật lần cuối:** 2026-10-24  
**Trạng thái dự án:** Phase 4 đang thực hiện (Theme Gallery)

---

## Tổng quan tiến độ

| Phase | Tên | Trạng thái | Tiến độ | Ghi chú |
|---|---|---|---|---|
| **Phase 0** | Foundation | ✅ Hoàn thành | 100% | Đã có: scan, add manual, connect/probe, lưu/xóa, UI cơ bản |
| **Phase 1** | Device Status & Remote | ✅ Hoàn thành | 100% | Remote + status + rename đã hoàn thành |
| **Phase 2** | App Inventory & Safety Layer | ✅ Hoàn thành | 100% | App list, safety guard, version info |
| **Phase 3** | APK Installer | ✅ Hoàn thành | 100% | Phân tích, so sánh version, cài đặt, cleanup, cảnh báo |
| **Phase 4** | Theme & Home Customization | 🔄 Đang làm | 44% | Phát hiện, backup, theme gallery từ cleanyourtv, apply qua content provider |
| **Phase 5** | Smart Cleanup & Debloat | ⬜ Chưa làm | 0% | **Nguy hiểm nhất** - cần cẩn thận |
| **Phase 6** | Advanced Operations | ⬜ Chưa làm | 0% | Tùy chọn |

**Legend:** `⬜ Chưa làm` | `🔄 Đang làm` | `✅ Hoàn thành` | `⏸️ Tạm dừng` | `❌ Bỏ qua` | `🧪 Đang test`

---

## PHASE 4: Theme, Wallpaper & Home Customization (com.gathin.tvhome)

### 4.1 Launcher Detection
| Task ID | Task | Trạng thái | Files | Mô tả chi tiết | Acceptance Criteria | Notes |
|---|---|---|---|---|---|---|
| P4-01 | Detect gathin.tvhome | ✅ Hoàn thành | `core/launcher_detector.py`, `main.py`, `ui/js/app.js` | Check installed + default home | OK | |
| P4-02 | Compatibility UI gate | ✅ Hoàn thành | `ui/index.html`, `ui/js/app.js` | Tab Home/Theme + gate | OK | |

### 4.2 Theme Management
| Task ID | Task | Trạng thái | Files | Mô tả chi tiết | Acceptance Criteria | Notes |
|---|---|---|---|---|---|---|
| P4-03 | Load themes from cleanyourtv | ✅ Hoàn thành | `core/cleanyourtv_themes.py`, `main.py` | Load từ data/cleanyourtv/themes | OK | Copy từ cleanyourtv repo |
| P4-04 | Theme gallery UI | ✅ Hoàn thành | `ui/js/app.js`, `ui/css/home.css`, `ui/index.html` | Grid + thumbnail + preview | OK | |
| P4-05 | Apply theme (CRITICAL) | ✅ Hoàn thành | `core/theme_manager.py`, `main.py`, `ui/js/app.js` | Backup trước, push qua content://com.gathin.tvhome.theme, force-stop | OK | **CRITICAL** - dùng cách của cleanyourtv |
| P4-06 | Reset theme | 🔄 Đang làm | `core/theme_manager.py` | Khôi phục | Cơ bản có force-stop | Cần thêm reset thực tế |
| P4-07 | Create custom theme | ⬜ Chưa làm | - | Form cơ bản | - | Tùy chọn |

### 4.3 Wallpaper
| Task ID | Task | Trạng thái | Files | Mô tả chi tiết | Acceptance Criteria | Notes |
|---|---|---|---|---|---|---|
| P4-08 | Wallpaper picker | ⬜ Chưa làm | - | Chọn ảnh | - | |
| P4-09 | Image validation | ⬜ Chưa làm | `core/image_processor.py` | Validate format/kích thước | - | |
| P4-10 | Image optimization | ⬜ Chưa làm | `core/image_processor.py` | Resize/compress | - | |
| P4-11 | Push wallpaper | ✅ Hoàn thành | `core/theme_manager.py`, `main.py` | Push wallpaper.jpg + wallpapers/ collection | OK | |

### 4.4 Layout Editor
| Task ID | Task | Trạng thái | Files | Mô tả chi tiết | Acceptance Criteria | Notes |
|---|---|---|---|---|---|---|
| P4-12 | Read current layout/config | ⬜ Chưa làm | `core/layout_manager.py` | Đọc config | - | |
| P4-13 | Layout editor UI | ⬜ Chưa làm | - | Grid editor | - | |
| P4-14 | App ordering/visibility | ⬜ Chưa làm | - | Drag & drop | - | |
| P4-15 | Save layout (CRITICAL) | ⬜ Chưa làm | `core/layout_manager.py` | Backup trước ghi | - | **CRITICAL** |
| P4-16 | Backup/restore launcher config | ✅ Hoàn thành | `core/theme_manager.py`, `main.py`, `ui/js/app.js` | Backup + force-stop | OK | **CRITICAL** |

**Checklist Phase 4:** [x] P4-01 [x] P4-02 [x] P4-03 [x] P4-04 [x] P4-05 [ ] P4-06 [ ] P4-07 [ ] P4-08 [ ] P4-09 [ ] P4-10 [x] P4-11 [ ] P4-12 [ ] P4-13 [ ] P4-14 [ ] P4-15 [x] P4-16

**Tiến độ Phase 4:** 7/16 (44%)

## Tiến độ tổng thể

```
Phase 0: ████████████████████ 100% (5/5)
Phase 1: ████████████████████ 100% (10/10)
Phase 2: ████████████████████ 100% (14/14)
Phase 3: ████████████████████ 100% (9/9)
Phase 4: ███████████░░░░░░░░   44% (7/16)
Phase 5: ░░░░░░░░░░░░░░░░░░░░   0% (0/18)
Phase 6: ░░░░░░░░░░░░░░░░░░░░   0% (0/7)

TỔNG:    ████████████████░░░   55% (44/79)
```
