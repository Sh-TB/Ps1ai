#!/usr/bin/env python3
"""Make LOCAL license-patched homebrew test images (Issue #6 boot gate).

The OpenBIOS shell boot-loops a homebrew disc whose license sectors (0..15)
are empty: the shello CDChecker retries forever and the game EXE never loads
(OBSERVED 2026-10-22 for Tetrade/Nortis/PSXMC under beetle-psx + OpenBIOS).
Copying the 16 license sectors from the user's OWN retail disc into a LOCAL
copy of the homebrew image unblocks boot.

LEGALITY: patched images are derived from the user's locally owned retail
disc and stay OUT of VCS (this script writes to a local workspace only;
nothing here is committed). No copyrighted bytes enter the repository.
"""
import os
import shutil
import sys

SEC = 2352
GAME_WS = "/home/z/my-project/emu/games_homebrew"
MSX_BIN = os.environ.get(
    "M1_RETAIL_BIN",
    "/home/z/my-project/emu/game/Metal Slug X (USA).bin")
DST = os.path.join(GAME_WS, "patched")

PAIRS = {
    "TETRADE_PSX.bin": "TETRADE_lic.bin",
    "nortis_nortis.bin": "nortis_lic.bin",
    "PSXMC.bin": "PSXMC_lic.bin",
    "hello_pong.bin": "hello_pong_lic.bin",   # round 11 (task 17-c)
}


def main():
    if not os.path.exists(MSX_BIN):
        print(f"retail disc image not found: {MSX_BIN}\n"
              "set M1_RETAIL_BIN to your legally owned disc image")
        return 1
    with open(MSX_BIN, "rb") as f:
        license_data = f.read(16 * SEC)
    if b"Sony Computer Entertainment" not in license_data:
        print("license sector signature not found in the retail image "
              "(wrong file?)")
        return 1
    os.makedirs(DST, exist_ok=True)
    for src_name, dst_name in PAIRS.items():
        src = os.path.join(GAME_WS, src_name)
        if not os.path.exists(src):
            print(f"skip {src_name}: not fetched")
            continue
        dst = os.path.join(DST, dst_name)
        shutil.copyfile(src, dst)
        with open(dst, "r+b") as f:
            f.seek(0)
            f.write(license_data)
        cue = os.path.join(DST, dst_name.replace(".bin", ".cue"))
        with open(cue, "w") as f:
            f.write(f'FILE "{dst_name}" BINARY\n  TRACK 01 MODE2/2352\n'
                    '    INDEX 01 00:00:00\n')
        print(f"{src_name} -> {dst} (+cue)")
    print("patched local images ready (never commit them)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
