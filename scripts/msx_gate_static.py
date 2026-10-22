#!/usr/bin/env python3
"""msx_gate_static.py — Phase 2 static probe: ground-truth disassembly of
ENEMY.BIN overlay @0x8009C0E8 to find FUN_800a87f8, its body, and every
jal/j/b targeting it (callers), plus cross-reference of the known entity
table constants (0x800CA268 base, stride 0x14C, HP +0x8E).

Outputs a compact report to stdout (JSON at the end).
"""
import json
import sys

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

ENEMY = "/home/z/my-project/ps1ai/ps1play/re/ENEMY.BIN"
EXE = "/home/z/my-project/ps1ai/ps1play/re/SLUS_012.12"
CODE_OFF = 0xD180            # ENEMY.BIN code region file offset
DEST = 0x8009C0E8            # live-mapped destination (verified live)
CODE_END_OFF = 0x1C2C8
TARGET = 0x800A87F8
TGT_OFF = CODE_OFF + (TARGET - DEST)

code = open(ENEMY, "rb").read()
exe = open(EXE, "rb").read()
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.skipdata = True

out = {"target": hex(TARGET), "tgt_file_off": hex(TGT_OFF)}

# ---------------------------------------------------------------- body
print("=" * 72)
print(f"FUN_800A87F8 body (file off {hex(TGT_OFF)}):")
body = []
for ins in md.disasm(code[TGT_OFF:TGT_OFF + 56], TARGET):
    print(f"  {ins.address:08x}: {ins.bytes.hex():<12} {ins.mnemonic:<8} {ins.op_str}")
    body.append({"a": ins.address, "m": ins.mnemonic, "o": ins.op_str,
                 "b": ins.bytes.hex()})
out["body"] = body

# ------------------------------------------------- in-overlay callers
callers = []
lo, hi = CODE_OFF, CODE_END_OFF
blob = code[lo:hi]
# jal 0xTARGET  => opcode 3 << 26 | (TARGET>>2)&0x3FFFFFF
def jal_word(tgt):
    return (3 << 26) | ((tgt >> 2) & 0x3FFFFFF)
import struct
w = struct.pack(">I", jal_word(TARGET))
i = 0
while True:
    i = blob.find(w, i)
    if i < 0:
        break
    va = DEST + (lo + i - lo)
    # disassemble a window around to know the function context: walk back
    callers.append(va)
    i += 4
out["jal_sites_in_overlay"] = [hex(a) for a in callers]
print(f"\njal sites targeting {hex(TARGET)} inside overlay: "
      f"{[hex(a) for a in callers]}")

# J (opcode 2) too
wj = struct.pack(">I", (2 << 26) | ((TARGET >> 2) & 0x3FFFFFF))
i = 0
j_sites = []
while True:
    i = blob.find(wj, i)
    if i < 0:
        break
    j_sites.append(DEST + i)
    i += 4
out["j_sites_in_overlay"] = [hex(a) for a in j_sites]

# --------------------------------------------- EXE-side jal callers
w2 = struct.pack(">I", jal_word(TARGET))
i = 0
exe_callers = []
while True:
    i = exe.find(w2, i)
    if i < 0:
        break
    exe_callers.append(0x80010000 + i if i >= 0x10000 else i)  # rough VA
    i += 4
# EXE text at t_addr 0x80010000, file offset of EXE header 0x800; text
# starts at file 0x800 for PSX EXE (pc0 in header). Verify mapping:
# re_index identity: t_addr 0x80010000, t_size 620544; typical layout:
# file 0x800 -> 0x80010000
exe_callers = [0x80010000 + (a) for a in exe_callers]
out["jal_sites_in_exe"] = [hex(a) for a in exe_callers]
print(f"jal sites targeting {hex(TARGET)} inside EXE: "
      f"{[hex(a) for a in exe_callers]}")

# ----------------------------------- nearby caller function mapping
gh = json.load(open(
    "/home/z/my-project/ps1ai/data/games/SLUS-01212/ghidra/"
    "ghidra_overlay_functions.json"))
byentry = {int(f["entry"], 16): f for f in gh}
def owner(va):
    best = None
    for e, f in byentry.items():
        size = f.get("bytes", 4)
        if e <= va < e + size:
            if best is None or e > best[0]:
                best = (e, f)
    return best
print("\nCallers (function owners):")
for va in callers:
    o = owner(va)
    print(f"  site {va:08x} -> {o[1]['name'] if o else '?? '}")
    if o:
        out.setdefault("callers", []).append(
            {"site": hex(va), "fn": o[1]["name"], "fn_entry": o[1]["entry"],
             "fn_bytes": o[1]["bytes"]})

json.dump(out, open("/home/z/my-project/scripts/msx_gate_static_out.json",
                    "w"), indent=1)
print("\nsaved -> /home/z/my-project/scripts/msx_gate_static_out.json")
