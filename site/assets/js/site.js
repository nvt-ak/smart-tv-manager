/* SmartTV Manager landing page: language toggle, scene toggle, OS-aware download. */
(function () {
  "use strict";
  var REPO = "nvt-ak/smart-tv-manager";
  var LATEST = "https://github.com/" + REPO + "/releases/latest";

  var VI = {
    skip: "Bỏ qua, tới nội dung",
    nav_features: "Tính năng", nav_how: "Cách dùng", nav_download: "Tải về", nav_faq: "Hỏi đáp",
    h1: "Màn hình chính của TV, gọn như bạn muốn.",
    lede: "Gỡ quảng cáo và những app không dùng, dựng màn hình chính riêng, quản lý mọi thứ từ máy tính qua Wi‑Fi. Không phải gõ lệnh.",
    cta_how: "Xem cách dùng", free: "Miễn phí, mã nguồn mở",
    demo_h: "Xem app làm được gì trong 45 giây.",
    demo_p: "Lướt nhanh mọi tính năng, từ kết nối TV đến khoá trẻ em.",
    dl_generic: "Tải về", dl_win_btn: "Tải cho Windows", dl_mac_btn: "Tải cho macOS",
    seg_before: "Launcher gốc", seg_after: "Với SmartTV Manager",
    tv_cap: "Hình minh hoạ màn hình chính. Số liệu vàng và xăng là dữ liệu mẫu.",
    clean_h: "Tìm thứ làm TV chậm, rồi tắt nó đi.",
    clean_p: "Xem mọi app trên TV với tên dễ đọc. Tìm theo tên hoặc package, lọc theo app đang bật, đã tắt hoặc do bạn cài. App đã tắt bật lại được chỉ với một cú nhấp.",
    c1_t: "Vô hiệu hoá và bật lại", c1_d: "App hệ thống vẫn nằm trên TV, chỉ bị tắt. Bật lại lúc nào cũng được.",
    c2_t: "Gỡ app do bạn cài", c2_d: "App bạn tự cài có thể gỡ hẳn, sau khi xác nhận.",
    c3_t: "App được bảo vệ", c3_d: "App hệ thống cốt lõi và màn hình chính đang dùng bị khoá, để một cú nhấp nhầm không làm hỏng TV.",
    c4_t: "Cài file APK", c4_d: "Chọn file trên máy tính và cài lên TV, có nhật ký tiến trình trực tiếp.",
    win_title: "Ứng dụng · TV phòng khách", win_search: "Tìm theo tên hoặc package",
    tab_all: "Tất cả", tab_user: "Người dùng", tab_on: "Đang bật", tab_off: "Đã tắt",
    a_stop: "Dừng app", a_disable: "Vô hiệu hoá", a_open: "Mở", a_uninstall: "Gỡ cài đặt", a_enable: "Bật lại",
    home_h: "Màn hình chính của riêng bạn.",
    home_p: "SmartTV Manager cài và cấu hình CleanYourTV, một launcher mã nguồn mở, rồi áp dụng theme lên đó ngay từ máy tính.",
    home_cap: "Giá vàng và xăng dầu (Việt Nam) được vẽ vào hình nền. Dữ liệu mẫu.",
    h1_t: "Theme", h1_d: "Chọn theme rồi áp dụng. Cấu hình hiện tại được sao lưu trước, màn hình chính tự khởi động lại.",
    h2_t: "Widget nằm trong hình nền", h2_d: "Giá được vẽ thẳng vào ảnh nền nên TV không tốn tài nguyên để chạy chúng.",
    h3_t: "Phím remote vẫn hoạt động", h3_d: "Các phím Settings, TV, Netflix, YouTube, Prime Video và Media được gán sẵn cho remote TCL.",
    h4_t: "Launcher gốc, một cú nhấp để quay lại", h4_d: "Nó bị tắt khi theme đang dùng để phím Home mở màn hình của bạn. Muốn thì bật lại bản gốc bất cứ lúc nào.",
    guard_h: "Giờ đi ngủ cho TV, do chính TV thực thi.",
    guard_p: "Đặt khung giờ TV bị khoá và mã PIN của phụ huynh để mở. Một app nhỏ trên TV giữ lịch này, nên TV vẫn khoá đúng giờ ngay cả khi máy tính đã tắt.",
    g1_t: "Lịch theo ngày và giờ", g1_d: "Thêm một hoặc nhiều khung giờ khoá. Khung qua nửa đêm, như 22:00 đến 06:30, được tính từ ngày bắt đầu.",
    g2_t: "Nhập PIN bằng remote TV", g2_d: "Lên và Xuống đổi số, Phải thêm số, OK xác nhận. PIN chỉ được lưu trên TV dưới dạng băm, và nhập sai nhiều lần sẽ phải chờ lâu hơn.",
    g3_t: "Khoá ngay, mở khoá tạm", g3_d: "Che màn hình ngay lập tức, hoặc cho xem thêm 30 phút mà không đổi lịch.",
    g4_t: "Cài đặt luôn được bảo vệ", g4_d: "Cài đặt và cửa hàng ứng dụng luôn hỏi PIN nên không thể tắt khoá dễ dàng. Không chặn được đổi cổng HDMI, cast từ điện thoại hay reset nhà máy.",
    lg_h: "Nay đã có TV LG webOS (bản đầu).",
    lg_p: "Quét mạng một lần, SmartTV Manager tìm cả TV Android lẫn TV LG. Ghép cặp TV LG bằng cách chấp nhận thông báo trên màn hình, rồi điều khiển từ máy tính.",
    lg1_t: "Remote, nhập chữ và app", lg1_d: "Phím điều hướng, nhập chữ vào ô văn bản, mở app và chuyển cổng HDMI. Nút nguồn chỉ tắt TV; muốn bật lại hãy dùng remote LG.",
    lg2_t: "Theme Home", lg2_d: "Cùng bốn bố cục Home và công tắc widget, cài dưới dạng app snapshot. Cần bật Developer Mode trên TV, cài Node.js và webOS CLI của LG. Muốn làm mới dữ liệu thì Apply lại.",
    lg3_t: "Những gì LG chưa có", lg3_d: "Cài APK, Smart Clean và khoá trẻ em chỉ dành cho Android.",
    lg4_t: "Chưa thử trên TV LG thật", lg4_d: "Hãy xem đây là bản dùng thử. Rất hoan nghênh báo cáo từ TV thật, kèm model và phiên bản webOS, trên GitHub.",
    how_lg: "Dùng TV LG? Chọn LG webOS khi thêm thiết bị và chấp nhận thông báo ghép cặp trên TV. Nếu TV không hiện, bật LG Connect Apps trong cài đặt mạng của TV.",
    how_h: "Ba bước là dùng được.",
    s1_t: "Bật gỡ lỗi trên TV", s1_d: "Cài đặt, Tuỳ chọn thiết bị, Giới thiệu: nhấn OK bảy lần vào Bản dựng. Sau đó bật gỡ lỗi USB hoặc gỡ lỗi mạng trong Tuỳ chọn nhà phát triển.",
    s2_t: "Kết nối qua Wi‑Fi", s2_d: "Nhập địa chỉ IP của TV vào app và chấp nhận thông báo hiện trên TV.",
    s3_t: "Dọn dẹp và tuỳ biến", s3_d: "Tắt những app không cần. Khi app hỏi, cho nó cài CleanYourTV rồi chọn một theme.",
    dl_h: "Tải SmartTV Manager", dl_p: "Miễn phí, mã nguồn mở, cho Windows và macOS.",
    dl_win: "Windows 10 trở lên, 64-bit. Giải nén rồi chạy SmartTVManager.exe.",
    dl_mac: "Mở file .dmg và kéo app vào Applications.",
    dl_zip: "Tải .zip", dl_dmg: "Tải .dmg",
    dl_note: "App chưa được ký số. Windows SmartScreen có thể cảnh báo (chọn Thông tin thêm, rồi Vẫn chạy). Nếu Windows báo không nạp được Python.Runtime, chuột phải file .zip, mở Properties, tick Unblock rồi giải nén lại, còn macOS có thể yêu cầu cho phép trong Cài đặt hệ thống, Quyền riêng tư và bảo mật. Mã nguồn công khai nếu bạn muốn tự kiểm tra hoặc tự build.",
    dl_all: "Tất cả bản phát hành", dl_src: "Mã nguồn trên GitHub",
    faq_h: "Hỏi đáp",
    q1: "Có an toàn không?", a1: "App chạy trên máy tính của bạn và nói chuyện với TV qua mạng nội bộ bằng ADB. Nó không thu thập dữ liệu. App chỉ kết nối GitHub để tải launcher và các nguồn giá công khai cho widget, khi bạn dùng các tính năng đó. Vô hiệu hoá một app có thể hoàn tác. Gỡ cài đặt thì không, nên app luôn hỏi trước.",
    q2: "Dùng được với TV nào?", a2: "App được viết và thử trên TCL Google TV chạy Android 11. Quản lý app và cài APK dùng ADB thông thường nên các TV Android TV hoặc Google TV khác nhiều khả năng dùng được. Gán phím remote được chuẩn bị cho remote TCL. Launcher cần Android 8 trở lên. TV LG webOS được hỗ trợ ở bản đầu (remote, app, HDMI, theme Home), chưa kiểm chứng trên TV LG thật; cài APK và Smart Clean chỉ dành cho Android.",
    q7: "Có dùng được với TV LG không?", a7: "Có, ở dạng bản đầu cho LG webOS: remote, app, cổng HDMI và theme Home. Chưa được kiểm chứng trên TV LG thật, và cài APK, Smart Clean, khoá trẻ em không có trên LG.",
    q3: "Có cần root TV không?", a3: "Không. Bạn chỉ cần bật gỡ lỗi USB hoặc gỡ lỗi mạng.",
    q4: "Làm sao hoàn tác thay đổi?", a4: "Bật lại app đã tắt trong danh sách app, dùng “Đặt lại launcher gốc” để trả màn hình chính ban đầu, và khôi phục bản sao lưu cấu hình launcher trước đó.",
    q5: "Widget chỉ dành cho Việt Nam?", a5: "Widget vàng và xăng dầu có sẵn dùng nguồn dữ liệu Việt Nam, tính bằng VND. Quản lý app, cài APK và theme dùng được ở mọi nơi.",
    q6: "Đây có phải công cụ chính thức của TCL hay Google không?", a6: "Không. Đây là dự án độc lập, không liên kết với TCL, Google, LG hay tác giả CleanYourTV. CleanYourTV dùng giấy phép MIT.",
    foot: "SmartTV Manager là phần mềm tự do. Launcher mà app cài là CleanYourTV của Gathin23, giấy phép MIT. Tên sản phẩm thuộc về chủ sở hữu của chúng.",
    foot_issue: "Báo lỗi",
    foot_support: "Mời mình ly cà phê",
    sup_h: "Mời mình ly cà phê",
    sup_p: "SmartTV Manager miễn phí và mã nguồn mở. Nếu app giúp ích được cho bạn, các bác có thể mời mình ly cà phê để mình có thêm động lực phát triển tiếp dự án.",
    sup_note: "Hoàn toàn không bắt buộc. Một ngôi sao trên GitHub hay một báo cáo lỗi cũng giúp mình rất nhiều. Cảm ơn các bác!",
    sup_acct: "Chuyển khoản ngân hàng (Việt Nam)",
    sup_cap: "Quét bằng app ngân hàng bất kỳ có hỗ trợ VietQR."
  };

  var EN = {};
  document.querySelectorAll("[data-i18n]").forEach(function (el) {
    EN[el.getAttribute("data-i18n")] = el.textContent;
  });
  var EN_META = { title: document.title, desc: document.querySelector('meta[name="description"]').content };
  var VI_META = {
    title: "SmartTV Manager: dọn dẹp và tuỳ biến Android TV và TV LG webOS",
    desc: "Gỡ quảng cáo và app không dùng, dựng màn hình chính riêng và quản lý Android TV, Google TV hoặc TV LG webOS từ máy tính. Miễn phí, mã nguồn mở cho Windows và macOS."
  };

  var lang = "en";
  var release = null;

  function t(key) {
    return (lang === "vi" && VI[key]) || EN[key] || "";
  }

  function osName() {
    var ua = navigator.userAgent || "";
    if (/Windows/i.test(ua)) return "win";
    if (/Mac OS X|Macintosh/i.test(ua) && !/iPhone|iPad/i.test(ua)) return "mac";
    return "";
  }

  function applyLang(next) {
    lang = next;
    document.documentElement.lang = next;
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var k = el.getAttribute("data-i18n");
      var v = next === "vi" ? VI[k] : EN[k];
      if (v) el.textContent = v;
    });
    var demo = document.getElementById("demoVideo");
    if (demo && demo.paused) {
      // Swap the tour video to the chosen language; leave it alone while it is playing.
      demo.poster = "assets/video/poster-" + next + ".jpg";
      demo.src = "assets/video/smarttv-manager-intro-" + next + ".mp4";
    }
    var m = next === "vi" ? VI_META : EN_META;
    document.title = m.title;
    document.querySelector('meta[name="description"]').content = m.desc;
    document.querySelectorAll(".lang button").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-lang") === next));
    });
    try { localStorage.setItem("lang", next); } catch (e) { /* storage may be blocked */ }
    renderDownload();
  }

  function fmtSize(bytes) {
    return (bytes / 1048576).toFixed(0) + " MB";
  }

  function renderDownload() {
    var os = osName();
    var heroText = document.getElementById("heroDlText");
    var heroLink = document.getElementById("heroDl");
    var ver = document.getElementById("heroVer");
    if (os === "win") heroText.textContent = t("dl_win_btn") || "Download for Windows";
    else if (os === "mac") heroText.textContent = t("dl_mac_btn") || "Download for macOS";
    else heroText.textContent = t("dl_generic");
    if (lang === "en") {
      if (os === "win") heroText.textContent = "Download for Windows";
      if (os === "mac") heroText.textContent = "Download for macOS";
    }
    var mine = os === "win" ? "dlWin" : os === "mac" ? "dlMac" : "";
    ["dlWin", "dlMac"].forEach(function (id) {
      document.getElementById(id).classList.toggle("is-mine", id === mine);
    });
    if (!release) return;
    var assets = release.assets || [];
    var win = assets.filter(function (a) { return /\.zip$/i.test(a.name) && /win/i.test(a.name); })[0];
    var mac = assets.filter(function (a) { return /\.dmg$/i.test(a.name); })[0];
    var linkWin = document.getElementById("linkWin");
    var linkMac = document.getElementById("linkMac");
    if (win) { linkWin.href = win.browser_download_url; }
    if (mac) { linkMac.href = mac.browser_download_url; }
    var pick = os === "win" ? win : os === "mac" ? mac : null;
    heroLink.href = pick ? pick.browser_download_url : LATEST;
    var tag = release.tag_name || "";
    var size = pick ? "  " + fmtSize(pick.size) : "";
    ver.textContent = (lang === "vi" ? "Phiên bản " : "Version ") + tag.replace(/^v/, "") + size;
    if (win) document.getElementById("metaWin").textContent = t("dl_win") + "  " + fmtSize(win.size);
    if (mac) document.getElementById("metaMac").textContent = t("dl_mac") + "  " + fmtSize(mac.size);
  }

  function loadRelease() {
    if (!window.fetch) return;
    fetch("https://api.github.com/repos/" + REPO + "/releases/latest", { headers: { Accept: "application/vnd.github+json" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { if (j && j.tag_name) { release = j; renderDownload(); } })
      .catch(function () { /* keep the generic releases link */ });
  }

  /* Home screen comparison: reveal once on load, then follow the buttons. */
  function setupTv() {
    var tv = document.getElementById("tv");
    var scan = document.getElementById("scan");
    var btns = tv.querySelectorAll(".seg button");
    var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    var timer = null;

    function show(which, animate) {
      tv.classList.toggle("is-before", which === "before");
      btns.forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-scene") === which)); });
      if (!animate || reduce) return;
      var screen = tv.querySelector(".tv-screen");
      var w = screen.clientWidth;
      scan.style.transition = "none";
      scan.style.transform = "translateX(" + (which === "after" ? 0 : w) + "px)";
      tv.classList.add("is-moving");
      void scan.offsetWidth;
      scan.style.transition = "transform .9s cubic-bezier(.65,0,.2,1)";
      scan.style.transform = "translateX(" + (which === "after" ? w : 0) + "px)";
      clearTimeout(timer);
      timer = setTimeout(function () { tv.classList.remove("is-moving"); }, 950);
    }

    btns.forEach(function (b) {
      b.addEventListener("click", function () { show(b.getAttribute("data-scene"), true); });
    });
    if (reduce) { show("after", false); }
    else { setTimeout(function () { show("after", true); }, 900); }
  }

  document.querySelectorAll(".lang button").forEach(function (b) {
    b.addEventListener("click", function () { applyLang(b.getAttribute("data-lang")); });
  });

  var saved = null;
  try { saved = localStorage.getItem("lang"); } catch (e) { saved = null; }
  var initial = saved || ((navigator.language || "").toLowerCase().indexOf("vi") === 0 ? "vi" : "en");
  setupTv();
  applyLang(initial);
  loadRelease();
})();
