# TV Remote Hub

Desktop app: lists Android TVs on the LAN, connects over ADB with one click.
Scans every local /24 for open port 5555, or add a TV by IP manually.
Separate from `cleanyourtv`'s own ADB key — grant USB debugging again on
each TV the first time this app connects to it.

## Setup

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

## Run

```bash
venv/bin/python main.py
```

## Notes

- Saved devices: `~/.tv-remote-hub/devices.json`.
- ADB key: `~/.tv-remote-hub/adbkey`.
- Only scans for the port being open; it does not probe/authenticate until
  you click Connect, so a scan alone never triggers a TV's debugging prompt.
