#!/usr/bin/env python3
"""r20-t2: LOCAL license patch for the autogaz homebrew disc (same 16-sector
copy workflow as scripts/make_homebrew_lic.py; kept as a separate local
script so the shared manifest-driven tool is untouched).

Patched image is derived from the user's locally owned retail disc, stays in
the local workspace (emu/games_homebrew/patched) and is NEVER committed.
"""
import os
import shutil

SEC = 2352
GAME_WS = "/home/z/my-project/emu/games_homebrew"
MSX_BIN = os.environ.get(
    "M1_RETAIL_BIN", "/home/z/my-project/emu/game/Metal Slug X (USA).bin")
SRC = os.path.join(GAME_WS, "ws_autogaz", "autogaz-ps1", "autogaz.bin")
DST = os.path.join(GAME_WS, "patched", "autogaz_lic.bin")


def main():
    with open(MSX_BIN, "rb") as f:
        lic = f.read(16 * SEC)
    if b"Sony Computer Entertainment" not in lic:
        print("license signature not found in retail image")
        return 1
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    shutil.copyfile(SRC, DST)
    with open(DST, "r+b") as f:
        f.seek(0)
        f.write(lic)
    cue = DST.replace(".bin", ".cue")
    with open(cue, "w") as f:
        f.write('FILE "autogaz_lic.bin" BINARY\n  TRACK 01 MODE2/2352\n'
                '    INDEX 01 00:00:00\n')
    print(f"{SRC} -> {DST} (+cue)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
