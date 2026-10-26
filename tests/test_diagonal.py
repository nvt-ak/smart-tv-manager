"""The glass sheen ramp must cover the whole card: no empty corners (they showed as dark triangles on the TV)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.widget_cards import _diagonal  # noqa: E402


class DiagonalTests(unittest.TestCase):
    def test_runs_corner_to_corner_without_gaps(self):
        g = _diagonal(400, 200)
        self.assertEqual(g.size, (400, 200))
        self.assertEqual(g.getpixel((0, 0)), 0)
        self.assertGreaterEqual(g.getpixel((399, 199)), 250)
        # Both other corners sit mid-way, and values only grow along either axis.
        self.assertTrue(100 <= g.getpixel((399, 0)) <= 160)
        self.assertTrue(100 <= g.getpixel((0, 199)) <= 160)
        row = [g.getpixel((x, 100)) for x in range(400)]
        self.assertEqual(row, sorted(row))


if __name__ == "__main__":
    unittest.main()
