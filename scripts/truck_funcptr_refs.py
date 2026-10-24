#!/usr/bin/env python3
"""Phase 2b: who references the truck-path functions?

The Ghidra callers lists are empty for FUN_8009de68/800a41d8/800a4588 ->
they are probably invoked via entity state-pointer dispatch. Find every
reference to these addresses inside the corpus:
  1. C-text mentions (decompiler printed the address / pointer cast)
  2. Raw pointer words in function byte blobs (function-pointer tables)
Also: proper hub-user count (case-insensitive), and dump Ghidra C for the
three targets to cross-check the m2c reading.
"""
import json, struct, os, re

REPO = "/home/z/my-project/ps1ai"
OUT = "/home/z/my-project/work/msx_recomp/evidence/issue5_truck"

corp = json.load(open(f"{REPO}/data/games/SLUS-01212/ghidra/overlay_decompiled.json"))

TARGETS = [0x8009DE68, 0x800A41D8, 0x800A4588, 0x800AB094,
           0x800AB0FC, 0x800AADBC, 0x800B179C, 0x800151DC]
target_set = set(TARGETS)

def bytes_of(f):
    b = f.get("bytes")
    if isinstance(b, bytes):
        return b
    if isinstance(b, str):
        try:
            return bytes.fromhex(b)
        except ValueError:
            return b""
    return b""

# 1+2: scan every corpus entry
ref_map = {t: [] for t in TARGETS}
hub_users = []
for addr, f in corp.items():
    c = f.get("c") or ""
    low = c.lower()
    if "800c9a98" in low or "-6568" in low or "-0x6568" in low:
        hub_users.append(addr)
    for t in TARGETS:
        # C text mention (fun_8009de68 or 0x8009de68)
        if f"{t:08x}" in low or f"{t:x}" in low:
            ref_map[t].append((addr, "ctext"))
            continue
        # raw pointer word in bytes
        b = bytes_of(f)
        if b:
            packed = struct.pack("<I", t)
            if packed in b:
                ref_map[t].append((addr, "ptrword"))

print("=== references (overlay corpus) ===")
for t in TARGETS:
    entries = ref_map[t]
    kinds = {}
    for a, k in entries:
        kinds.setdefault(k, []).append(a)
    print(f"{t:08X}:")
    for k, addrs in kinds.items():
        print(f"   {k}: {len(addrs)} -> {[corp[a]['name'] for a in addrs[:12]]}")

print(f"\nhub users (case-insens): {len(hub_users)} functions")
print(sorted(corp[a]["name"] for a in hub_users[:20]), "...")

# 3: Ghidra C for the three targets (cross-check m2c)
print("\n=== Ghidra C: FUN_8009de68 ===")
print(corp["8009de68"]["c"][:1800])
print("\n=== Ghidra C: FUN_800a41d8 ===")
print(corp["800a41d8"]["c"][:1400])
print("\n=== Ghidra C: FUN_800a4588 (head) ===")
print(corp["800a4588"]["c"][:1400])

out = {
    "refs": {f"{t:08x}": [{"ref_site": a, "kind": k, "site_name": corp[a]["name"]}
                           for a, k in ref_map[t]] for t in TARGETS},
    "hub_users": hub_users,
}
os.makedirs(OUT, exist_ok=True)
with open(f"{OUT}/funcptr_refs.json", "w") as fh:
    json.dump(out, fh, indent=1)
