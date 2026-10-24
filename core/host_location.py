"""Host machine location (native), for widget weather.

WebKit `navigator.geolocation` in pywebview is not wired to a permission delegate,
so macOS often returns PERMISSION_DENIED without a prompt. Use CoreLocation here.
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple

LatLonErr = Tuple[Optional[float], Optional[float], Optional[str]]

_location_lock = threading.Lock()
_MacLocationDelegate: Any = None


def _darwin_inject_location_usage_description() -> None:
    try:
        import AppKit
    except ImportError:
        return
    bundle = AppKit.NSBundle.mainBundle()
    info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
    if info is None:
        return
    key = "NSLocationWhenInUseUsageDescription"
    if not info.get(key):
        info[key] = (
            "SmartTV Manager dùng vị trí máy tính để lấy thời tiết cho widget Home trên TV."
        )


def open_location_privacy_settings() -> bool:
    if sys.platform != "darwin":
        return False
    try:
        subprocess.run(
            [
                "open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_LocationServices",
            ],
            check=False,
            timeout=5,
        )
        return True
    except Exception:
        return False


def _ensure_mac_location_delegate():
    global _MacLocationDelegate
    if _MacLocationDelegate is not None:
        return _MacLocationDelegate

    import objc
    import CoreLocation
    from Foundation import NSObject

    class MacLocationDelegate(NSObject):
        def initWithFetch_(self, fetch):
            self = objc.super(MacLocationDelegate, self).init()
            if self is None:
                return None
            self.fetch = fetch
            return self

        def _auth_status(self, manager):
            try:
                return int(manager.authorizationStatus())
            except Exception:
                return int(CoreLocation.CLLocationManager.authorizationStatus())

        def _begin_fix(self, manager):
            if hasattr(manager, "requestLocation"):
                manager.requestLocation()
            else:
                manager.startUpdatingLocation()

        def _on_auth_change(self, manager):
            status = self._auth_status(manager)
            if status in (
                CoreLocation.kCLAuthorizationStatusAuthorizedWhenInUse,
                CoreLocation.kCLAuthorizationStatusAuthorizedAlways,
            ):
                self._begin_fix(manager)
            elif status in (
                CoreLocation.kCLAuthorizationStatusDenied,
                CoreLocation.kCLAuthorizationStatusRestricted,
            ):
                self.fetch.fail("denied")

        def locationManager_didUpdateLocations_(self, manager, locations):
            if not locations:
                return
            loc = locations[-1]
            coord = loc.coordinate()
            manager.stopUpdatingLocation()
            self.fetch.finish(float(coord.latitude), float(coord.longitude))

        def locationManager_didFailWithError_(self, manager, error):
            manager.stopUpdatingLocation()
            self.fetch.fail(str(error.localizedDescription()))

        def locationManagerDidChangeAuthorization_(self, manager):
            self._on_auth_change(manager)

        def locationManager_didChangeAuthorization_(self, manager, status):
            self._on_auth_change(manager)

    _MacLocationDelegate = MacLocationDelegate
    return _MacLocationDelegate


class _LocationFetch:
    """One CoreLocation request; retains manager/delegate until finished."""

    __slots__ = ("done", "result", "_retain")

    def __init__(self) -> None:
        self.done = threading.Event()
        self.result: Dict[str, Any] = {}
        self._retain: list = []

    def finish(self, lat: float, lon: float) -> None:
        self.result["lat"] = lat
        self.result["lon"] = lon
        self._release()
        self.done.set()

    def fail(self, err: str) -> None:
        self.result["err"] = err
        self._release()
        self.done.set()

    def _release(self) -> None:
        self._retain.clear()

    def hold(self, *objects) -> None:
        self._retain.extend(objects)


def _schedule_on_main(fn) -> None:
    """Run fn on the AppKit main thread (permission dialogs require this)."""
    try:
        import dispatch
    except ImportError:
        from PyObjCTools import AppHelper

        AppHelper.callAfter(fn)
        return
    dispatch.dispatch_async(dispatch.dispatch_get_main_queue(), fn)


def _start_location_on_main(fetch: _LocationFetch) -> None:
    import CoreLocation

    if not CoreLocation.CLLocationManager.locationServicesEnabled():
        fetch.fail("disabled")
        return

    Delegate = _ensure_mac_location_delegate()
    delegate = Delegate.alloc().initWithFetch_(fetch)
    manager = CoreLocation.CLLocationManager.alloc().init()
    fetch.hold(delegate, manager)
    manager.setDelegate_(delegate)
    manager.setDesiredAccuracy_(CoreLocation.kCLLocationAccuracyThreeKilometers)

    status = delegate._auth_status(manager)
    if status == CoreLocation.kCLAuthorizationStatusNotDetermined:
        manager.requestWhenInUseAuthorization()
    elif status in (
        CoreLocation.kCLAuthorizationStatusAuthorizedWhenInUse,
        CoreLocation.kCLAuthorizationStatusAuthorizedAlways,
    ):
        delegate._begin_fix(manager)
    else:
        fetch.fail("denied")


def _get_darwin_location(timeout_s: float) -> LatLonErr:
    try:
        import CoreLocation  # noqa: F401
    except ImportError:
        return (
            None,
            None,
            "Thiếu pyobjc-framework-CoreLocation — chạy: pip install pyobjc-framework-CoreLocation",
        )

    _darwin_inject_location_usage_description()
    fetch = _LocationFetch()
    wait_s = max(15.0, float(timeout_s))

    with _location_lock:
        _schedule_on_main(lambda: _start_location_on_main(fetch))
        deadline = time.time() + wait_s
        while not fetch.done.is_set() and time.time() < deadline:
            time.sleep(0.05)
        if not fetch.done.is_set():
            fetch.fail("timeout")

    err = fetch.result.get("err")
    if err == "denied":
        return (
            None,
            None,
            "Quyền vị trí bị từ chối. Mở System Settings → Privacy & Security → "
            "Location Services và bật cho ứng dụng đang chạy SmartTV Manager "
            "(Python, Cursor hoặc SmartTV Manager.app).",
        )
    if err == "disabled":
        return None, None, "Location Services đang tắt trên máy — bật trong System Settings."
    if err == "timeout":
        return (
            None,
            None,
            "Hết thời gian chờ vị trí — nếu không thấy hộp thoại quyền, mở "
            "System Settings → Location Services, bật cho Python/Cursor/SmartTV Manager, "
            "rồi bấm «Lấy vị trí» lại (hoặc nhập tên thành phố).",
        )
    if err:
        return None, None, err

    lat, lon = fetch.result.get("lat"), fetch.result.get("lon")
    if lat is None or lon is None:
        return None, None, "Không lấy được tọa độ"
    return lat, lon, None


def get_host_location(timeout_s: float = 45.0) -> LatLonErr:
    if sys.platform == "darwin":
        return _get_darwin_location(timeout_s)
    return (
        None,
        None,
        "Định vị native chưa hỗ trợ nền tảng này — nhập tên thành phố thủ công.",
    )
