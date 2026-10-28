import unittest
from unittest import mock

from core import home_widgets


class NativeCardsTest(unittest.TestCase):
    def test_launcher_patch_carries_the_city_and_its_position(self):
        cfg = {"enabled": True, "weather_city": "Hà Nội"}
        with mock.patch.object(home_widgets, "build_board_lines", side_effect=AssertionError("Unit test must not fetch live prices")):
            patch = home_widgets.launcher_config_patch(cfg, board_lines=[])
        self.assertEqual(patch["weather_city"], "Hà Nội")
        self.assertAlmostEqual(patch["weather_lat"], 21.0, delta=0.5)
        self.assertAlmostEqual(patch["weather_lon"], 105.8, delta=0.5)


if __name__ == "__main__":
    unittest.main()
