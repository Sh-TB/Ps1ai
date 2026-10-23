#!/usr/bin/env python3
"""scan_eb598_refs.py — disassemble the canonical MSX EXE text with
capstone and find every lui+addiu/ori (and lui+lw/sw) pair that
materializes KSEG addresses of interest:
  target  0x800EB598  (the scroll word that saturates at 992.0)
  anchor  0x800CA2E0  (slot0/player X — known-live, validates scanner)
  extras  0x800D4970 / 0x800D4974 (conjugate pair), 0x800D4A22,
          0x800D494E, 0x800D4958, 0x800D4938 (window flips)
Report each reference site with +/- 6 instructions of context so the
clamp comparison can be read directly.
"""
import json
import struct
import sys

import numpy as np
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_LITTLE_ENDIAN, CS_MODE_MIPS32

EXE = "/home/z/my-project/work/msx_recomp/SLUS_012.12.full"
TEXT_VA = 0x80010000
HDR = 0x800

TARGETS = {
    0x800EB598: "SCROLL(992-sat)",
    0x800CA2E0: "ANCHOR(playerX)",
    0x800D4970: "PAIR_A",
    0x800D4974: "PAIR_B",
    0x800D4A22: "FLIP_1to2",
    0x800D494E: "FLIP_3to0",
    0x800D4958: "FLIP_20to0",
    0x800D4938: "COUNTER",
}

data = open(EXE, "rb").read()
# GROUND TRUTH (validated 2026-10-24): the .full text is stored plain
# little-endian — sane prologue at the entry 0x80082A44 decodes with NO
# byteswap; the 0x80012814 region is a pointer table (0x8007C38C xN).
text = data[HDR:HDR + 620544]

md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
md.detail = False
md.skipdata = True          # embedded data words: emit .byte, keep going

# ---- pass 1: linear decode + lui register-value tracking -------------
# (lui rX, imm) sets rX = imm<<16 for tracking; a following
# addiu/ori rX, rX, simm materializes ea = (imm<<16)+simm. lw/sw with
# simm(rX) reads/writes ea+simm-rX-base. We record every ea in TARGETS.
insns = []          # (va, size, mnemonic, op_str, bytes)
for i in md.disasm(text, TEXT_VA):
    insns.append((i.address, i.size, i.mnemonic, i.op_str, i.bytes))
if len(insns) < 1000:
    print("DECODE FAILURE:", len(insns), "instructions — aborting")
    sys.exit(2)
print(f"decoded {len(insns)} instructions", flush=True)

reg_hi = {}          # reg -> (imm, va_of_lui)
hits = {t: [] for t in TARGETS}

def note(ea, idx, kind):
    if ea in hits:
        hits[ea].append((idx, kind))

for idx, (va, size, mn, op, by) in enumerate(insns):
    parts = op.split(",")
    if mn == "lui" and len(parts) == 2:
        try:
            rt = parts[0].strip()
            imm = int(parts[1].strip(), 0)
            reg_hi[rt] = (imm & 0xFFFF, va)
        except ValueError:
            pass
        continue
    if mn in ("addiu", "ori", "addu", "addi") and len(parts) == 3:
        rd, rs, s2 = (p.strip() for p in parts)
        if rs in reg_hi and rd == rs:
            (hi, hiva) = reg_hi[rs]
            try:
                simm = int(s2, 0)
            except ValueError:
                continue
            if mn == "ori":
                simm &= 0xFFFF
            ea = ((hi << 16) + simm) & 0xFFFFFFFF
            note(ea, idx, mn)
            if ea in hits:
                reg_hi.pop(rs, None)   # consumed; avoid double-count
        continue
    if mn in ("lw", "sw", "lb", "lbu", "sb", "lh", "lhu", "sh") and \
            len(parts) == 2:
        rt, mem = parts[0].strip(), parts[1].strip()
        if "(" in mem:
            off_s, rs = mem.rsplit("(", 1)
            rs = rs.rstrip(")")
            if rs in reg_hi:
                (hi, hiva) = reg_hi[rs]
                try:
                    simm = int(off_s.strip(), 0)
                except ValueError:
                    continue
                ea = ((hi << 16) + simm) & 0xFFFFFFFF
                note(ea, idx, mn)
    # branch/other instructions do not invalidate tracking here (best
    # effort linear scan; PSX -O2 emits lui close to its consumer)

out = {}
for t, name in TARGETS.items():
    lst = []
    for idx, kind in hits[t]:
        va0 = insns[max(0, idx - 6)][0]
        va1 = insns[min(len(insns) - 1, idx + 6)][0] + insns[idx + 6][1] \
            if idx + 6 < len(insns) else va0
        ctx = []
        for j in range(max(0, idx - 6), min(len(insns), idx + 7)):
            v, s, m2, o, _b = insns[j]
            mark = " <<" if j == idx else ""
            ctx.append(f"{v:08x}: {m2} {o}{mark}")
        lst.append({"idx": idx, "va": f"{insns[idx][0]:08x}",
                    "kind": kind, "ctx": ctx})
    out[f"{t:08x}"] = {"name": name, "n": len(lst), "sites": lst}

with open("/home/z/my-project/scripts/eb598_refs.json", "w") as f:
    json.dump(out, f, indent=1)
for t, r in out.items():
    print(f"{t} {r['name']}: {r['n']} sites")
