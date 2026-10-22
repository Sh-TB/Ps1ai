#!/usr/bin/env python3
"""msx_gate_static7.py — disassemble the tiny predicate functions used by
the 8 FUN_800A87F8 callers, plus full bodies of two callers, and the
FUN_800A87F8 region including its true prologue (0x800A87E8)."""
import json

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

ENEMY = "/home/z/my-project/ps1ai/ps1play/re/ENEMY.BIN"
CODE_OFF, DEST = 0xD180, 0x8009C0E8
code = open(ENEMY, "rb").read()
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.skipdata = True

gh = json.load(open(
    "/home/z/my-project/ps1ai/data/games/SLUS-01212/ghidra/"
    "ghidra_overlay_functions.json"))
byentry = {int(f["entry"], 16): f for f in gh}

def dis(va, n, label):
    print(f"\n--- {label} {va:#x} ({n}B) ---")
    off = CODE_OFF + (va - DEST)
    for ins in md.disasm(code[off:off + n], va):
        print(f"  {ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}")

# predicates used by the 8 callers
for va, n in [(0x800A8924, 16), (0x800A9894, 16), (0x800A964C, 20),
              (0x800A9B1C, 24), (0x800A8ECC, 80), (0x800A8C58, 4)]:
    f = byentry.get(va)
    dis(va, n, f"predicate {f['name'] if f else '??'} "
       f"callers={f['callers'] if f else '?'}")

# FUN_800A87F8 with its preceding function (true prologue?)
dis(0x800A87B4, 0x60 + 0x30, "FUN_800A87B4 + FUN_800A87F8 region")
