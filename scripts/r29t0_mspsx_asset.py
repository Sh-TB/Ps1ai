#!/usr/bin/env python3
"""r29t0_mspsx_asset.py — rebuild the MSPSX local image after the 5th
filesystem rollback (candidates_r21/ + patched/mspsx_lic.* are gone).

Pipeline (zero boots):
  1. download the v0.1 release mspsx.bin (docs/homebrew_sources_r21.md N1:
     github.com/AcidGunner/MSPSX release v0.1, MODE2/2352 disc, 4 CDDA
     tracks, 117,891,648 B)
  2. assert sha256 == d35a189b...a4c5fa (the r22/r23-verified pristine
     value - byte-identical or abort)
  3. place at candidates_r21/mspsx_v0.1.bin
  4. run scripts/r22t1R_lic_patch.py (16 license sectors from the user's
     own retail MSX disc -> patched/mspsx_lic.bin/.cue, EXE untouched)

Game bytes / license sectors stay out of the repo.
"""
import hashlib
import os
import subprocess
import sys
import urllib.request

GAME_WS = "/home/z/my-project/emu/games_homebrew"
CAND = os.path.join(GAME_WS, "candidates_r21")
URL = "https://github.com/AcidGunner/MSPSX/releases/download/v0.1/mspsx.bin"
DST = os.path.join(CAND, "mspsx_v0.1.bin")
EXPECT_BYTES = 117891648
EXPECT_SHA = "d35a189b1ed14b7f07bf4cc31423ca43d8f34e35e8c3cb40c11bc6d3d0a4c5fa"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    os.makedirs(CAND, exist_ok=True)
    if os.path.exists(DST) and sha256(DST) == EXPECT_SHA:
        print("pristine already present:", DST)
    else:
        print("downloading", URL, flush=True)
        tmp = DST + ".part"
        urllib.request.urlretrieve(URL, tmp)
        os.replace(tmp, DST)
    got_b, got_s = os.path.getsize(DST), sha256(DST)
    print(f"mspsx_v0.1.bin: {got_b} bytes sha256={got_s}")
    assert got_b == EXPECT_BYTES, f"size mismatch {got_b}"
    assert got_s == EXPECT_SHA, f"sha mismatch {got_s}"
    print("pristine byte-identical to the r22/r23-verified image")

    r = subprocess.run([sys.executable,
                        "/home/z/my-project/ps1ai/scripts/r22t1R_lic_patch.py"],
                       capture_output=True, text=True)
    print(r.stdout[-800:])
    if r.returncode != 0:
        print(r.stderr[-800:])
        sys.exit(1)
    lic = os.path.join(GAME_WS, "patched", "mspsx_lic.bin")
    print("licensed image:", lic, os.path.getsize(lic), "bytes")
    print("OK")


if __name__ == "__main__":
    main()
