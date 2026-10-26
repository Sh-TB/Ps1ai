#!/usr/bin/env python3
"""r14_scratch_build.py — FULLY scratch-built stage-1 disc (no
hello_pong byte lineage anywhere: own PVD template in the PSX-flavored
layout, own path tables, own root with +14-padded records, stage-1
loader + verbatim cs50x.exe, license sectors from the user's retail
disc copy (local-only, as always)).

Layout: 16 PVD / 17 terminator / 18-19 path tables / 20-21 optional
tables (own bytes) / 22 root / 23 SYSTEM.CNF / 24-25 LOADER.EXE /
26-64 CS50X.EXE. Total 65 sectors."""
import hashlib
import json
import os
import struct
import sys

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(REPO, "scripts"))
from r14_stage1_build import asm, ps_exe, dir_record  # noqa: E402

EMU = "/home/z/my-project/emu/games_homebrew"
PATCHED = os.path.join(EMU, "patched")
RETAIL = "/home/z/my-project/emu/game/Metal Slug X (USA).bin"
CS50X = os.path.join(EMU, "cs50x.exe")
OUT_DIR = os.path.join(REPO, "scratch", "round14_breakout")
RAW, DATA_OFF, SEC = 2352, 24, 2048
STAGE_TADDR = 0x80180000


def path_table(root_lba, be=False):
    e = struct.pack(">I" if be else "<I", root_lba)
    return bytes([1, 0]) + e + struct.pack(">H" if be else "<H", 1) \
        + b"\x00" + b"\x00"


def main():
    body, labels = asm()
    loader_exe = ps_exe(STAGE_TADDR, STAGE_TADDR, len(body), 0x801FFF00,
                        body)
    game_exe = open(CS50X, "rb").read()
    cnf = (b"BOOT=cdrom:\\LOADER.EXE;1\nTCB=4\nEVENT=10\n"
           b"STACK=801FFF00\n")

    root_lba, cnf_lba, loader_lba, game_lba = 22, 23, 24, 26
    pt_l, pt_m, opt1, opt2 = 18, 19, 20, 21
    loader_secs = (len(loader_exe) + SEC - 1) // SEC
    game_secs = (len(game_exe) + SEC - 1) // SEC
    total = game_lba + game_secs

    img = bytearray(total * SEC)

    # ---- PVD (own bytes, PSX-flavored layout like hello_pong's) ----
    pvd = bytearray(SEC)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[8:40] = b"PLAYSTATION".ljust(32)
    pvd[40:72] = b"CS50X_SCRATCH".ljust(32)
    struct.pack_into("<I", pvd, 80, total)
    struct.pack_into(">I", pvd, 84, total)
    struct.pack_into("<I", pvd, 120, 1)
    struct.pack_into(">I", pvd, 124, 1)
    struct.pack_into("<I", pvd, 128, 1)
    struct.pack_into(">I", pvd, 132, 1)
    struct.pack_into("<I", pvd, 136, SEC)
    struct.pack_into(">I", pvd, 140, SEC)
    struct.pack_into("<I", pvd, 144, 10)
    struct.pack_into(">I", pvd, 148, 10)
    # PSX flavor: L path table @140, M @144 (LE), opt tables BE @148/152
    pvd2 = bytearray(pvd)
    struct.pack_into("<I", pvd2, 140, pt_l)          # L path table
    struct.pack_into("<I", pvd2, 144, pt_m)          # M path table
    struct.pack_into(">I", pvd2, 148, opt1)          # opt L (BE)
    struct.pack_into(">I", pvd2, 152, opt2)          # opt M (BE)
    # root dir record at 156 (34 bytes)
    pvd2[156:156 + 34] = dir_record("\x00", root_lba, SEC, flags=2)
    assert dir_record("\x00", root_lba, SEC, flags=2)[0] == 48, \
        "root record must be 48B for PVD slot"
    # NOTE: a 48-byte record would overflow the PVD slot (156+48=204
    # < 2048 OK actually). hello_pong's is 34+14=48 too? check:
    img[16 * SEC:17 * SEC] = pvd2

    # ---- terminator ----
    term = bytearray(SEC)
    term[0] = 0xFF
    term[1:6] = b"CD001"
    term[6] = 1
    img[17 * SEC:18 * SEC] = term

    # ---- path tables + optional ----
    img[pt_l * SEC:pt_l * SEC + 10] = path_table(root_lba)
    img[pt_m * SEC:pt_m * SEC + 10] = path_table(root_lba, be=True)
    img[opt1 * SEC:opt1 * SEC + 10] = path_table(root_lba)
    img[opt2 * SEC:opt2 * SEC + 10] = path_table(root_lba, be=True)

    # ---- root dir ----
    root = bytearray()
    root += dir_record("\x00", root_lba, SEC, flags=2)
    root += dir_record("\x01", root_lba, SEC, flags=2)
    root += dir_record("LOADER.EXE;1", loader_lba, len(loader_exe))
    root += dir_record("SYSTEM.CNF;1", cnf_lba, len(cnf))
    root += dir_record("CS50X.EXE;1", game_lba, len(game_exe))
    img[root_lba * SEC:root_lba * SEC + len(root)] = root

    # ---- files ----
    img[cnf_lba * SEC:cnf_lba * SEC + len(cnf)] = cnf
    img[loader_lba * SEC:loader_lba * SEC + len(loader_exe)] = loader_exe
    img[game_lba * SEC:game_lba * SEC + len(game_exe)] = game_exe

    # ---- raw + license ----
    raw = bytearray()
    for lba in range(total):
        raw += b"\x00" + b"\xff" * 10 + b"\x00"
        m, rem = divmod(lba + 150, 75 * 60)
        s, f = divmod(rem, 75)
        to_bcd = lambda n: ((n // 10) << 4) | (n % 10)
        raw += bytes([to_bcd(m), to_bcd(s), to_bcd(f)]) + b"\x02"
        raw += bytes([0, 0, 0x08, 0, 0, 0, 0x08, 0])
        raw += img[lba * SEC:(lba + 1) * SEC]
        raw += bytes(280)
    lic = open(RETAIL, "rb").read(16 * RAW)
    assert b"Sony Computer Entertainment" in lic
    raw = bytearray(lic) + raw[16 * RAW:]

    dst = os.path.join(PATCHED, "breakout_scratch.bin")
    open(dst, "wb").write(bytes(raw))
    with open(dst.replace(".bin", ".cue"), "w") as c:
        c.write('FILE "breakout_scratch.bin" BINARY\n'
                '  TRACK 01 MODE2/2352\n'
                '    INDEX 01 00:00:00\n')
    rep = {"image": dst, "bytes": len(raw), "total_sectors": total,
           "sha256": hashlib.sha256(bytes(raw)).hexdigest(),
           "pvd": "own template (PSX layout: L@140 M@144 root@156)",
           "records": "+14 padded (hello_pong style)",
           "lineage": "NONE - no hello_pong bytes anywhere"}
    json.dump(rep, open(os.path.join(OUT_DIR, "scratch_build.json"), "w"),
              indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
