/* Google Analytics 4 for the SmartTV Manager landing page.
 * Nothing is loaded if the ID is malformed or the browser sends Do Not Track.
 */
(function () {
  "use strict";

  var GA_MEASUREMENT_ID = "G-QK5QWH32L2";

  if (!/^G-[A-Z0-9]{6,}$/.test(GA_MEASUREMENT_ID)) return;

  // Respect the browser's Do Not Track setting.
  if (navigator.doNotTrack === "1" || window.doNotTrack === "1") return;

  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  window.gtag = gtag;

  gtag("js", new Date());
  gtag("config", GA_MEASUREMENT_ID, { anonymize_ip: true });

  var s = document.createElement("script");
  s.async = true;
  s.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(GA_MEASUREMENT_ID);
  document.head.appendChild(s);

  // Custom events: downloads and outbound links.
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a) return;
    var href = a.href || "";
    if (/\/releases\/|\.(zip|dmg|exe)(\?|$)/i.test(href)) {
      gtag("event", "download_click", { link_url: href, link_text: (a.textContent || "").trim().slice(0, 80) });
    } else if (a.hostname && a.hostname !== location.hostname) {
      gtag("event", "outbound_click", { link_url: href });
    }
  });
})();
