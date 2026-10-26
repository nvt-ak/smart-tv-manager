import os
import tempfile
import unittest

from PIL import Image

from core import preview_check


class PreviewCheckTest(unittest.TestCase):
    def _save(self, color, name="x.png"):
        d = tempfile.mkdtemp()
        path = os.path.join(d, name)
        Image.new("RGB", (64, 36), color).save(path)
        return path

    def test_black_frame_is_black(self):
        self.assertTrue(preview_check.is_black(self._save((0, 0, 0))))

    def test_dark_but_real_screen_is_kept(self):
        self.assertFalse(preview_check.is_black(self._save((12, 20, 40))))

    def test_bright_screen_is_kept(self):
        self.assertFalse(preview_check.is_black(self._save((200, 180, 90))))

    def test_missing_or_broken_file_counts_as_black(self):
        self.assertTrue(preview_check.is_black(os.path.join(tempfile.gettempdir(), "no-such-shot.png")))
        d = tempfile.mkdtemp()
        bad = os.path.join(d, "bad.png")
        with open(bad, "wb") as f:
            f.write(b"not an image")
        self.assertTrue(preview_check.is_black(bad))


if __name__ == "__main__":
    unittest.main()
