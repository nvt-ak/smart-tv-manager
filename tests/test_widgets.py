"""Home widget tests: lunar calendar, sources parsing, settings and the dashboard render.

Run from the repo root:  python -m unittest tests.test_widgets -v
No test touches the network.
"""
import os
import sys
import unittest
from datetime import date
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import home_widgets, vn_calendar, widget_cards, widget_render, widget_sources  # noqa: E402

FORECAST_SAMPLE = {
    "current": {"temperature_2m": 26.8, "relative_humidity_2m": 84, "weather_code": 1, "is_day": 0},
    "daily": {
        "time": ["2026-10-25", "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"],
        "weather_code": [51, 53, 51, 51, 53, 80],
        "temperature_2m_max": [32.4, 31.6, 30.8, 31.0, 30.3, 29.2],
        "temperature_2m_min": [25.7, 24.8, 24.1, 23.3, 23.6, 23.2],
        "precipitation_probability_max": [82, 96, 57, 33, 76, 71],
        "uv_index_max": [6.05, 5.8, 7.1, 7.1, 4.6, 6.8],
    },
}
VCB_SAMPLE = (
    '<!--For reference only. Only one request every 5 minutes!-->\n<ExrateList>\n'
    '  <DateTime>10/25/2026 10:11:32 PM</DateTime>\n'
    '  <Exrate CurrencyCode="EUR" CurrencyName="EURO" Buy="28,219.06" Transfer="28,504.10" Sell="29,707.60" />\n'
    '  <Exrate CurrencyCode="USD" CurrencyName="US DOLLAR" Buy="26,040.00" Transfer="26,070.00" Sell="26,400.00" />\n'
    '</ExrateList>'
)


class LunarCalendarTests(unittest.TestCase):
    def test_known_dates(self):
        self.assertEqual(vn_calendar.solar_to_lunar(date(2026, 10, 23)), (14, 9, 2026, False))
        self.assertEqual(vn_calendar.solar_to_lunar(date(2026, 10, 24)), (15, 9, 2026, False))
        self.assertEqual(vn_calendar.solar_to_lunar(date(2024, 2, 10)), (1, 1, 2024, False))
        # 2025 has a leap sixth month; 25 Jul 2025 is its first day.
        self.assertEqual(vn_calendar.solar_to_lunar(date(2025, 7, 25)), (1, 6, 2025, True))

    def test_round_trip(self):
        for d in (date(2026, 1, 1), date(2026, 10, 23), date(2027, 2, 6), date(2028, 7, 4), date(2030, 12, 31)):
            ld, lm, ly, leap = vn_calendar.solar_to_lunar(d)
            self.assertEqual(vn_calendar.lunar_to_solar(ld, lm, ly, leap), d)

    def test_tet(self):
        self.assertEqual(vn_calendar.lunar_to_solar(1, 1, 2026), date(2026, 2, 17))
        self.assertEqual(vn_calendar.lunar_to_solar(1, 1, 2027), date(2027, 2, 6))

    def test_year_names(self):
        self.assertEqual(vn_calendar.year_name(2026), "Bính Ngọ")
        self.assertEqual(vn_calendar.year_name(2027), "Đinh Mùi")

    def test_card_matches_the_reference_design(self):
        card = vn_calendar.lunar_card(date(2026, 10, 23))
        self.assertEqual((card["lunar_day"], card["lunar_month"]), (14, 9))
        names = [e["name"] for e in card["events"]]
        self.assertEqual(names, ["Rằm tháng 9", "Ngày Nhà giáo VN", "Tết Đinh Mùi"])
        self.assertEqual([e["relative"] for e in card["events"]], ["Ngày mai", "còn 28 ngày", "còn 106 ngày"])
        self.assertEqual(card["events"][2]["label"], "Thứ Bảy, 6/2/2027")

    def test_today_is_called_today(self):
        ev = vn_calendar.next_moon_event(date(2026, 10, 24))
        self.assertEqual(ev["relative"], "Hôm nay")


