#!/usr/bin/env python3
"""Phase 2f: find every reference to the score word 0x800EE318 in the
overlay code region + resident EXE text. Score adds happen at kills;
the surrounding code is the real damage/death logic (not the +0x8E
screen-position field the old labels chased).

Pattern: lui rt, 0x800F  (paired with) lw/su/addiu/sw imm 0xE318 (= -0x1CE8).
"""
import struct, json, os
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

REPO = "/home/z/my-project/ps1ai"
OUT = "/home/z/my-project/work/msx_recomp/evidence/issue5_truck"
OVERLAY = f"{REPO}/ps1play/re/ENEMY.BIN"
EXE = "/home/z/my-project/work/msx_recomp/SLUS_012.12.full"

OVERLAY_VA = 0x8009C0E8
CODE_OFF = 0xD180
CODE_END_OFF = 0x1C2C8
EXE_VA = 0x80010000
EXE_HDR = 0x800

funcs = json.load(open(f"{REPO}/data/games/SLUS-01212/ghidra/ghidra_overlay_functions.json"))
fn_bounds = sorted((int(f["entry"], 16), int(f["entry"], 16) + f["bytes"], f["name"])
                   for f in funcs)

def fn_of(va):
    for s, e, n in fn_bounds:
        if s <= va < e:
            return n
    return "EXE"

md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)

def scan_region(buf, va0):
    hits = []
    for off in range(0, len(buf) - 3, 4):
        w = struct.unpack_from("<I", buf, off)[0]
        imm = w & 0xFFFF
        opc = w >> 26
        # lui rt, 0x800F  (opcode 0x0F)
        if opc == 0x0F and imm == 0x800F:
            hits.append((va0 + off, "lui 800F"))
        # any op with sign-extended imm 0xE318 (=> -0x1CE8)
        elif imm == 0xE318:
            hits.append((va0 + off, f"op{opc:#x} -0x1CE8"))
    return hits

ov = open(OVERLAY, "rb").read()
exe = open(EXE, "rb").read()

ov_hits = scan_region(ov[CODE_OFF:CODE_END_OFF], OVERLAY_VA)
ex_hits = scan_region(exe[EXE_HDR:EXE_HDR + (OVERLAY_VA - EXE_VA)], EXE_VA)

def pair_up(hits):
    """Group: each lui 800F followed within 8 insns by an E318 op."""
    out = []
    for i, (va, k) in enumerate(hits):
        if k == "lui 800F":
            for va2, k2 in hits[i + 1:i + 12]:
                if va2 - va > 64:
                    break
                if "op" in k2:
                    out.append((va, va2))
                    break
    return out

print(f"overlay: {len(ov_hits)} raw refs -> {len(pair_up(ov_hits))} lui+E318 pairs")
for va1, va2 in pair_up(ov_hits):
    print(f"  lui@{va1:08X} use@{va2:08X}  func={fn_of(va1)}")

print(f"\nEXE text: {len(ex_hits)} raw refs -> {len(pair_up(ex_hits))} lui+E318 pairs")
for va1, va2 in pair_up(ex_hits):
    print(f"  lui@{va1:08X} use@{va2:08X}")

os.makedirs(OUT, exist_ok=True)
json.dump({"overlay_pairs": [[va1, va2] for va1, va2 in pair_up(ov_hits)],
           "exe_pairs": [[va1, va2] for va1, va2 in pair_up(ex_hits)]},
          open(f"{OUT}/score_refs.json", "w"), indent=1)
