#!/usr/bin/env python3
"""r22t7 v3 — MSX (SLUS_012.12, MIPSel): (mission,area) byte table + readers.

Key finds so far:
  0x80010074 "MISSION SELECT"   0x80010090 "MISSION 1".."MISSION 6"
  0x80011160 "STAGE %d"         0x8001075C.. "\\ANG\\M1\\MISS01.BIN;1".."\\ANG\\M4\\MISS20.BIN;1"
  0x80010C86  byte table starts right after "\\ST01\\ST01.BIN;1"
"""
import struct
from collections import defaultdict

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32, CS_MODE_LITTLE_ENDIAN

EXE = "/home/z/my-project/emu/msx_usa/SLUS_012.12"
T = 0x80010000
H = 0x800
d = open(EXE, "rb").read()
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)

def off(va):
    return H + (va - T)

def xrefs(va, window=8):
    """All lui(+addiu/ori within `window` bytes) pairs materialising `va`."""
    hits = []
    for i in range(H, len(d) - 4 - window, 4):
        w1 = struct.unpack_from("<I", d, i)[0]
        if (w1 >> 26) != 0x0F:
            continue
        hi = w1 & 0xFFFF
        rt = (w1 >> 16) & 0x1F
        for k in range(1, window // 4 + 1):
            w2 = struct.unpack_from("<I", d, i + 4 * k)[0]
            if (w2 >> 26) in (0x09, 0x0D) and ((w2 >> 21) & 0x1F) == rt and ((w2 >> 16) & 0x1F) == rt:
                lo = w2 & 0xFFFF
                addr = (hi << 16) + (lo - 0x10000) if lo >= 0x8000 else (hi << 16) + lo
                if addr == va:
                    hits.append(T + i - H)
    return hits

def show_refs(name, va, limit=14):
    xs = xrefs(va)
    print(f"{name} {va:#x}: {len(xs)} xrefs -> {[hex(x) for x in xs[:limit]]}")
    return xs

# ---- 1. dump the byte table after \ST01\ST01.BIN;1
print("===== bytes 0x80010C86..0x80010D80 (suspected (mission,area) table) =====")
blob = d[off(0x80010C86):off(0x80010D80)]
for r in range(0, len(blob), 16):
    va = 0x80010C86 + r
    print(f"{va:#x}: " + " ".join(f"{b:02x}" for b in blob[r:r + 16]))

# find where the byte table ends and pointers begin
print("\n===== words 0x80010D80..0x80010EE8 =====")
for va in range(0x80010D80, 0x80010EE8, 4):
    w = struct.unpack_from(">I", d, off(va))[0]
    if 0x80010000 <= w <= 0x800A7800:
        print(f"{va:#x}: {w:#010x}  (in-image ptr)")

# ---- 2. xrefs to the table start and the STAGE% string and MISSION SELECT
print()
show_refs("(mission,area) table start", 0x80010C86)
show_refs("STAGE %d", 0x80011160)
show_refs("MISSION SELECT", 0x80010074)
show_refs("MISSION 1", 0x80010090)
show_refs("file \\ANG\\M1\\MISS01.BIN;1", 0x80010920)
show_refs("file \\ST01\\ST01.BIN;1", 0x80010C78)

# ---- 3. disassemble around every xref of "STAGE %d"
for label, va in (("STAGE %d", 0x80011160), ("MISSION SELECT", 0x80010074)):
    xs = xrefs(va)
    for x in xs[:3]:
        print(f"\n===== caller of {label}: {x - 0x40:#x}..{x + 0x40:#x} =====")
        for ins in md.disasm(d[off(x - 0x40):off(x + 0x40)], x - 0x40):
            mark = " <== ref" if ins.address == x else ""
            print(f"{ins.address:08x}: {ins.bytes.hex()}  {ins.mnemonic:<7} {ins.op_str}{mark}")
