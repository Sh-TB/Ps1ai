#!/usr/bin/env python3
"""analyze_patch_sites.py — offline structural analysis of the
published GameShark patch sites against OUR local SLUS_012.12 EXE.

The published 'infinite X' codes write 0x2400 into the UPPER half of
the 4-byte MIPS instruction at (addr-2). 0x2400 in the upper half makes
the instruction `addiu $zero, $zero, imm` — a NOP. So:

  * upper half 0xA0xx/0xA4xx/0xA8xx (sb/sh/sw)  -> store neutralized
    (the decremented counter is never written back)  [store-NOP patch]
  * upper half 0x10xx-0x17xx (beq/bne/blez/bgtz) -> branch skipped
  * anything else -> the patch would corrupt a different instruction

Read-only; decodes the bytes of the owner's local EXE copy.
"""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(_REPO, "ps1play", "re", "SUS01212_EXE_PLACEHOLDER")

SITES = [
    ("ammo",  0x8002DCE6, ["8002DCE6 2400"]),
    ("bombs", 0x800398BE, ["800398BE 2400"]),
    ("time",  0x8002962A, ["8002962A 2400"]),
    ("lives A", 0x800475AE, ["800475AE 2400"]),
    ("lives B", 0x80047522, ["80047522 2400"]),
    ("invuln 1", 0x8003273E, ["8003273E 2400"]),
    ("invuln 2", 0x80032764, ["80032764 00C8"]),
    ("invuln 3", 0x80032766, ["80032766 2405"]),
]

OPCODES = {
    0x23: "lw", 0x25: "lhu", 0x24: "lbu", 0x20: "lb",
    0x2B: "sw", 0x29: "sh", 0x28: "sb",
    0x04: "beq", 0x05: "bne", 0x06: "blez", 0x07: "bgtz",
    0x09: "addiu", 0x08: "addi", 0x0A: "slti", 0x0B: "sltiu",
    0x0C: "andi", 0x0D: "ori", 0x0F: "lui", 0x23 + 64: "lw",
}


def classify(upper):
    if 0xA000 <= upper <= 0xA3FF:
        return "STORE (sb/sh/sw) -> patch neutralizes the write-back"
    if 0x1000 <= upper <= 0x17FF:
        return "BRANCH -> patch skips it"
    op = upper >> 6 << 2
    name = OPCODES.get(upper >> 10 << 0, "?")  # rough
    return f"OTHER (upper={upper:04X})"


def main():
    exe_path = os.path.join(_REPO, "ps1play", "re", "SLUS_012.12")
    exe = open(exe_path, "rb").read()

    def word(vaddr):
        off = vaddr - 0x80010000 + 0x800     # PS-EXE: 0x800 header
        b = exe[off:off + 4]
        return b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)

    print(f"EXE: {exe_path} ({len(exe)} bytes)")
    for name, va, codes in SITES:
        instr = word(va - 2)
        upper = instr >> 16
        op = instr >> 26
        kind = {0x2B: "sw", 0x29: "sh", 0x28: "sb",
                0x04: "beq", 0x05: "bne", 0x06: "blez", 0x07: "bgtz",
                0x09: "addiu"}.get(op, f"op{op}")
        val = int(codes[0].split()[1], 16)
        new_upper = val
        effect = ("NOP (addiu $zero)") if val == 0x2400 else \
            f"upper-> {val:04X}"
        print(f"{name:10s} @{va:08X}: instr={instr:08X} ({kind:6s}) "
              f"upper={upper:04X} -> patched {effect} | {kind}")


if __name__ == "__main__":
    main()
