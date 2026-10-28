#!/usr/bin/env python3
"""r23t2_v11_lic.py — LOCAL license patch for the AUTHOR's BuzzyBee v1.1
scene-mirror image (psx.arthus.net/homebrew/BuzzyBee_v1.1_image/buzzy.bin,
sha256 d5d7a629…f7acc32d — matches the r22 scout hash exactly).

The v1.1 image carries the game's own CDDA track (TRACK 02 AUDIO INDEX 01
00:15:69) — main.c:52 `int tracks[] = {2, 0}` + DsPlay(2, tracks, 0) wants
exactly that track; the r23t2 repo-EXE image had no audio track at all,
which is the r23t2 boot-1/2 black-screen prime suspect (DsPlay on a missing
track right after GPU init, before the first frame).

Its license sectors are CUSTOM ("32bit Jam / Scene is Alive" — r22 finding),
so the OpenBIOS CDChecker will loop on it; the same local 16-sector patch
from the user's own retail MSX disc unblocks it (route 2, never committed).

Output: emu/games_homebrew/patched/buzzybee_v11_lic.bin/.cue (LOCAL ONLY).
"""
import hashlib
import os
import shutil

SEC = 2352
SRC = "/home/z/my-project/emu/games_homebrew/candidates_r23/buzzy_v11_scene.bin"
SRC_SHA = "d5d7a62937c0e4a7cfe22b5eb73d2fbc869927b8744dfe1f7301f839f7acc32d"
MSX = "/home/z/my-project/emu/game/Metal Slug X (USA).bin"
OUT = "/home/z/my-project/emu/games_homebrew/patched/buzzybee_v11_lic.bin"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    got = sha256(SRC)
    assert got == SRC_SHA, f"source sha mismatch: {got}"
    lic = open(MSX, "rb").read(16 * SEC)
    assert b"Sony Computer Entertainment" in lic, "MSX license not found"
    assert b"Sony Computer Entertainment" not in open(SRC, "rb").read(
        16 * SEC), "scene image already Sony-licensed? unexpected"
    shutil.copyfile(SRC, OUT)
    assert sha256(OUT) == SRC_SHA
    with open(OUT, "r+b") as f:
        f.seek(0)
        f.write(lic)
    # cue: convert the author's PREGAP keyword (beetle-safe INDEX form)
    # TRACK 02 AUDIO PREGAP 00:02:00 INDEX 01 00:15:69
    #  -> INDEX 00 00:13:69, INDEX 01 00:15:69
    with open(OUT.replace(".bin", ".cue"), "w") as f:
        f.write('FILE "buzzybee_v11_lic.bin" BINARY\n'
                '  TRACK 01 MODE2/2352\n'
                '    INDEX 01 00:00:00\n'
                '  TRACK 02 AUDIO\n'
                '    INDEX 00 00:13:69\n'
                '    INDEX 01 00:15:69\n')
    print(f"OK {SRC} -> {OUT} (+cue); license 16 sectors written, "
          f"payload untouched (sha256 {got[:16]}...)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
