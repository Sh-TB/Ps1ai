#!/usr/bin/env python3
"""r36t1_lostplumber_wrap.py — build a bootable local disc for LostPlumber
(NDR008/LostPlumber, MIT-in-header — flagged, local research use only).

Task r36t1 (R36 train A). Artifact from the r22 scout, re-verified here:
  LostPlumber.ps-exe 86,016 B, sha256 413d315a…bc863f8
  PS-X EXE: pc0 0x80010000, t_addr 0x80010000, t_size 83,968, sp 0x801FFF00.

Same engine as BuzzyBee (author's doukutsupsx-derived driver, engine/input.c:59
InitPAD) => BIOS pad class, expected to work on beetle+OpenBIOS.

Layout (iso9660_min, r23t2 family):
  LBA 0..15   license sectors from the user's own retail MSX disc (LOCAL ONLY)
  LBA 16..    SYSTEM.CNF (no-space BOOT= form, OpenBIOS-verified) + LOSTPLUMBER.EXE

Output: emu/games_homebrew/patched/lostplumber_lic.bin/.cue (LOCAL ONLY).
"""
import hashlib
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import iso9660_min  # noqa: E402

SRC = "/home/z/my-project/emu/games_homebrew/candidates_r22/LostPlumber.ps-exe"
MSX = os.environ.get(
    "M1_RETAIL_BIN", "/home/z/my-project/emu/game/Metal Slug X (USA).bin")
OUT_DIR = "/home/z/my-project/emu/games_homebrew/patched"
BIN_NAME = "lostplumber_lic.bin"
SEC = 2352
SRC_SHA = "413d315a077668b0baf35e13dbe0ef2d6ceeb9721f7a4e937f5b93c2fbc863f8"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    got = sha256(SRC)
    assert got == SRC_SHA, f"source sha mismatch: {got}"
    exe = open(SRC, "rb").read()
    assert exe[:8] == b"PS-X EXE", "not a PS-X EXE"
    sp = int.from_bytes(exe[0x30:0x34], "little")
    tsize = int.from_bytes(exe[0x1C:0x20], "little")
    assert tsize == 83968, f"t_size {tsize} != 83968"
    # no-space BOOT= form (r23-verified for OpenBIOS)
    cnf = (f"BOOT=cdrom:\\LOSTPLUMBER.EXE;1\r\n"
           f"TCB=4\r\n"
           f"EVENT=16\r\n"
           f"STACK={sp:08X}\r\n").encode()
    print(f"psexe: {len(exe)} B sha256={got} sp=0x{sp:08X} t_size={tsize}")

    bin_data, cue = iso9660_min.build_image(
        [("SYSTEM.CNF", cnf), ("LOSTPLUMBER.EXE", exe)])
    print(f"data track: {len(bin_data)//SEC} sectors")

    lic = open(MSX, "rb").read(16 * SEC)
    assert b"Sony Computer Entertainment" in lic, "MSX license not found"
    bin_data = bytearray(bin_data)
    bin_data[:16 * SEC] = lic
    bin_data = bytes(bin_data)

    os.makedirs(OUT_DIR, exist_ok=True)
    bin_path = os.path.join(OUT_DIR, BIN_NAME)
    with open(bin_path, "wb") as f:
        f.write(bin_data)
    with open(bin_path.replace(".bin", ".cue"), "w") as f:
        f.write(cue.replace("image.bin", BIN_NAME))
    print(f"wrote {bin_path}: {len(bin_data)} B ({len(bin_data)//SEC} sectors) "
          f"sha256={hashlib.sha256(bin_data).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
