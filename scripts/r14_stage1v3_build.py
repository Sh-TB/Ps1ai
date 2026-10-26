#!/usr/bin/env python3
"""r14_stage1v3_build.py — s1v3: pad32K-STYLE in-place patching.

The round-14 discriminator: discs that KEEP hello_pong's original root
sector (only in-place field patches, pad32K-style) get REAL kernel
reads; discs with a REBUILT root sector hit the stale-metadata
anomaly. So: hello_pong_lic.bin + extent-24 payload replaced with the
spin-flag stage-1 + ONLY the dirent size field patched in-place
(30720 -> 4096). CNF untouched (BOOT=GAMEPS1.exe;1 — which is what
loads extent 24). Nothing else changes."""
import hashlib
import json
import os
import struct
import sys

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(REPO, "scripts"))
from r14_stage1v2_build import asm_v2, ps_exe  # noqa: E402

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
    loader = ps_exe(STAGE_TADDR, STAGE_TADDR, len(body), 0x801FFF00,
                    body)
    game = open(CS50X, "rb").read()

    img = bytearray(open(HP_LIC, "rb").read())

    # find the GAMEPS1.EXE;1 dirent in the ORIGINAL root @22 (in-place)
    root = rd_user(img, 22)
    off, rec = 0, None
    while off < SEC and root[off]:
        ln = root[off]
        nm = root[off + 33:off + 33 + root[off + 32]]
        if nm.upper().startswith(b"GAMEPS1.EXE"):
            rec = off
            break
        off += ln
    assert rec is not None, "GAMEPS1.EXE;1 record not found"
    # patch ONLY the size field (LE at rec+10, BE at rec+14)
    img[22 * RAW + DATA_OFF + rec + 10:22 * RAW + DATA_OFF + rec + 14] = \
        struct.pack("<I", len(loader))
    img[22 * RAW + DATA_OFF + rec + 14:22 * RAW + DATA_OFF + rec + 18] = \
        struct.pack(">I", len(loader))
    # verify
    root2 = rd_user(img, 22)
    assert struct.unpack("<I", root2[rec + 10:rec + 14])[0] == len(loader)

    # replace the exe payload at extent 24 (sector-wise)
    wr_user(img, 24, loader)
    assert rd_user(img, 24)[:8] == b"PS-X EXE"
    # park cs50x verbatim at extent 26+ for provenance (not read by boot)
    wr_user(img, 26, game)

    dst = os.path.join(PATCHED, "breakout_s1v3.bin")
    open(dst, "wb").write(bytes(img))
    with open(dst.replace(".bin", ".cue"), "w") as c:
        c.write('FILE "breakout_s1v3.bin" BINARY\n'
                '  TRACK 01 MODE2/2352\n'
                '    INDEX 01 00:00:00\n')
    rep = {"image": dst, "bytes": len(img),
           "sha256": hashlib.sha256(bytes(img)).hexdigest(),
           "method": "pad32K-style: original root kept, only dirent "
                     "size patched in place; stage-1 spin-flag at 24",
           "stage1": {"t_addr": hex(STAGE_TADDR),
                      "flag": "0x80180400",
                      "labels": {k: hex(v) for k, v in labels.items()}},
           "payload_sha256": hashlib.sha256(game).hexdigest()}
    json.dump(rep, open(os.path.join(OUT_DIR, "stage1v3_build.json"),
                        "w"), indent=1)
    print(json.dumps({k: v for k, v in rep.items()
                      if k != "stage1"}, indent=1))
    print("stage1 labels:", rep["stage1"]["labels"])


if __name__ == "__main__":
    main()
