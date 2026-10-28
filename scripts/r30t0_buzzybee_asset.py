#!/usr/bin/env python3
"""r30t0_buzzybee_asset.py — rebuild the BuzzyBee NTSC image + clone the
upstream source for mechanics ground truth (zero boots).

r23 facts re-verified on rebuild:
  - BuzzyBee.ps-exe = raw GitHub HEAD (NDR008/BuzzyBee, branch master -
    main 404s, r23 lesson), 299,008 B, sha256 9b0bfc08...c909a8ba
  - the game compiles PAL-only display code (SCREEN_HEIGHT=256,
    SetVideoMode(1)) -> renders BLACK on beetle+OpenBIOS; the disclosed
    2-instruction NTSC patch (r23) makes it render
  - output buzzybee_ntsc_lic.bin/.cue stays LOCAL (game bytes + license)
"""
import hashlib
import os
import subprocess
import sys
import urllib.request

GAME_WS = "/home/z/my-project/emu/games_homebrew"
CAND = os.path.join(GAME_WS, "candidates_r23")
EXE_URL = ("https://raw.githubusercontent.com/NDR008/BuzzyBee/master/"
           "BuzzyBee.ps-exe")
EXE_DST = os.path.join(CAND, "BuzzyBee.ps-exe")
EXE_SHA = "9b0bfc089c33d6116f2e67436254a4ced6e26275a7cac83f5f0dda95c909a8ba"
CLONE = "/tmp/BuzzyBee"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    os.makedirs(CAND, exist_ok=True)
    if not (os.path.exists(EXE_DST) and sha256(EXE_DST) == EXE_SHA):
        print("downloading", EXE_URL, flush=True)
        urllib.request.urlretrieve(EXE_URL, EXE_DST)
    got = sha256(EXE_DST)
    print(f"EXE: {os.path.getsize(EXE_DST)} bytes sha256={got}")
    assert got == EXE_SHA, f"EXE sha mismatch: {got}"

    if not os.path.isdir(CLONE):
        subprocess.run(["git", "clone", "--depth", "1", "-b", "master",
                        "https://github.com/NDR008/BuzzyBee", CLONE],
                       check=True, capture_output=True)
    names = sorted(os.listdir(CLONE))
    print("clone:", names[:12])

    r = subprocess.run([sys.executable, os.path.join(
        "/home/z/my-project/ps1ai/scripts", "r23t2_ntsc_patch_and_wrap.py")],
        capture_output=True, text=True)
    print(r.stdout[-600:])
    if r.returncode != 0:
        print(r.stderr[-600:])
        sys.exit(1)
    out = os.path.join(GAME_WS, "patched", "buzzybee_ntsc_lic.bin")
    print("built:", out, os.path.getsize(out), "bytes")
    print("OK")


if __name__ == "__main__":
    main()
