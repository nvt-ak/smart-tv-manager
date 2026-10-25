"""Build data/cleanyourtv/device-profiles.json from Gathin's examples/ (pinned commit).

Usage:
    python scripts/sync_device_profiles.py <path-to-cleanyourtv-checkout>

The checkout must be at the commit pinned in data/cleanyourtv/launcher-pin.json and
contain examples/<tv>/{tv.json,debloat.txt}. Upstream is MIT licensed
(https://github.com/Gathin23/cleanyourtv); the generated file keeps its notice.
"""
import json
import os
import re
import sys

PKG_RE = re.compile(r"^([A-Za-z][\w]*(?:\.[\w]+)+)\s*(?:#\s*(.*))?$")
WARN_RE = re.compile(r"\b(never|do not|don't|keep|breaks?|broken|must|requires?|only after)\b", re.I)
HEADER_ID_RE = re.compile(r"\b(?:device|product|board)\s+([A-Za-z0-9][\w.\-]{2,})", re.I)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def tokens_for(folder: str, tv: str, header: list) -> list:
    toks = {norm(folder)}
    paren = re.findall(r"\(([^)]*)\)", tv or "")
    for chunk in paren:
        for part in re.split(r"[,;/]", chunk):
            n = norm(part)
            if len(n) >= 4:
                toks.add(n)
    head = re.sub(r"\([^)]*\)", " ", tv or "")
    n = norm(head)
    if len(n) >= 4:
        toks.add(n)
    for ln in header:
        for m in HEADER_ID_RE.finditer(ln):
            n = norm(m.group(1))
            if len(n) >= 4:
                toks.add(n)
    return sorted(t for t in toks if t not in {"with", "google", "android", "smart", "smarttv"})


def parse_debloat(path: str) -> dict:
    header, pkgs, started = [], [], False
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                if not started:
                    header.append(line.lstrip("# ").rstrip())
                continue
            m = PKG_RE.match(line)
            if not m:
                continue
            started = True
            pkgs.append({"p": m.group(1), "n": (m.group(2) or "").strip()[:140]})
    skip_prefix = ("apply", "undo", "everything is disabled", "to keep phone casting")
    warnings = [h for h in header if WARN_RE.search(h) and not h.lower().startswith(skip_prefix)]
    return {"header": header, "pkgs": pkgs, "warnings": [w[:300] for w in warnings[:8]]}


def main(root: str) -> None:
    commit = json.load(open(os.path.join("data", "cleanyourtv", "launcher-pin.json")))["commit"]
    out = []
    base = os.path.join(root, "examples")
    for folder in sorted(os.listdir(base)):
        d = os.path.join(base, folder)
        tvj, deb = os.path.join(d, "tv.json"), os.path.join(d, "debloat.txt")
        if not (os.path.isfile(tvj) and os.path.isfile(deb)):
            continue
        meta = json.load(open(tvj, encoding="utf-8"))
        parsed = parse_debloat(deb)
        if not parsed["pkgs"]:
            continue
        out.append({
            "id": folder,
            "tv": meta.get("tv", folder),
            "os": meta.get("os", ""),
            "brand": meta.get("brand", ""),
            "notes": meta.get("notes", ""),
            "tokens": tokens_for(folder, meta.get("tv", ""), parsed["header"][:30]),
            "warnings": parsed["warnings"],
            "pkgs": parsed["pkgs"],
        })
    doc = {
        "_license": "Derived from Gathin23/cleanyourtv examples (MIT, Copyright (c) 2026 Gathin).",
        "upstream": "https://github.com/Gathin23/cleanyourtv",
        "commit": commit,
        "profiles": out,
    }
    dest = os.path.join("data", "cleanyourtv", "device-profiles.json")
    with open(dest, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(out)} profiles, {sum(len(p['pkgs']) for p in out)} packages -> {dest}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
