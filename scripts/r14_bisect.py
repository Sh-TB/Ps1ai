#!/usr/bin/env python3
"""r14_bisect.py — TEST B: hello_pong_lic.bin + MY root-record style
(tight records, 5-entry layout philosophy) but with the ORIGINAL two
files (GAMEPS1.EXE;1@24 30720 + SYSTEM.CNF;1@23 original bytes).
Boots hello_pong => my record style is checker-compatible;
cubes       => my record style is the breaker."""
import os
import struct
import sys

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(REPO, "scripts"))
from r14_stage1_build import dir_record                      # noqa: E402

EMU = "/home/z/my-project/emu/games_homebrew"
RAW, DATA_OFF, SEC = 2352, 24, 2048
SRC = os.path.join(EMU, "patched", "hello_pong_lic.bin")
DST = os.path.join(EMU, "patched", "bisectB.bin")


def rd_user(img, lba):
    return bytes(img[lba * RAW + DATA_OFF:lba * RAW + DATA_OFF + SEC])


def wr_user(img, lba, data):
    off = 0
    while off < len(data):
        chunk = data[off:off + SEC]
        pos = (lba + off // SEC) * RAW + DATA_OFF
        img[pos:pos + len(chunk)] = chunk
        off += SEC


img = bytearray(open(SRC, "rb").read())
cnf = rd_user(img, 23).split(b"\x00")[0]          # original CNF bytes
exe_size = 30720

root = bytearray()
root += dir_record("\x00", 22, SEC, flags=2)
root += dir_record("\x01", 22, SEC, flags=2)
root += dir_record("GAMEPS1.EXE;1", 24, exe_size)
root += dir_record("SYSTEM.CNF;1", 23, len(cnf))
wr_user(img, 22, bytes(root) + bytes(SEC - len(root)))

open(DST, "wb").write(bytes(img))
with open(DST.replace(".bin", ".cue"), "w") as c:
    c.write('FILE "bisectB.bin" BINARY\n'
            '  TRACK 01 MODE2/2352\n'
            '    INDEX 01 00:00:00\n')
print("TEST B image:", DST, "cnf:", cnf)
