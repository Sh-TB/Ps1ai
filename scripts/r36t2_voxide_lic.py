#!/usr/bin/env python3
"""r36t2_voxide_lic.py — LOCAL license patch for VoXide v0.1.11 (route 2).

Task r36t2 (R36 train B). VoXide (EBonura/voxide, GPL-2.0-or-later; assets
CC0 per the ai-game-portal-ps1 audit) — the PSX-Minecraft sibling candidate.

Artifact (r22 scout, re-verified here): voxide.bin 2,511,936 B, sha256
7a37a390…c4e1e2ac; MODE2/2352, PVD volume VOXIDE, SYSTEM.CNF
BOOT=cdrom:\\PSX.EXE; license sectors 0..15 EMPTY -> route 2: copy the raw
first 16 sectors (sync+header+subheader+user data) of the user's own retail
MSX disc (r20/r22-proven workflow, r22t1R_lic_patch.py pattern).

Output: emu/games_homebrew/patched/voxide_lic.bin (+cue, filename-corrected).
LOCAL ONLY — never committed. NO emulator boot here (cap unaffected).
"""
import hashlib
import os
import shutil

SEC = 2352
GAME_WS = "/home/z/my-project/emu/games_homebrew"
MSX_BIN = os.environ.get(
    "M1_RETAIL_BIN", "/home/z/my-project/emu/game/Metal Slug X (USA).bin")
SRC = os.path.join(GAME_WS, "candidates_r22", "voxide_unpacked", "voxide.bin")
DST = os.path.join(GAME_WS, "patched", "voxide_lic.bin")
SRC_SHA = ("7a37a390e637bdcbcaa92c43d0d419a28ec1badeb0289772611b3d828ee749ca")


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
    # the zip-inner cue points at "voxide.bin" — write a corrected one
    cue = DST.replace(".bin", ".cue")
    with open(cue, "w") as f:
        f.write('FILE "voxide_lic.bin" BINARY\n'
                '  TRACK 01 MODE2/2352\n'
                '    INDEX 01 00:00:00\n')
    print(f"wrote {DST}: {os.path.getsize(DST)} B "
          f"sha256={hashlib.sha256(open(DST,'rb').read()).hexdigest()}")
    print(f"wrote {cue}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
