#!/usr/bin/env python3
"""r23t2_buzzybee_wrap.py — build a bootable local disc for BuzzyBee
(NDR008/BuzzyBee, MIT) from the repo-tree PS-EXE (task r23t2).

Artifact: BuzzyBee.ps-exe, 299,008 B, sha256 9b0bfc08…c909a8ba (re-verified
today against the r22 scout hash). pc0 0x80010000, t_addr 0x80010000,
t_size 296,960, sp 0x801FFF00.

Layout (iso9660_min, same family as r21t1_bkbs_wrap.py):
  LBA 0..15   license sectors from the user's own retail MSX disc
              (LOCAL ONLY — OpenBIOS CDChecker unblock, never committed)
  LBA 16..    iso9660_min data track: SYSTEM.CNF + BUZZYBEE.EXE
No CDDA requirement: unlike BKBS PlaySyncedTrack(), BuzzyBee has no
hard-wait on CD audio (audio is VAG/SPU via audioTransferVagToSPU).

Output: emu/games_homebrew/patched/buzzybee_lic.bin/.cue (LOCAL ONLY).
"""
import hashlib
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import iso9660_min  # noqa: E402

SRC = "/home/z/my-project/emu/games_homebrew/candidates_r23/BuzzyBee.ps-exe"
MSX = os.environ.get(
    "M1_RETAIL_BIN", "/home/z/my-project/emu/game/Metal Slug X (USA).bin")
OUT_DIR = "/home/z/my-project/emu/games_homebrew/patched"
BIN_NAME = "buzzybee_lic.bin"
SEC = 2352
SRC_SHA = "9b0bfc089c33d6116f2e67436254a4ced6e26275a7cac83f5f0dda95c909a8ba"


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
    # sp from the EXE header (offset 0x30) — echoed into SYSTEM.CNF
    sp = int.from_bytes(exe[0x30:0x34], "little")
    cnf = (f"BOOT = cdrom:\\BUZZYBEE.EXE;1\r\n"
           f"TCB = 4\r\n"
           f"EVENT = 16\r\n"
           f"STACK = {sp:08X}\r\n").encode()
    print(f"psexe: {len(exe)} B sha256={got} sp=0x{sp:08X}")

    bin_data, cue = iso9660_min.build_image(
        [("SYSTEM.CNF", cnf), ("BUZZYBEE.EXE", exe)])
    m = len(bin_data) // SEC
    print(f"data track: {m} sectors")

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
        f.write(cue)
    print(f"wrote {bin_path}: {len(bin_data)} B ({len(bin_data)//SEC} sectors) "
          f"sha256={hashlib.sha256(bin_data).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
