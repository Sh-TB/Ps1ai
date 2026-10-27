#!/usr/bin/env python3
"""r20t3_zenmai_wrap.py — minimal CD wrap for the zenmai Zork I PS-EXE (r20-t3).

Takes the raw PS-X EXE (zenmai-zork.psexe, pc0=0x80010000 t_size=698368) and
packs SYSTEM.CNF + EXE into a MODE2/2352 ISO9660 disc with the r17-proven
pure-Python writer (iso9660_min.py), then overwrites sectors 0..15 with the
16 license sectors from the user's own retail MSX image (same unblock as
Issue #6 boot gate). Patched image stays LOCAL (never committed).
"""
import hashlib
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import iso9660_min  # noqa: E402

SRC = "/home/z/my-project/emu/games_homebrew/zenmai-zork.psexe"
MSX = os.environ.get("M1_RETAIL_BIN",
                     "/home/z/my-project/emu/game/Metal Slug X (USA).bin")
OUT_DIR = "/home/z/my-project/emu/games_homebrew/patched"
EXE_NAME = "ZENMAI.EXE"

SEC = 2352


def main():
    exe = open(SRC, "rb").read()
    assert exe[:8] == b"PS-X EXE", "not a PS-X EXE"
    print(f"psexe: {len(exe)} bytes sha256={hashlib.sha256(exe).hexdigest()}")

    cnf = (f"BOOT = cdrom:\\{EXE_NAME};1\n"
           "TCB = 4\n"
           "EVENT = 10\n"
           "STACK = 801FFF00\n").encode()
    bin_data, cue = iso9660_min.build_image(
        [("SYSTEM.CNF", cnf), (EXE_NAME, exe)])

    lic = open(MSX, "rb").read(16 * SEC)
    assert b"Sony Computer Entertainment" in lic, "MSX license not found"
    bin_data = bytearray(bin_data)
    bin_data[:16 * SEC] = lic
    bin_data = bytes(bin_data)

    os.makedirs(OUT_DIR, exist_ok=True)
    bin_path = os.path.join(OUT_DIR, "zenmai_lic.bin")
    with open(bin_path, "wb") as f:
        f.write(bin_data)
    with open(os.path.join(OUT_DIR, "zenmai_lic.cue"), "w") as f:
        f.write(cue.replace('"image.bin"', '"zenmai_lic.bin"'))
    print(f"wrote {bin_path}: {len(bin_data)} bytes "
          f"sha256={hashlib.sha256(bin_data).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
