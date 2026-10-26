import unittest

from core import theme_widgets


class ThemeWidgetsTest(unittest.TestCase):
    def test_a_theme_without_a_dashboard_has_no_switches(self):
        self.assertEqual([], theme_widgets.available({"design_profile": "hanoi2"}))
        self.assertEqual([], theme_widgets.available(None))

    def test_each_profile_lists_its_own_widgets(self):
        keys = lambda p: [w["key"] for w in theme_widgets.available({"dashboard": True, "design_profile": p})]
        self.assertIn("show_gold", keys("hanoi2"))
        self.assertIn("show_lunar_header", keys("hanoi2"))
        self.assertNotIn("show_gold", keys("aurora"))
        self.assertIn("show_prices", keys("aurora"))
        self.assertEqual([], keys("crimson"))

    def test_default_is_on_unless_the_theme_turns_it_off(self):
        cfg = {"dashboard": True, "design_profile": "hanoi2", "show_fuel": False}
        state = {w["key"]: w["enabled"] for w in theme_widgets.resolve(cfg, {})}
        self.assertTrue(state["show_weather"])
        self.assertFalse(state["show_fuel"])

    def test_saved_choice_wins_and_is_written_for_every_widget(self):
        cfg = {"dashboard": True, "design_profile": "hanoi2", "show_fuel": False}
        out = theme_widgets.overrides(cfg, {"show_weather": False, "show_fuel": True})
        self.assertFalse(out["show_weather"])
        self.assertTrue(out["show_fuel"])
        self.assertEqual(7, len(out))

    def test_clean_drops_unknown_keys_and_non_booleans(self):
        cfg = {"dashboard": True, "design_profile": "aurora"}
        self.assertEqual({"show_weather": False},
                         theme_widgets.clean(cfg, {"show_weather": False, "show_gold": True, "show_quote": "no", "x": 1}))

    def test_every_key_is_known_to_the_theme_manager(self):
        from core.theme_manager import KNOWN_KEYS
        self.assertEqual([], [k for k in theme_widgets.KEYS if k not in KNOWN_KEYS])


if __name__ == "__main__":
    unittest.main()