class SourceTests(unittest.TestCase):
    def test_weather_codes(self):
        self.assertEqual(widget_sources.describe_code(0), ("Trời quang", "clear"))
        self.assertEqual(widget_sources.describe_code(95)[1], "storm")
        self.assertEqual(widget_sources.describe_code("x")[1], "cloud")

    def test_labels(self):
        self.assertEqual(widget_sources.aqi_label(91), "TB")
        self.assertEqual(widget_sources.aqi_label(122), "Kém")
        self.assertEqual(widget_sources.uv_label(7), "Cao")
        self.assertEqual(widget_sources.uv_label(None), "-")

    def test_fetch_weather_parses_open_meteo(self):
        with mock.patch.object(widget_sources, "_get", side_effect=[FORECAST_SAMPLE, {"current": {"us_aqi": 122}}]):
            data, err = widget_sources.fetch_weather("Hà Nội")
        self.assertIsNone(err)
        self.assertEqual(data["text"], "Ít mây")
        self.assertFalse(data["is_day"])
        self.assertEqual(data["aqi"], 122)
        self.assertEqual(len(data["forecast"]), 5)
        self.assertEqual(data["forecast"][0]["label"], "T2")  # 2026-10-26 is a Monday

    def test_weather_survives_missing_air_quality(self):
        def fake(url):
            if "air-quality" in url:
                raise RuntimeError("down")
            return FORECAST_SAMPLE
        with mock.patch.object(widget_sources, "_get", side_effect=fake):
            data, err = widget_sources.fetch_weather("Không có thành phố này")
        self.assertIsNone(err)
        self.assertEqual(data["city"], widget_sources.DEFAULT_CITY)
        self.assertIsNone(data["aqi"])

    def test_usd_vnd_from_vcb(self):
        with mock.patch.object(widget_sources, "_get_text", return_value=VCB_SAMPLE):
            data, err = widget_sources.fetch_usd_vnd()
        self.assertIsNone(err)
        self.assertEqual((data["source"], data["rate"]), ("Vietcombank", 26400.0))

    def test_usd_vnd_falls_back(self):
        with mock.patch.object(widget_sources, "_get_text", side_effect=OSError("down")), \
                mock.patch.object(widget_sources, "_get", return_value={"rates": {"VND": 26100}}):
            data, err = widget_sources.fetch_usd_vnd()
        self.assertEqual((data["source"], data["rate"]), ("open.er-api.com", 26100.0))

    def test_usd_vnd_error_when_both_fail(self):
        with mock.patch.object(widget_sources, "_get_text", side_effect=OSError("a")), \
                mock.patch.object(widget_sources, "_get", side_effect=OSError("b")):
            data, err = widget_sources.fetch_usd_vnd()
        self.assertIsNone(data)
        self.assertIn("USD/VND", err)


class SettingsTests(unittest.TestCase):
    def test_defaults_and_validation(self):
        cfg = home_widgets.normalize_widgets({"weather_city": "Atlantis", "widget_layout": "huge"})
        self.assertEqual(cfg["weather_city"], widget_sources.DEFAULT_CITY)
        self.assertEqual(cfg["widget_layout"], "compact")
        self.assertTrue(cfg["show_weather"] and cfg["show_lunar"] and cfg["show_fx"])

    def test_known_city_and_tall_layout_are_kept(self):
        cfg = home_widgets.normalize_widgets({"weather_city": "Đà Nẵng", "widget_layout": "tall", "show_fx": False})
        self.assertEqual((cfg["weather_city"], cfg["widget_layout"], cfg["show_fx"]), ("Đà Nẵng", "tall", False))

    def test_wallpaper_mode_needs_any_card(self):
        base = {"enabled": True, "widget_wallpaper": True}
        off = {k: False for k in ("show_gold", "show_fuel", "show_weather", "show_lunar", "show_fx")}
        self.assertFalse(home_widgets.wallpaper_mode({**base, **off}))
        self.assertTrue(home_widgets.wallpaper_mode({**base, **off, "show_lunar": True}))

    def test_widgets_data_collects_errors_per_source(self):
        cfg = {"show_gold": False, "show_fuel": False, "show_weather": True, "show_lunar": True, "show_fx": True}
        with mock.patch.object(widget_sources, "fetch_weather", return_value=(None, "no weather")), \
                mock.patch.object(widget_sources, "fetch_usd_vnd", return_value=({"rate": 26000.0, "source": "x"}, None)):
            data = home_widgets.widgets_data(cfg)
        self.assertEqual(data["errors"], {"weather": "no weather"})
        self.assertIsNone(data["weather"])
        self.assertEqual(data["fx"]["rate"], 26000.0)
        self.assertEqual(data["lunar"]["events"][0]["name"].split()[0] in ("Mùng", "Rằm"), True)


