#!/usr/bin/env python3
"""Fetch homebrew artifacts from data/homebrew/manifest.json into a
workspace dir, verifying SHA-256 before acceptance. Binaries stay OUT
of VCS by policy (data/homebrew holds only metadata + hashes)."""
import hashlib
import json
import os
import sys
import urllib.request

MANIFEST = os.path.join(os.path.dirname(__file__), "..", "data",
                        "homebrew", "manifest.json")
DEFAULT_DEST = "/home/z/my-project/emu/games_homebrew"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def write_tetrade_cue(dest):
    cue = os.path.join(dest, "tetrade.cue")
    with open(cue, "w") as f:
        f.write('FILE "TETRADE_PSX.bin" BINARY\n'
                '  TRACK 01 MODE2/2352\n'
                '    INDEX 01 00:00:00\n')
    return cue


def main():
    dest = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DEST
    os.makedirs(dest, exist_ok=True)
    manifest = json.load(open(MANIFEST))
    results = []
    for game in manifest["accepted"]:
        for art in game["artifacts"]:
            if not art.get("url"):
                continue
            out = os.path.join(dest, art["name"])
            if os.path.exists(out):
                got = sha256(out)
                ok = got == art["sha256"]
                results.append((art["name"], "cached",
                                "OK" if ok else f"HASH MISMATCH {got}"))
                if not ok:
                    return 2
                continue
            print(f"downloading {art['url']} -> {out}")
            urllib.request.urlretrieve(art["url"], out)
            got = sha256(out)
            if got != art["sha256"]:
                os.remove(out)
                results.append((art["name"], "downloaded",
                                f"HASH MISMATCH {got}"))
                return 2
            results.append((art["name"], "downloaded", "OK"))
    write_tetrade_cue(dest)
    for name, how, verdict in results:
        print(f"  {name}: {how} — {verdict}")
    print(f"artifacts ready in {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
