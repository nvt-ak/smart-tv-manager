#!/usr/bin/env python3
"""Desktop-side helper for the TV Guard control channel (G0 spike).

Prints `adb shell am broadcast ...` command lines; it never talks to a TV itself, so it is safe to
run anywhere. The real desktop integration will live in the main app later.

Examples:
  python guard_cli.py gen-secret > guard.secret
  python guard_cli.py hash-pin 1234
  python guard_cli.py cmd provision --secret-file guard.secret
  python guard_cli.py cmd set_pin --secret-file guard.secret --pin 1234
  python guard_cli.py cmd set_policy --secret-file guard.secret --policy-file policy.example.json
  python guard_cli.py cmd lock_now --secret-file guard.secret --text 30
  python guard_cli.py cmd lock_now --secret-file guard.secret --text 30 --run --serial 192.168.1.50:5555
"""
import argparse
import base64
import getpass
import hashlib
import hmac
import os
import re
import sys
import time

COMPONENT = "com.smarttvmanager.guard/.CommandReceiver"
ACTION = "com.smarttvmanager.guard.CMD"
PIN_ITERATIONS = 120_000  # Keep in sync with the 10k..1M range accepted by PinHasher.


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def b64u_nopad(data: bytes) -> str:
    return b64u(data).rstrip("=")


def hash_pin(pin: str, salt: bytes | None = None, iterations: int = PIN_ITERATIONS) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations, 32)
    return "$".join(["pbkdf2", str(iterations), b64u_nopad(salt), b64u_nopad(dk)])


def sign(secret: bytes, cmd: str, seq: int, payload: str) -> str:
    # Must match CommandAuth.message() on the TV: "<cmd>\n<seq>\n<payload>".
    msg = f"{cmd}\n{seq}\n{payload}".encode("utf-8")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def load_secret(path: str) -> bytes:
    with open(path, encoding="ascii") as f:
        raw = f.read().strip()
    return base64.urlsafe_b64decode(raw)


_SAFE = re.compile(r"^[A-Za-z0-9_./:@-]+$")


def _quote(arg: str) -> str:
    """Double quotes only: they mean the same in cmd.exe, PowerShell and POSIX shells."""
    return arg if _SAFE.match(arg) else f'"{arg}"'


def build_args(cmd: str, payload_text: str, secret: bytes, seq: int | None = None) -> list:
    payload = b64u(payload_text.encode("utf-8")) if payload_text else ""
    parts = [
        "shell", "am", "broadcast",
        "-n", COMPONENT, "-a", ACTION,
        "--es", "cmd", cmd,
    ]
    if cmd != "provision":
        seq = seq or int(time.time() * 1000)
        parts += ["--es", "seq", str(seq), "--es", "sig", sign(secret, cmd, seq, payload)]
    parts += ["--es", "payload", payload]
    return parts


def build_broadcast(cmd: str, payload_text: str, secret: bytes, seq: int | None = None) -> str:
    return " ".join(_quote(p) for p in ["adb"] + build_args(cmd, payload_text, secret, seq))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="action", required=True)

    sub.add_parser("gen-secret", help="print a new random shared secret (URL-safe base64)")

    hp = sub.add_parser("hash-pin", help="print the PBKDF2 hash to send with set_pin")
    hp.add_argument("pin", nargs="?", help="omit to be prompted without echo")

    cp = sub.add_parser("cmd", help="print the adb command for one control-channel command")
    cp.add_argument("name", choices=["provision", "ping", "set_policy", "set_pin", "lock_now", "unlock_now", "clear_policy"])
    cp.add_argument("--secret-file", required=True)
    cp.add_argument("--text", default="", help="payload text (minutes, PIN hash, ...)")
    cp.add_argument("--policy-file", help="JSON file used as payload for set_policy")
    cp.add_argument("--pin", help="set_pin only: 4-8 digit PIN (hashed here); omit to be prompted")
    cp.add_argument("--run", action="store_true", help="run adb instead of printing the command")
    cp.add_argument("--serial", help="with --run: device, for example 192.168.1.50:5555")
    cp.add_argument("--adb", default="adb", help="with --run: path to adb")

    args = ap.parse_args(argv)

    if args.action == "gen-secret":
        print(b64u(os.urandom(32)))
        return 0
    if args.action == "hash-pin":
        pin = args.pin or getpass.getpass("PIN: ")
        if not pin.isdigit() or not 4 <= len(pin) <= 8:
            print("PIN must be 4-8 digits (the TV overlay only enters digits)", file=sys.stderr)
            return 2
        print(hash_pin(pin))
        return 0

    secret = load_secret(args.secret_file)
    text = args.text
    if args.policy_file:
        with open(args.policy_file, encoding="utf-8") as f:
            text = f.read()
    payload_text = text
    if args.name == "set_pin":
        pin = args.pin or getpass.getpass("New PIN (4-8 digits): ")
        if not pin.isdigit() or not 4 <= len(pin) <= 8:
            print("PIN must be 4-8 digits (the TV overlay only enters digits)", file=sys.stderr)
            return 2
        payload_text = hash_pin(pin)  # hashed here; the TV never sees the PIN itself
    if args.name == "provision":
        secret_b64 = b64u(secret)  # the TV expects the secret itself, already base64
        argv_list = ["shell", "am", "broadcast", "-n", COMPONENT, "-a", ACTION,
                     "--es", "cmd", "provision", "--es", "payload", secret_b64]
    else:
        argv_list = build_args(args.name, payload_text, secret)

    if not args.run:
        print(" ".join(_quote(p) for p in ["adb"] + argv_list))
        return 0
    return run_adb(args.adb, args.serial, argv_list)


def run_adb(adb: str, serial: str | None, argv_list: list) -> int:
    """Run adb without a shell, so '$' and '=' in values are never interpreted."""
    import subprocess
    full = [adb] + (["-s", serial] if serial else []) + argv_list
    proc = subprocess.run(full, capture_output=True, text=True)
    out = (proc.stdout + proc.stderr).strip()
    print(out)
    if proc.returncode != 0 or 'data="error' in out:
        return 1
    return 0


def build_broadcast_raw_provision(secret_b64: str) -> str:
    # provision is unsigned and its payload is the base64 secret as-is (not wrapped again).
    return f'adb shell am broadcast -n {COMPONENT} -a {ACTION} --es cmd provision --es payload "{secret_b64}"'


if __name__ == "__main__":
    sys.exit(main())
