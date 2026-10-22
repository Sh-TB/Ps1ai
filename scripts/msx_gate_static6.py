#!/usr/bin/env python3
"""msx_gate_static6.py — find EXE-side references to:
  - 0x800B57FC and the other root-handler addresses (lui/addiu pairs)
  - root pointer slot 0x800C9A98 (lui 0x800c + addiu 0x9a98)
  - plus disassembly windows around each hit."""
import struct

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

EXE = "/home/z/my-project/ps1ai/ps1play/re/SLUS_012.12"
exe = open(EXE, "rb").read()
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.skipdata = True

def va2off(va):
    return 0x800 + (va - 0x80010000)

def find_lui_addiu(hi16, lo16_signed):
    """find lui $rX, hi16 followed within 2 instrs by addiu $rX,$rX,lo."""
    hits = []
    for off in range(0x800, 0x800 + 620544 - 8, 4):
        w1 = struct.unpack_from("<I", exe, off)[0]
        if (w1 >> 26) != 0x0F:               # lui
            continue
        rt = (w1 >> 16) & 31
        if ((w1 >> 0) & 0xFFFF) != hi16:
            continue
        for k in (1, 2):
            w2 = struct.unpack_from("<I", exe, off + 4 * k)[0]
            if (w2 >> 26) == 0x09 and ((w2 >> 16) & 31) == rt and \
                    ((w2 >> 21) & 31) == rt and \
                    struct.unpack("<h", struct.pack("<H", w2 & 0xFFFF))[0] \
                    == lo16_signed:
                hits.append(0x80010000 + (off - 0x800))
    return hits

for name, hi, lo in [("0x800B57FC", 0x800B, 0x57FC),
                     ("0x800C9A98", 0x800C, (0x9A98 - 0x10000) & 0xFFFF)]:
    hits = find_lui_addiu(hi, struct.unpack("<h", struct.pack("<H", lo))[0])
    print(f"refs to {name}: {len(hits)} -> {[hex(h) for h in hits[:24]]}")

# also: 32-bit absolute pointer occurrences in EXE data
for name, val in [("ptr 0x800B57FC", 0x800B57FC),
                  ("ptr 0x800C9A98", 0x800C9A98)]:
    pat = struct.pack("<I", val)
    hits, i = [], 0
    while True:
        i = exe.find(pat, i)
        if i < 0 or i > 0x800 + 620544:
            break
        hits.append(0x80010000 + (i - 0x800))
        i += 4
    print(f"{name} raw: {[hex(h) for h in hits[:16]]}")
