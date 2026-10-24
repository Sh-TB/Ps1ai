#!/usr/bin/env python3
"""Phase 2c: find every instruction in the ENEMY.BIN overlay code region that
reads/writes the mystery entity field +0x8E (and the companion fields +0xEA,
+0xEB, +0xF4, +0x7E, +0x92), and map each site to its containing Ghidra
function. This is the raw-bytes ground truth for the truck damage path.

Output: work/msx_recomp/evidence/issue5_truck/field_access_scan.json
"""
import json, os, struct
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

REPO = "/home/z/my-project/ps1ai"
OVERLAY = f"{REPO}/ps1play/re/ENEMY.BIN"
OUT = "/home/z/my-project/work/msx_recomp/evidence/issue5_truck"

OVERLAY_VA = 0x8009C0E8
CODE_OFF = 0xD180
CODE_END_OFF = 0x1C2C8

data = open(OVERLAY, "rb").read()
code = data[CODE_OFF:CODE_END_OFF]
base_va = OVERLAY_VA

funcs = json.load(open(f"{REPO}/data/games/SLUS-01212/ghidra/ghidra_overlay_functions.json"))
fn_bounds = []  # (start, end, name)
for f in funcs:
    start = int(f["entry"], 16)
    fn_bounds.append((start, start + f["bytes"], f["name"]))
fn_bounds.sort()

def fn_of(va):
    lo, hi = 0, len(fn_bounds) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        s, e, n = fn_bounds[mid]
        if va < s:
            hi = mid - 1
        elif va >= e:
            lo = mid + 1
        else:
            return n
    return None

FIELDS = {0x8E: "field_8E", 0xEA: "field_EA", 0xEB: "field_EB",
          0xF4: "field_F4", 0x7E: "field_7E", 0x92: "field_92"}
OPC = {0x21: "lh", 0x25: "lhu", 0x29: "sh", 0x28: "sb", 0x23: "lw", 0x2B: "sw"}

hits = []
for off in range(0, len(code) - 3, 4):
    w = struct.unpack_from("<I", code, off)[0]
    opc = w >> 26
    if opc not in OPC:
        continue
    imm = w & 0xFFFF
    if imm not in FIELDS:
        continue
    va = base_va + off
    hits.append({
        "va": va,
        "insn": OPC[opc],
        "field": FIELDS[imm],
        "imm": imm,
        "func": fn_of(va) or "?",
    })

summary = {}
for h in hits:
    key = (h["field"], h["insn"])
    summary.setdefault(key, []).append(h)

print("=== +0x8E access sites (the mystery field) ===")
for insn in ("sh", "sw"):
    lst = summary.get(("field_8E", insn), [])
    print(f"-- {insn} to +0x8E: {len(lst)} sites")
    for h in lst:
        print(f"   {h['va']:08X} in {h['func']}")
for insn in ("lh", "lhu"):
    lst = summary.get(("field_8E", insn), [])
    funcs_hit = {}
    for h in lst:
        funcs_hit.setdefault(h["func"], []).append(h["va"])
    print(f"-- {insn} from +0x8E: {len(lst)} sites in {len(funcs_hit)} funcs")

print("\n=== other tracked fields (write sites) ===")
for fld in ("field_EA", "field_EB", "field_F4", "field_7E", "field_92"):
    for insn in ("sh", "sb", "sw"):
        lst = summary.get((fld, insn), [])
        if lst:
            fc = {}
            for h in lst:
                fc.setdefault(h["func"], 0)
                fc[h["func"]] += 1
            print(f"-- {fld} {insn}: {len(lst)} sites in {len(fc)} funcs: "
                  + ", ".join(sorted(fc)[:8]))

os.makedirs(OUT, exist_ok=True)
with open(f"{OUT}/field_access_scan.json", "w") as fh:
    json.dump({"hits": hits, "summary_counts": {
        f"{k[0]}_{k[1]}": len(v) for k, v in summary.items()}}, fh, indent=1)
print("\nsaved ->", f"{OUT}/field_access_scan.json")
