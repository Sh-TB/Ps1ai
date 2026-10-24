#!/usr/bin/env python3
"""Scan the ENEMY.BIN overlay for the damage-application fingerprint:
  lh  rt, OFF(base)  ...  subu/addiu-neg on rt  ...  sh rt, OFF(base)
within a 20-insn window (same base reg + same offset). Also flag
`ori/sb` of the 0x80 bit into +0x28 (the death-flag setter).
"""
import struct, json
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

REPO = "/home/z/my-project/ps1ai"
OVERLAY = f"{REPO}/ps1play/re/ENEMY.BIN"
OVERLAY_VA = 0x8009C0E8
CODE_OFF = 0xD180
CODE_END_OFF = 0x1C2C8

ov = open(OVERLAY, "rb").read()
code = ov[CODE_OFF:CODE_END_OFF]

md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.skipdata = True

insns = list(md.disasm(code, OVERLAY_VA))
print(f"{len(insns)} insns")

hits = []
for i, ins in enumerate(insns):
    if ins.mnemonic != "lh":
        continue
    # parse "lh $v0, 0x2c($a0)"
    try:
        rt, rest = ins.op_str.split(", ")
        off, base = rest.split("(")
        base = base.rstrip(")")
        off = int(off, 0)
    except (ValueError, IndexError):
        continue
    if off < 0 or off > 0x140:
        continue
    for j in range(i + 1, min(i + 21, len(insns))):
        ij = insns[j]
        if ij.mnemonic in ("subu", "addiu") and rt in ij.op_str.split(","):
            # negative immediate for addiu
            if ij.mnemonic == "addiu":
                try:
                    imm = int(ij.op_str.split(", ")[-1], 0)
                except ValueError:
                    continue
                if imm >= 0:
                    continue
            elif ij.mnemonic == "subu":
                pass
            for k in range(j + 1, min(j + 8, len(insns))):
                ik = insns[k]
                if ik.mnemonic == "sh" and ik.op_str.endswith(
                        f"{off}({base})"):
                    hits.append((i, j, k, off, base,
                                 insns[i].address, insns[j].address,
                                 insns[k].address,
                                 insns[j].mnemonic + " " + insns[j].op_str))
                    break
            break

print(f"\n=== subtract-store fingerprints: {len(hits)} ===")
funcs = json.load(open(f"{REPO}/data/games/SLUS-01212/ghidra/ghidra_overlay_functions.json"))
fb = sorted((int(f["entry"], 16), int(f["entry"], 16) + f["bytes"], f["name"])
            for f in funcs)

def fn_of(va):
    for s, e, n in fb:
        if s <= va < e:
            return n
    return "?"

for i, j, k, off, base, a_lh, a_sub, a_sh, subtxt in hits:
    print(f"+{off:#04x}({base})  lh@{a_lh:08X} {subtxt}  sh@{a_sh:08X}  "
          f"func={fn_of(a_lh)}")

# 0x80-bit writer into +0x28
print("\n=== sb/ori 0x80 into +0x28 ===")
for i, ins in enumerate(insns):
    if ins.mnemonic in ("ori", "addiu") and ins.op_str.endswith(", 0x80"):
        rt = ins.op_str.split(",")[0]
        for j in range(i + 1, min(i + 6, len(insns))):
            if insns[j].mnemonic == "sb" and \
                    insns[j].op_str.startswith(rt + ", 0x28("):
                print(f"{insns[i].address:08X} {ins.mnemonic} {ins.op_str} "
                      f"-> sb@{insns[j].address:08X} func={fn_of(insns[i].address)}")
                break
