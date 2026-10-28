#!/usr/bin/env python3
"""r22t1R_lic_patch.py — LOCAL license patch for the MSPSX homebrew disc.

Same 16-sector copy workflow as scripts/r20t2_autogaz_patch.py (proven in
r20/r21): copy the raw first 16 MODE2/2352 sectors (sync+header+subheader+
user data) of the user's locally owned retail disc onto the homebrew image.
The image stays in emu/games_homebrew/patched/ and is NEVER committed.

Boot 1 image = mspsx_lic.bin   (license-patched, EXE UNPATCHED)
Boot 2 image = mspsx_lic_rxen.bin (built by r22t1R_rxen_patch.py from this)

This script performs NO emulator boot (boot cap unaffected).
"""
import hashlib
import os
import shutil

SEC = 2352
GAME_WS = "/home/z/my-project/emu/games_homebrew"
MSX_BIN = os.environ.get(
    "M1_RETAIL_BIN", "/home/z/my-project/emu/game/Metal Slug X (USA).bin")
SRC = os.path.join(GAME_WS, "candidates_r21", "mspsx_v0.1.bin")
DST = os.path.join(GAME_WS, "patched", "mspsx_lic.bin")
SRC_SHA = "d35a189b1ed14b7f07bf4cc31423ca43d8f34e35e8c3cb40c11bc6d3d0a4c5fa"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    got = sha256(SRC)
    assert got == SRC_SHA, f"source sha mismatch: {got}"
    with open(MSX_BIN, "rb") as f:
        lic = f.read(16 * SEC)
    assert b"Sony Computer Entertainment" in lic, \
        "license signature not found in retail image"
    assert b"Sony Computer Entertainment" not in open(SRC, "rb").read(16 * SEC), \
        "homebrew already licensed? unexpected"
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    shutil.copyfile(SRC, DST)
    assert sha256(DST) == SRC_SHA
    with open(DST, "r+b") as f:
        f.seek(0)
        f.write(lic)
    # cue mirrors the release layout (1 data + 4 CDDA tracks, same indices)
    cue = DST.replace(".bin", ".cue")
    with open(cue, "w") as f:
        f.write('FILE "mspsx_lic.bin" BINARY\n'
                '  TRACK 01 MODE2/2352\n'
                '    INDEX 01 00:00:00\n'
                '  TRACK 02 AUDIO\n'
                '    INDEX 00 00:15:43\n'
                '    INDEX 01 00:17:43\n'
                '  TRACK 03 AUDIO\n'
                '    INDEX 00 01:57:19\n'
                '    INDEX 01 01:59:19\n'
                '  TRACK 04 AUDIO\n'
                '    INDEX 00 03:47:40\n'
                '    INDEX 01 03:49:40\n'
                '  TRACK 05 AUDIO\n'
                '    INDEX 00 06:33:41\n'
                '    INDEX 01 06:35:41\n')
    print(f"OK {SRC} -> {DST} (+cue); license 16 sectors written, "
          f"payload untouched")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
