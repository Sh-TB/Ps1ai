#!/usr/bin/env python3
"""msx_gate_static3.py — classify the 8 in-overlay jal sites targeting
FUN_800A87F8: owner function + disassembly window + word context."""
import json
import struct

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

ENEMY = "/home/z/my-project/ps1ai/ps1play/re/ENEMY.BIN"
CODE_OFF, DEST, CODE_END_OFF = 0xD180, 0x8009C0E8, 0x1C2C8
SITES = [0x8009EE04, 0x8009F178, 0x8009F30C, 0x8009F49C, 0x8009FB04,
         0x8009FCCC, 0x8009FDD4, 0x800A0AB8]
TARGET = 0x800A87F8

code = open(ENEMY, "rb").read()
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.skipdata = True

gh = json.load(open(
    "/home/z/my-project/ps1ai/data/games/SLUS-01212/ghidra/"
    "ghidra_overlay_functions.json"))
byentry = sorted([(int(f["entry"], 16), f) for f in gh])

def owner(va):
    best = None
    for e, f in byentry:
        if e <= va < e + f.get("bytes", 4):
            if best is None or e > best[0]:
                best = (e, f)
    return best

def va2off(va):
    return CODE_OFF + (va - DEST)

# ---- verify each site is really jal 0x800a87f8 (little-endian word) ----
want = struct.pack("<I", (0x0C000000 | ((TARGET >> 2) & 0x3FFFFFF)))
for va in SITES:
    off = va2off(va)
    got = code[off:off + 4]
    print(f"verify {va:08x}: {'OK ' if got == want else 'BAD'} "
          f"({got.hex()})")

print("\n" + "=" * 72)
for va in SITES:
    o = owner(va)
    name = o[1]["name"] if o else "??"
    entry = o[0] if o else 0
    print(f"\n### site {va:08x}  owner {name} (entry {entry:08x}, "
          f"+{va - entry:#x}, {o[1]['bytes'] if o else '?'}B)")
    # disassemble from entry (bounded)
    eoff = va2off(entry)
    n = min(o[1]["bytes"] + 4, 320) if o else 256
    cnt = 0
    for ins in md.disasm(code[eoff:eoff + n], entry):
        mark = ""
        if ins.address == va:
            mark = "   <=== JAL TARGET SITE"
        if ins.mnemonic in ("jal", "j") and ins.op_str.startswith("0x"):
            mark += f"   [jal {ins.op_str}]"
        print(f"  {ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}{mark}")
        cnt += 1
        if cnt > 60:
            print("   ...")
            break
