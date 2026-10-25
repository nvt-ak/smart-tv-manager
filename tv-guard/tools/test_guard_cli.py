import base64
import hashlib
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import guard_cli  # noqa: E402


class GuardCliTest(unittest.TestCase):
    def test_signature_matches_documented_message_format(self):
        secret = bytes(range(32))
        sig = guard_cli.sign(secret, "lock_now", 1000, "NjA=")
        # Independent recomputation of "<cmd>\n<seq>\n<payload>".
        import hmac
        expected = hmac.new(secret, b"lock_now\n1000\nNjA=", hashlib.sha256).hexdigest()
        self.assertEqual(sig, expected)

    def test_pin_hash_format(self):
        h = guard_cli.hash_pin("1234", salt=b"\x07" * 16, iterations=10_000)
        parts = h.split("$")
        self.assertEqual(parts[0], "pbkdf2")
        self.assertEqual(parts[1], "10000")
        self.assertNotIn("=", h)  # unpadded, as PinHasher expects
        pad = lambda s: s + "=" * (-len(s) % 4)
        dk = hashlib.pbkdf2_hmac("sha256", b"1234", base64.urlsafe_b64decode(pad(parts[2])), 10_000, 32)
        self.assertEqual(base64.urlsafe_b64decode(pad(parts[3])), dk)

    def test_broadcast_contains_signature_and_encoded_payload(self):
        secret = b"s" * 32
        line = guard_cli.build_broadcast("lock_now", "30", secret, seq=5)
        self.assertIn('"MzA="', line)
        self.assertIn(guard_cli.sign(secret, "lock_now", 5, "MzA="), line)
        self.assertIn("-n com.smarttvmanager.guard/.CommandReceiver", line)

    def test_provision_is_unsigned(self):
        line = guard_cli.build_broadcast_raw_provision("abc=")
        self.assertNotIn("--es sig", line)
        self.assertIn("--es cmd provision", line)

    def test_cli_rejects_bad_pin(self):
        rc = guard_cli.main(["hash-pin", "12"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
