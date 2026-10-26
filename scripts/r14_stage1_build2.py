#!/usr/bin/env python3
"""r14_stage1_build2.py — stage-1 disc v2: built INSIDE a full copy of
hello_pong_lic.bin (1063 sectors, known-bootable structure — the v1
65-sector standalone image was rejected by the shell's disc checker).

Same content as v1: SYSTEM.CNF@23 (BOOT=LOADER.EXE), LOADER.EXE@24
(stage-1, 2 sectors), CS50X.EXE@26 (verbatim, 39 sectors). Everything
else byte-identical to hello_pong_lic.bin (PVD root@156 path@18/19,
tail sectors, 1063 total). Local license sectors stay from the user's
own retail disc copy.
"""
import hashlib
import json
import os
import struct

import capstone

EMU = "/home/z/my-project/emu/games_homebrew"
PATCHED = os.path.join(EMU, "patched")
HP_LIC = os.path.join(PATCHED, "hello_pong_lic.bin")
CS50X = os.path.join(EMU, "cs50x.exe")
OUT_DIR = "/home/z/my-project/ps1ai/scratch/round14_breakout"
RAW, DATA_OFF, SEC = 2352, 24, 2048

STAGE_TADDR = 0x80180000
GAME_PC = 0x80010000
TOTAL_BODY = 0x13000

# ---- stage-1 program (assembled by r14_stage1_build.py's asm()) ----
import sys
REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(REPO, "scripts"))
from r14_stage1_build import asm, ps_exe, dir_record  # noqa: E402


def wr_user(img, lba, data):
    """Sector-wise user-data write: each 2048-byte chunk lands at
    lba*2352+24, preserving every raw sector's sync/header/subheader/
    EDC-ECC (a contiguous write would slice through them — the r13
    container bug, root-caused by the sector diff today)."""
    off = 0
    while off < len(data):
        chunk = data[off:off + SEC]
        pos = (lba + off // SEC) * RAW + DATA_OFF
        img[pos:pos + len(chunk)] = chunk
        off += SEC


def rd_user(img, lba):
    off = lba * RAW + DATA_OFF
    return bytes(img[off:off + SEC])


def main():
    body, labels = asm()
    loader_exe = ps_exe(STAGE_TADDR, STAGE_TADDR, len(body), 0x801FFF00,
                        body)
    game_exe = open(CS50X, "rb").read()
    assert struct.unpack("<I", game_exe[0x18:0x1C])[0] == GAME_PC

    cnf = (b"BOOT=cdrom:\\LOADER.EXE;1\n"
           b"TCB=4\nEVENT=10\nSTACK=801FFF00\n")

    img = bytearray(open(HP_LIC, "rb").read())
    total = len(img) // RAW                     # 1063
    assert total == 1063

    # PVD: patch volume id only (vol_space_size 1063 stays correct)
    pvd = bytearray(rd_user(img, 16))
    assert pvd[1:6] == b"CD001"
    pvd[40:72] = b"CS50X_BOOT".ljust(32)
    wr_user(img, 16, pvd)

    # root dir @22 — same order style as hello_pong (exe, cnf) + loader
    root = bytearray()
    root += dir_record("\x00", 22, SEC, flags=2)
    root += dir_record("\x01", 22, SEC, flags=2)
    root += dir_record("LOADER.EXE;1", 24, len(loader_exe))
    root += dir_record("SYSTEM.CNF;1", 23, len(cnf))
    root += dir_record("CS50X.EXE;1", 26, len(game_exe))
    wr_user(img, 22, bytes(root) + bytes(SEC - len(root)))

    wr_user(img, 23, cnf)
    wr_user(img, 24, loader_exe)
    wr_user(img, 26, game_exe)

    dst = os.path.join(PATCHED, "breakout_r14b.bin")
    open(dst, "wb").write(bytes(img))
    with open(dst.replace(".bin", ".cue"), "w") as c:
        c.write('FILE "breakout_r14b.bin" BINARY\n'
                '  TRACK 01 MODE2/2352\n'
                '    INDEX 01 00:00:00\n')

    # verify: dirent parse + payload bytes on disc
    d = rd_user(img, 22)
    off, seen = 0, []
    while off < SEC and d[off]:
        ln = d[off]
        nm = d[off + 33:off + 33 + d[off + 32]]
        ext = struct.unpack("<I", d[off + 2:off + 6])[0]
        sz = struct.unpack("<I", d[off + 10:off + 14])[0]
        seen.append((nm.decode(), ext, sz))
        off += ln
    chk = rd_user(img, 26)
    assert chk[:8] == b"PS-X EXE", chk[:8]
    # full game file present? (sector-wise read-back)
    got = b"".join(rd_user(img, 26 + i) for i in
                   range((len(game_exe) + SEC - 1) // SEC))[:len(game_exe)]
    assert got == game_exe, "game exe bytes mismatch on disc"

    rep = {"image": dst, "bytes": len(img), "total_sectors": total,
           "sha256": hashlib.sha256(bytes(img)).hexdigest(),
           "root_dir": seen,
           "stage1_labels": {k: hex(v) for k, v in labels.items()}}
    json.dump(rep, open(os.path.join(OUT_DIR, "stage1_build_v2.json"), "w"),
              indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