def _sample_data(layout):
    return {
        "layout": layout,
        "weather": {"city": "Hà Nội", "temp": 29.2, "humidity": 73, "text": "Trời quang", "kind": "clear",
                    "is_day": True, "high": 33.4, "low": 25.1, "rain_chance": 12, "uv": 7.1, "aqi": 91,
                    "forecast": [{"label": "T7", "kind": "rain", "high": 33, "low": 26}] * 5},
        "lunar": vn_calendar.lunar_card(date(2026, 10, 23)),
        "gold": {"items": [{"code": "SJL1L10", "api_name": "SJC 9999", "buy": 139e6, "sell": 142e6},
                           {"code": "SJ9999", "api_name": "SJC Ring", "buy": 138e6, "sell": 141e6}]},
        "fuel": {"zone": 1, "items": [{"name": "Xăng E10 RON 95-III", "price": 24910},
                                      {"name": "Xăng E5 RON 92-II", "price": 25060},
                                      {"name": "Dầu DO 0,05S-II", "price": 29250}]},
        "fx": {"source": "Vietcombank", "rate": 26040},
        "generated": "09:12 23/10/2026",
    }


class RenderTests(unittest.TestCase):
    def test_both_layouts_draw_three_cards_on_a_full_hd_wallpaper(self):
        for layout in ("compact", "tall"):
            with self.subTest(layout=layout):
                img = widget_render.render_widgets(None, _sample_data(layout), bg_color="#140a0c")
                self.assertEqual(img.size, (1920, 1080))
                # The card area is no longer a flat background.
                region = widget_cards.TALL_REGION if layout == "tall" else widget_cards.COMPACT_REGION
                crop = img.crop(region).convert("L")
                lo, hi = crop.getextrema()
                self.assertGreater(hi - lo, 150)
                # The strip between the clock row and the cards is untouched.
                self.assertLess(max(img.crop((0, 0, 1920, 150)).convert("L").getextrema()), 40)

    def test_preview_scale_keeps_cards_inside_the_image(self):
        img = widget_render.render_widgets(None, _sample_data("tall"), size=(1280, 720), bg_color="#140a0c")
        self.assertEqual(img.size, (1280, 720))

    def test_missing_sources_just_skip_their_card(self):
        data = _sample_data("compact")
        data["weather"] = None
        drawn = widget_cards.draw_dashboard(widget_render.render_widgets(None, {}, bg_color="#000000"), data, 1.0)
        self.assertEqual(drawn, ["lunar", "prices"])

    def test_classic_layout_still_works_for_gold_and_fuel_only(self):
        data = _sample_data("compact")
        data.update({"weather": None, "lunar": None, "fx": None})
        data["gold"] = {"world": None, "updated": "", "items": [{"name": "SJC", "buy": 1e8, "sell": 1.1e8,
                                                                 "change_sell": 0}]}
        img = widget_render.render_widgets(None, data, bg_color="#000000")
        self.assertEqual(img.size, (1920, 1080))


if __name__ == "__main__":
    unittest.main()
