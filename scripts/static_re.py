#!/usr/bin/env python3
"""static_re.py — STATIC reverse engineering of SLUS_012.12.

'Turn the game into source': disassemble the main executable, build the
global-address xref map (which code touches which RAM address), and infer
the meaning of the GameShark addresses + the entity structures directly
from the code. Output: ps1play/re/source_map.json + readable report.

Method (pure numpy + capstone, no guessing):
  1. load text (file[2048:]) mapped at t_addr (0x80010000)
  2. scan every `lui rX, hi` and the following <=4 instructions:
       addiu/lw/lbu/lhu/sw/... with the same base reg
     -> effective virtual address = (hi<<16) + signed(lo)
  3. xref map: virtual addr -> [(pc, kind, insn)]
  4. for the GameShark-known addresses and the hottest globals:
     disassemble the surrounding function and list EVERY global access
     in it -> that cluster IS the struct (fields, neighbours, semantics).
"""
import json
import os
import struct
import sys
from collections import defaultdict

import numpy as np
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

EXE = "/home/z/my-project/ps1play/re/SLUS_012.12"
OUT_DIR = "/home/z/my-project/ps1play/re"

T_ADDR = 0x80010000

raw = open(EXE, "rb").read()
text = raw[2048:]
va0 = T_ADDR
words = np.frombuffer(text[:len(text) // 4 * 4], dtype="<u4")
print(f"text: {len(text)} bytes mapped at {va0:#010x} "
      f"({len(words)} instructions)")

SEXT = lambda v: v - 0x10000 if v >= 0x8000 else v          # noqa: E731
LOADSTORE = {0x20: "lb", 0x21: "lh", 0x22: "lwl", 0x23: "lw",
             0x24: "lbu", 0x25: "lhu", 0x26: "lwr",
             0x28: "sb", 0x29: "sh", 0x2A: "swl", 0x2B: "sw",
             0x2E: "swr"}

# ------------------------------------------------------------------
# 1) xref scan
# ------------------------------------------------------------------
w = words
is_lui = (w & 0xFC100000) == 0x3C000000
lui_idx = np.flatnonzero(is_lui)
print(f"lui instructions: {len(lui_idx)}")

xref = defaultdict(list)          # eff_va -> [(pc, kind, raw_insn)]
for i in lui_idx.tolist():
    insn = int(w[i])
    hi = insn & 0xFFFF
    rt = (insn >> 16) & 0x1F
    base = hi << 16
    pc = va0 + i * 4
    for j in range(i + 1, min(i + 5, len(w))):
        ij = int(w[j])
        op = ij >> 26
        rs = (ij >> 21) & 0x1F
        rt2 = (ij >> 16) & 0x1F
        if op == 0x0F:                        # new lui: hi overwritten
            break
        if op == 0x09 and rs == rt:           # addiu rT, rX, imm
            eff = base + SEXT(ij & 0xFFFF)
            if 0x80000000 <= eff < 0x81000000:
                xref[eff].append((pc, "addiu", ij))
        elif op in LOADSTORE and rs == rt:    # lw/sw/... off(rX)
            eff = base + SEXT(ij & 0xFFFF)
            if 0x80000000 <= eff < 0x81000000:
                xref[eff].append((pc, LOADSTORE[op], ij))

print(f"distinct referenced addresses: {len(xref)}")

# ------------------------------------------------------------------
# 2) xrefs for the published GameShark knowledge
# ------------------------------------------------------------------
GS = {
    "pad_mirror": 0x800D4948,
    "mission_unlock": 0x800D4213,
    "score_p1": 0x800EE318,
    "score_p2": 0x800EE320,
    "hp_p1": 0x80032764,
    "bombs_p1": 0x800398B4,
    "ammo_p1": 0x8002DCD8,
    "lives_p1": 0x800475A8,
    "timer": 0x800295F8,
    "weapon_id": 0x8002D92C,
    "pow_p1": 0x80087A78,
    "hit_slot_A": 0x800852D8,
    "hit_slot_B": 0x80085700,
    "hit_slot_C": 0x80085870,
}
print("\n=== GameShark address xrefs (static proof) ===")
gs_xrefs = {}
for name, va in GS.items():
    hits = xref.get(va, [])
    # also count neighbours +/-2 (halfword pairs are referenced via base)
    near = {va + d: len(xref.get(va + d, [])) for d in (-2, -1, 1, 2)}
    gs_xrefs[name] = {"va": va, "direct_xrefs": len(hits),
                      "sites": [hex(h[0]) for h in hits[:6]],
                      "near": {hex(k): v for k, v in near.items()}}
    print(f"  {name:15s} {va:#010x}: {len(hits):3d} direct xrefs "
          f"@ {[hex(h[0]) for h in hits[:4]]}")

# ------------------------------------------------------------------
# 3) hottest global addresses (the engine's real variable map)
# ------------------------------------------------------------------
hot = sorted(((len(v), a) for a, v in xref.items()), reverse=True)
print("\n=== top-40 referenced globals ===")
for n, a in hot[:40]:
    print(f"  {a:#010x}: {n}")

# ------------------------------------------------------------------
# 4) disassembly around key sites -> struct field clusters
# ------------------------------------------------------------------
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.skipdata = True


def disasm_func(pc, before=0x40, after=0xC0):
    lo = max(0, pc - va0 - before)
    hi = min(len(text), pc - va0 + after)
    code = text[lo:hi]
    out = []
    for ins in md.disasm(code, va0 + lo):
        out.append((ins.address, ins.mnemonic, ins.op_str))
    return out


def globals_in(window):
    """Every global access inside a disasm window (recomputed locally)."""
    found = defaultdict(list)
    regs = {}
    for idx, (addr, mn, op) in enumerate(window):
        if mn == "lui":
            parts = op.replace(",", " ").split()
            if len(parts) >= 2:
                try:
                    regs[parts[0]] = int(parts[1], 16) << 16
                except ValueError:
                    pass
        elif mn in ("addiu", "li", "lw", "sw", "lb", "lbu", "lh", "lhu",
                    "sb", "sh"):
            parts = op.replace(",", " ").replace("(", " ").replace(")",
                                                                   "").split()
            try:
                if mn == "addiu" and len(parts) == 3:
                    imm = int(parts[2], 0)
                    if parts[1] in regs:
                        eff = regs[parts[1]] + (imm - 0x10000
                                                if imm >= 0x8000 else imm)
                        found[eff].append(f"{addr:#x} {mn} {op}")
                elif mn in ("lw", "sw", "lb", "lbu", "lh", "lhu", "sb",
                            "sh") and len(parts) == 3:
                    imm = int(parts[0], 0)
                    if parts[2] in regs:
                        eff = regs[parts[2]] + (imm - 0x10000
                                                if imm >= 0x8000 else imm)
                        found[eff].append(f"{addr:#x} {mn} {op}")
            except ValueError:
                continue
    return found


print("\n=== struct field clusters around key sites ===")
clusters = {}
for name, va in GS.items():
    hits = xref.get(va, [])
    if not hits:
        continue
    pc = hits[0][0]
    win = disasm_func(pc)
    g = globals_in(win)
    lo_va = min(g) if g else va
    hi_va = max(g) if g else va
    fields = {hex(a - (lo_va & ~0xFF)): {"va": hex(a), "refs": v[:2]}
              for a, v in sorted(g.items())
              if lo_va - 0x200 <= a <= hi_va + 0x200}
    clusters[name] = {
        "site_pc": hex(pc), "window_globals": len(g),
        "range": [hex(lo_va), hex(hi_va)],
        "fields": {k: v for k, v in list(fields.items())[:40]},
    }
    print(f"\n  [{name}] site {pc:#x}, {len(g)} globals in window, "
          f"range {hex(lo_va)}..{hex(hi_va)}")
    for a, v in sorted(g.items())[:24]:
        print(f"     {a:#010x}  {v[0]}")

# ------------------------------------------------------------------
# 5) save source map
# ------------------------------------------------------------------
os.makedirs(OUT_DIR, exist_ok=True)
srcmap = {
    "exe": {"file": EXE, "t_addr": T_ADDR, "t_size": len(text),
            "pc0": 0x80082A44},
    "gs_xrefs": gs_xrefs,
    "hot_globals": [{"va": hex(a), "refs": n} for n, a in hot[:200]],
    "clusters": clusters,
}
with open(os.path.join(OUT_DIR, "source_map.json"), "w") as f:
    json.dump(srcmap, f, indent=1)
print(f"\nsource map -> {OUT_DIR}/source_map.json")
