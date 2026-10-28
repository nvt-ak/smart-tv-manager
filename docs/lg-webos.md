# LG webOS trong SmartTV Manager

## Kết nối và điều khiển

Chọn **LG webOS** ở màn hình thêm thiết bị, nhập IP TV và chấp nhận yêu cầu
ghép cặp trên TV. Bật tùy chọn kết nối ứng dụng di động/LG Connect Apps nếu không
thấy yêu cầu. Manager ưu tiên kết nối TLS cổng 3001. TV cũ có thể được thêm bằng
`IP:3000` (WS không mã hóa, chỉ khi người dùng chọn rõ cổng này).

Khóa ghép cặp và dấu vân tay chứng chỉ nằm riêng trong thư mục dữ liệu ứng dụng
`webos/`, không đi vào theme, gói cài Home hoặc devices.json. Nếu chứng chỉ TV
thay đổi, xác minh đúng TV trước khi xóa khóa endpoint tương ứng để ghép cặp lại.

Remote, nhập văn bản, mở ứng dụng và chuyển HDMI dùng giao thức LG. Nút nguồn
chỉ **tắt** TV; bật lại bằng remote LG. Quét LAN chỉ tìm cổng đang mở, chưa chứng
minh đó là LG và chưa ghép cặp. Tên/model có thể chỉ là LG webOS nếu firmware từ
chối API metadata. Trạng thái cổng mở không có nghĩa TV đã cho phép điều khiển.

## Cài Home và áp dụng theme/widget

1. Cài Developer Mode từ kho LG Apps, đăng nhập tài khoản LG Developer, bật
   Developer Mode rồi bật Key Server. Theo dõi và gia hạn session trên TV.
2. Cài Node.js 20 trở lên và webOS CLI chính thức: `npm install -g @webos-tools/cli`.
3. Dùng `ares-setup-device` tạo profile, ví dụ `lgtv`, với đúng IP TV,
   cổng SSH 9922 và username `prisoner`.
4. Dùng `ares-novacom --device lgtv --getkey` và passphrase hiển thị trên TV.
   Kiểm tra kết nối profile theo hướng dẫn CLI của LG.
5. Trong Manager chọn TV LG, vào Home, nhập đúng tên profile CLI rồi chọn theme
   và widget như thường lệ. Manager đối chiếu IP profile với TV đang chọn trước
   khi cài đặt; profile sai TV sẽ bị từ chối.

Home app có ID `com.smtvmanager.home`. Bốn profile aurora/hanoi/hanoi2/hanoi3 lấy
cấu hình, wallpaper và công tắc widget từ catalog hiện có; hình học được port
từ `nvt-ak/smtv-home`. App Android được ánh xạ chỉ khi có app LG tương ứng;
SmartTube không bị tự đổi thành YouTube. App thiếu icon vẫn có tên và mở được.

Mỗi lần Apply tạo **snapshot** dữ liệu widget/app/HDMI, đóng gói `.ipk`, cài và
mở Home. Muốn cập nhật dữ liệu hoặc danh sách ứng dụng, Apply lại. Đồng hồ chạy
trên TV; dữ liệu giá/thời tiết/lịch trong snapshot không tự cập nhật. Nguồn lỗi
hiển thị dữ liệu chưa có, không tạo số liệu minh họa. Bản ghi theme trong Manager
là lịch sử triển khai cục bộ, không phải xác nhận trạng thái hiện thời trên TV.

Developer Mode có thể hết hạn và LG có thể gỡ app cài theo chế độ này. Bản đầu
chưa đồng bộ nóng, chưa tự gia hạn Developer Mode và chưa cung cấp Home watcher.
Home app không thay thế launcher hệ thống; có thể gán Quick Access bằng remote
theo khả năng model. Nút Home vật lý vẫn thuộc LG.

## Giới hạn và kiểm chứng

APK, Smart Clean/debloat, Android shell, screenshot ADB, thay launcher mặc định
và TV Guard không áp dụng cho LG. Không root TV. Chưa cam kết tương thích mọi
model/firmware, Magic Remote hoặc mọi ô nhập văn bản.

Test tự động dùng fake transport, fake CLI và UI mô phỏng. Trước phát hành cần
thử TV thật: pairing mới/từ chối/tái kết nối, standby, remote/input, cài Home,
session hết hạn, bốn bố cục và từng công tắc widget. macOS/Windows bundle cũng
cần build trên hệ điều hành tương ứng; CLI là công cụ cài riêng trên máy người dùng.

## Nguồn tham khảo

- [LG Developer Mode](https://webostv.developer.lge.com/develop/getting-started/developer-mode-app)
- [webOS CLI](https://webostv.developer.lge.com/develop/tools/cli-introduction)
- [webos-vibehack](https://github.com/OmkarK97/webos-vibehack), commit 31a518a:
  nghiên cứu SSAP, Luna và giới hạn Home; không sử dụng UI/catalog của repo này.
- [Kế hoạch và use case](plans/lg-webos.md)
