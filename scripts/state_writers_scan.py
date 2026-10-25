#!/usr/bin/env python3
"""state_writers_scan.py — find EVERY writer/reader of the section-
walker words (state 0x800EB5F4, flags 0x800EB5D0, progress 0x800EB5D4,
section-id 0x800EB5C8) across the WHOLE EXE text, tracking the
`lui $reg, 0x800f` + offset register-relative addressing that the
naive byte scan missed.

Answers: who saturates the progress word at 0xFFFF (the pin), and
which other code paths can advance/release the section.

Usage: python3 scripts/state_writers_scan.py
"""
import sys
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

REPO = "/home/z/my-project/ps1ai"
EXE = "/home/z/my-project/work/msx_recomp/SLUS_012.12.full"
EXE_VA = 0x80010000
EXE_HDR = 0x800
TEXT_LO, TEXT_HI = 0x80010000, 0x8009C000
WORDS = {0x800EB5F4: "STATE", 0x800EB5D0: "FLAGS",
         0x800EB5D4: "PROGRESS", 0x800EB5C8: "SECTID"}

exe = open(EXE, "rb").read()
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.skipdata = True


def va2off(va):
    return EXE_HDR + (va - EXE_VA)


insns = list(md.disasm(exe[va2off(TEXT_LO):va2off(TEXT_HI)], TEXT_LO))
print(f"disassembled {len(insns)} insns {TEXT_LO:#x}..{insns[-1].address:#x}")

# register base tracking: $reg -> (0x800f0000 base + displacement)
# we only care about lui $reg, 0x800f (base 0x800F0000)
base = {}
hits = []
cur_fn = None
for i, ins in enumerate(insns):
    if ins.mnemonic == "lui":
        parts = ins.op_str.replace(" ", "").split(",")
        if len(parts) == 2 and parts[1].lower() == "0x800f":
            base[parts[0]] = 0x800F0000
    elif ins.mnemonic in ("sw", "sh", "lw", "lhu", "lb", "lbu", "sb"):
        parts = [p.strip() for p in ins.op_str.split(",")]
        mem = parts[-1] if len(parts) >= 2 else ""
        if "(" in mem and mem.endswith(")"):
            disp, reg = mem.rsplit("(", 1)
            reg = reg[:-1]
            if reg in base:
                if not disp:
                    d = 0
                else:
                    try:
                        d = int(disp, 16)
                    except ValueError:
                        d = int(disp, 0)
                ea = (base[reg] + d) & 0xFFFFFFFF
                if ea in WORDS:
                    hits.append((ins.address, ins.mnemonic, ea,
                                 ins.op_str, cur_fn))
    elif ins.mnemonic == "jal":
        pass
    # crude function boundary: $ra store after sp adjust
    if ins.mnemonic == "addiu" and "$sp, $sp, -" in ins.op_str:
        cur_fn = ins.address

print(f"\n=== {len(hits)} accesses to walker words ===")
cur_ea = None
for addr, mn, ea, op, fn in hits:
    if ea != cur_ea:
        print(f"\n--- {WORDS[ea]} @ {ea:#08x} ---")
        cur_ea = ea
    print(f"  {addr:08x} {fn and f'(fn~{fn:08x})' or '':14s} "
          f"{mn:4s} {op}")
