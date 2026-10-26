#!/usr/bin/env python3
"""r14_padloader_build.py — padLOADER: pad32K-exact style. Take
hello_pong's ORIGINAL PS-EXE header bytes (from the pristine
hello_pong_lic.bin) and patch ONLY pc0/t_addr/t_size/s_addr to point
at the spin-flag stage-1; body = stage-1 + zero padding. Root dirent
size patched in-place (as pad32K did). This mirrors the ONE disc style
proven to get REAL kernel reads."""
import hashlib
import json
import os
import struct
import sys

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(REPO, "scripts"))
from r14_stage1v2_build import asm_v2  # noqa: E402

EMU = "/home/z/my-project/emu/games_homebrew"
PATCHED = os.path.join(EMU, "patched")
HP_LIC = os.path.join(PATCHED, "hello_pong_lic.bin")
CS50X = os.path.join(EMU, "cs50x.exe")
OUT_DIR = os.path.join(REPO, "scratch", "round14_breakout")
RAW, DATA_OFF, SEC = 2352, 24, 2048
STAGE_TADDR = 0x80180000


def wr_user(img, lba, data):
    off = 0
    while off < len(data):
        chunk = data[off:off + SEC]
        pos = (lba + off // SEC) * RAW + DATA_OFF
        img[pos:pos + len(chunk)] = chunk
        off += SEC


def rd_user(img, lba):
    return bytes(img[lba * RAW + DATA_OFF:
                     lba * RAW + DATA_OFF + SEC])


def main():
    body, labels = asm_v2()
    base = bytearray(open(HP_LIC, "rb").read())

    # hello_pong's original exe header at extent 24 (first 2048 user B)
    hdr = bytearray(rd_user(base, 24)[:0x800])
    assert hdr[:8] == b"PS-X EXE"
    # patch ONLY the load fields (pad32K-style in-place edits)
    struct.pack_into("<I", hdr, 0x10, STAGE_TADDR)       # pc0
    struct.pack_into("<I", hdr, 0x18, STAGE_TADDR)       # t_addr
    struct.pack_into("<I", hdr, 0x1C, len(body))         # t_size
    struct.pack_into("<I", hdr, 0x30, 0x801FFF00)        # s_addr
    struct.pack_into("<I", hdr, 0x34, 0)                 # s_size
    exe = bytes(hdr) + body                               # 2048+2048

    img = bytearray(base)
    wr_user(img, 24, exe)
    # dirent size in-place: 30720 -> 4096
    root = rd_user(img, 22)
    off, rec = 0, None
    while off < SEC and root[off]:
        ln = root[off]
        nm = root[off + 33:off + 33 + root[off + 32]]
        if nm.upper().startswith(b"GAMEPS1.EXE"):
            rec = off
            break
        off += ln
    assert rec is not None
    img[22 * RAW + DATA_OFF + rec + 10:22 * RAW + DATA_OFF + rec + 14] = \
        struct.pack("<I", len(exe))
    img[22 * RAW + DATA_OFF + rec + 14:22 * RAW + DATA_OFF + rec + 18] = \
        struct.pack(">I", len(exe))
    # park cs50x verbatim at 26+ (provenance; harness stages it anyway)
    wr_user(img, 26, open(CS50X, "rb").read())

    dst = os.path.join(PATCHED, "breakout_padloader.bin")
    open(dst, "wb").write(bytes(img))
    with open(dst.replace(".bin", ".cue"), "w") as c:
        c.write('FILE "breakout_padloader.bin" BINARY\n'
                '  TRACK 01 MODE2/2352\n'
                '    INDEX 01 00:00:00\n')
    rep = {"image": dst, "bytes": len(img),
           "sha256": hashlib.sha256(bytes(img)).hexdigest(),
           "style": "pad32K-exact: original header fields patched "
                    "in place; stage-1 spin-flag body",
           "stage1": {"t_addr": hex(STAGE_TADDR), "flag": "0x80180400",
                      "labels": {k: hex(v) for k, v in
                                 labels.items()}}}
    json.dump(rep, open(os.path.join(OUT_DIR, "padloader_build.json"),
                        "w"), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
