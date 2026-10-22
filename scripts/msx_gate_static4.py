#!/usr/bin/env python3
"""msx_gate_static4.py — disassembly windows around the 8 TRUE jal sites
targeting FUN_800A87F8, to classify calling context."""
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

ENEMY = "/home/z/my-project/ps1ai/ps1play/re/ENEMY.BIN"
CODE_OFF, DEST = 0xD180, 0x8009C0E8
SITES = [0x8009CDF4, 0x8009D038, 0x8009D1CC, 0x8009D35C, 0x8009D894,
         0x8009DA5C, 0x8009DB64, 0x8009E718]
code = open(ENEMY, "rb").read()
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.skipdata = True

def va2off(va):
    return CODE_OFF + (va - DEST)

def diswin(va, back=0x50, fwd=0x24):
    s = va - back
    out = []
    for ins in md.disasm(code[va2off(s):va2off(va) + fwd], s):
        mark = "  <<< JAL->800A87F8" if ins.address == va else ""
        if ins.mnemonic == "jal" and ins.address != va:
            mark += f"   [jal {ins.op_str}]"
        out.append(f"  {ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}{mark}")
    return out

for va in SITES:
    print(f"\n{'='*70}\n### window around {va:08x}")
    print("\n".join(diswin(va)))
