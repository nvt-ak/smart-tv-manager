# LG webOS trong SmartTV Manager

## Kết nối và điều khiển

Chọn **LG webOS** ở màn hình thêm thiết bị, nhập IP TV và chấp nhận yêu cầu
ghép cặp trên TV. Bật tùy chọn kết nối ứng dụng di động/LG Connect Apps nếu không
thấy yêu cầu. Manager ưu tiên kết nối TLS cổng 3001. TV cũ có thể được thêm bằng
`IP:3000` (WS không mã hóa, chỉ khi người dùng chọn rõ cổng này).

Khóa ghép cặp và dấu vân tay chứng chỉ nằm riêng trong thư mục dữ liệu ứng dụng
`webos/`, không đi vào theme, gói cài Home hoặc devices.json. Nếu chứng chỉ TV
thay đổi (ví dụ sau khi cập nhật firmware), xác minh đúng TV rồi bấm nút **Quên ghép
cặp** (biểu tượng ngắt liên kết) trên thẻ thiết bị LG, sau đó kết nối lại và chấp nhận
yêu cầu trên TV. Xóa TV khỏi danh sách cũng xóa khóa và dấu vân tay của nó.

Khi TV ngủ, kết nối đã lưu có thể chết. Manager tự kết nối lại một lần nếu lệnh chưa
được ghi ra socket, hoặc nếu đó là lệnh chỉ đọc (danh sách ứng dụng/input, âm lượng).
Lệnh có tác dụng phụ (mở ứng dụng, chuyển HDMI, nhập văn bản, tắt nguồn) không bao giờ
bị gửi lại tự động sau khi có thể đã tới TV. Phím điều hướng dùng lại một kênh phím
trong vài giây liên tiếp rồi mở kênh mới; khoảng này là ước lượng, chưa đo trên TV thật.

Remote, nhập văn bản, mở ứng dụng và chuyển HDMI dùng giao thức LG. Nút nguồn
chỉ **tắt** TV; bật lại bằng remote LG. Quét LAN chỉ tìm cổng đang mở, chưa chứng
minh đó là LG và chưa ghép cặp. Tên/model có thể chỉ là LG webOS nếu firmware từ
chối API metadata. Trạng thái cổng mở không có nghĩa TV đã cho phép điều khiển.

## Cài Home và áp dụng theme/widget

1. Cài Developer Mode từ kho LG Apps, đăng nhập tài khoản LG Developer, bật
   Developer Mode rồi bật Key Server. Theo dõi và gia hạn session trên TV.
2. Cài Node.js 20 trở lên và webOS CLI chính thức: `npm install -g @webos-tools/cli`.
3. Dùng `ares-setup-device` tạo profile, ví dụ `lgtv`, với đúng **địa chỉ IP** TV
   (không dùng hostname: Manager so sánh IP của profile với TV đang chọn và sẽ từ chối
   profile không khớp), cổng SSH 9922 và username `prisoner`.
4. Dùng `ares-novacom --device lgtv --getkey` và passphrase hiển thị trên TV.
   Kiểm tra kết nối profile theo hướng dẫn CLI của LG.
5. Trong Manager chọn TV LG, vào Home, nhập đúng tên profile CLI rồi chọn theme
   và widget như thường lệ. Manager đối chiếu IP profile với TV đang chọn trước
   khi cài đặt; profile sai TV sẽ bị từ chối.

Trên macOS, ứng dụng mở từ Finder không có PATH của shell. Manager tự thêm
`/opt/homebrew/bin`, `/usr/local/bin`, `~/.npm-global/bin`, `~/.volta/bin` và
`~/.local/bin` khi gọi CLI. Nếu CLI nằm nơi khác (ví dụ nvm), tạo symlink vào một trong
các thư mục đó hoặc mở Manager từ terminal. Gói Home nhận tối đa 12 ảnh nền, tổng 24 MB.

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
