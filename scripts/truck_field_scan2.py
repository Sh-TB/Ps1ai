#!/usr/bin/env python3
"""Phase 2d: refined scan for WRITERS of entity field +0x8E across:
  - the ENEMY.BIN overlay code region (0x8009C0E8 + 0xD180..0x1C2C8 in file)
  - the resident EXE text (SLUS_012.12.full: VA 0x80010000 + (off-0x800)),
    up to the overlay load address 0x8009C0E8
Patterns: direct sh/sb/sw at 0x8E (and sw 0x8C / sb 0x8E / sb 0x8F windows),
plus addiu ... ,0x8E base computations followed by 0-offset stores nearby.
"""
import json, struct, os
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
    return "EXE" if va < OVERLAY_VA else "?"

def scan(buf, va_base, label):
    hits = []
    for off in range(0, len(buf) - 3, 4):
        w = struct.unpack_from("<I", buf, off)[0]
        opc = w >> 26
        imm = w & 0xFFFF
        simm = imm - 0x10000 if imm >= 0x8000 else imm
        va = va_base + off
        rs = (w >> 21) & 0x1F
        rt = (w >> 16) & 0x1F
        # direct stores to +0x8E and word window 0x8C
        if opc == 0x29 and imm == 0x8E:            # sh ,0x8e(
            hits.append((va, "sh +0x8E", rt, rs, simm))
        elif opc == 0x28 and imm in (0x8E, 0x8F):  # sb bytes of the half
            hits.append((va, f"sb {imm:#x}", rt, rs, simm))
        elif opc == 0x2B and imm == 0x8C:          # sw covers 0x8C..0x8F
            hits.append((va, "sw +0x8C(w8E)", rt, rs, simm))
        # base computation addiu reg, reg, 0x8E (or 0x8C)
        elif opc == 0x09 and imm in (0x8E, 0x8C):  # addiu
            hits.append((va, f"addiu base {imm:#x}", rt, rs, simm))
    return hits

ov = open(OVERLAY, "rb").read()
exe = open(EXE, "rb").read()
overlay_code = ov[CODE_OFF:CODE_END_OFF]
exe_text = exe[EXE_HDR:EXE_HDR + (OVERLAY_VA - EXE_VA)]
print(f"scan sizes: overlay {len(overlay_code):#x}  exe_text {len(exe_text):#x}")

for buf, vbase, label in ((exe_text, EXE_VA, "EXE text"),):
    hits = scan(buf, vbase, label)
    print(f"=== {label}: {len(hits)} candidate sites ===")
    for va, kind, rt, rs, simm in hits:
        print(f"  {va:08X} {kind:18s} func={fn_of(va)}")

ovh = scan(overlay_code, OVERLAY_VA, "overlay")
print(f"=== overlay: {len(ovh)} candidate sites ===")
for va, kind, rt, rs, simm in ovh:
    print(f"  {va:08X} {kind:18s} func={fn_of(va)}")
