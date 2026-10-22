#!/usr/bin/env python3
"""msx_gate_static2.py — data-pointer scan for FUN_800A87F8 + disassembly
of its callees (0x8001a158, 0x800b57fc) and the grefs table."""
import json
import sqlite3
import struct

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

ENEMY = "/home/z/my-project/ps1ai/ps1play/re/ENEMY.BIN"
EXE = "/home/z/my-project/ps1ai/ps1play/re/SLUS_012.12"
CODE_OFF, CODE_END_OFF, DEST = 0xD180, 0x1C2C8, 0x8009C0E8
TARGET = 0x800A87F8
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.skipdata = True

code = open(ENEMY, "rb").read()
exe = open(EXE, "rb").read()
pat = struct.pack("<I", TARGET)          # little-endian pointer bytes

def scan(blob, base_va, lo=0, hi=None):
    hits, i = [], 0
    hi = hi if hi is not None else len(blob)
    region = blob[lo:hi]
    while True:
        i = region.find(pat, i)
        if i < 0:
            break
        hits.append(base_va + lo + i)
        i += 4
    return hits

ov_hits = scan(code, DEST, CODE_OFF, CODE_END_OFF)
exe_hits = scan(exe, 0x80010000, 0x800, 0x800 + 620544)
print("overlay data refs to FUN_800A87F8:", [hex(a) for a in ov_hits])
print("EXE data refs to FUN_800A87F8:", [hex(a) for a in exe_hits])

# who owns each overlay ref (function containing it)?
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

for va in ov_hits:
    o = owner(va)
    print(f"  ov {va:08x} in {o[1]['name']} (entry {o[1]['entry']}, "
          f"{o[1]['bytes']}B)" if o else f"  ov {va:08x} owner ??")

# relative position inside owner function (offset from entry)
for va in ov_hits:
    o = owner(va)
    if o:
        print(f"     -> offset +{va - o[0]:#x} into {o[1]['name']}")

# ---------------------------------------------- disassemble EXE callees
def dis_exe(va, nbytes=120, label=""):
    off = 0x800 + (va - 0x80010000)
    print(f"\n--- {label} {va:08x} (file {off:#x}) ---")
    for ins in list(md.disasm(exe[off:off + nbytes], va))[:30]:
        print(f"  {ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}")

dis_exe(0x8001A158, 160, "callee1")
dis_exe(0x800B57FC, 160, "callee2")

# ------------------------------------------- grefs in sqlite for target
c = sqlite3.connect(
    "/home/z/my-project/work/msx_recomp/index/re_index.sqlite")
cols = [r[1] for r in c.execute("PRAGMA table_info(overlay_grefs)")]
print("\noverlay_grefs cols:", cols)
try:
    rows = c.execute(
        "SELECT * FROM overlay_grefs WHERE addr=2148177144 OR "
        "value=2148177144").fetchall()
    print("overlay_grefs hits:", len(rows))
    for r in rows[:20]:
        print("  ", ["%08x" % v if isinstance(v, int) and v > 0x100000
                     else v for v in r])
except Exception as e:
    print("gref query:", e)
