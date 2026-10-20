#!/usr/bin/env python3
"""static_re.py — STATIC reverse engineering of SLUS_012.12 (Issue #3).

'Turn the game into source': disassemble the main executable, build the
global-address xref map (which code touches which RAM address), and infer
the meaning of the GameShark addresses + the entity structures directly
from the code. Output: source_map.json + readable report.

All paths are resolved repository-relative (or via CLI); large outputs
default to an EXTERNAL analysis workspace, never a hard-coded home path.

Usage:
  python3 scripts/static_re.py [--exe <PS-X EXE>] [--out <dir>]
                               [--game <cue/bin>] [--force]

Resolution order for the exe: --exe > extract via --game (cue/bin) >
<repo>/ps1play/re/SLUS_012.12 (gitignored owner-local copy if present).
The image-derived exe is preferred: the legacy in-repo copy is truncated
by its final 2048 bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
from collections import defaultdict

import numpy as np
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from game_rebuild_index import (  # noqa: E402
    DiscImage, parse_pvd, walk_disc, parse_system_cnf, resolve_cue_bin,
)

T_ADDR = 0x80010000
LEGACY_EXE = os.path.join(_REPO, "ps1play", "re", "SLUS_012.12")

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
    "player_obj_ptr": 0x800C9A98,
}

SEXT = lambda v: v - 0x10000 if v >= 0x8000 else v          # noqa: E731
LOADSTORE = {0x20: "lb", 0x21: "lh", 0x22: "lwl", 0x23: "lw",
             0x24: "lbu", 0x25: "lhu", 0x26: "lwr",
             0x28: "sb", 0x29: "sh", 0x2A: "swl", 0x2B: "sw",
             0x2E: "swr"}
ITYPE_WRITES_RT = {0x08, 0x0A, 0x0B, 0x0C, 0x0E}


def exe_from_image(game):
    """Extract the boot exe through ISO records (never a fixed offset)."""
    disc = DiscImage(game)
    pvd = parse_pvd(disc)
    if pvd is None:
        raise SystemExit("no ISO9660 PVD")
    files, _dirs = walk_disc(disc, pvd)
    cnf = None
    for f in files:
        if f["path"].upper().endswith("SYSTEM.CNF"):
            cnf = disc.read_user_range(f["lba"], min(f["size"], 4096))
            break
    boot = parse_system_cnf(cnf.decode("ascii", "replace")) if cnf else None
    for f in files:
        base = f["path"].split("/")[-1]
        if boot and base.upper() in (boot.upper(), boot.upper() + ";1"):
            data = disc.read_user_range(f["lba"], f["size"])
            if data[:8] == b"PS-X EXE":
                return data, f["path"]
    raise SystemExit(f"boot exe {boot!r} not found / not a PS-X EXE")


def scan_xrefs(words, va0):
    """Register-tracked lui->access effective-address xref scan."""
    xref = defaultdict(list)
    n = len(words)
    for i in range(n):
        w = int(words[i])
        if (w & 0xFC100000) != 0x3C000000:
            continue
        hi16 = w & 0xFFFF
        rt = (w >> 16) & 0x1F
        if rt == 0:
            continue
        base = hi16 << 16
        for j in range(i + 1, min(i + 25, n)):
            ij = int(words[j])
            op = ij >> 26
            rs = (ij >> 21) & 0x1F
            rtj = (ij >> 16) & 0x1F
            if op == 0x00:
                if ((ij >> 11) & 0x1F) == rt:
                    break
                continue
            if op == 0x0F:
                if rtj == rt:
                    break
                continue
            if op in LOADSTORE and rs == rt:
                eff = base + SEXT(ij & 0xFFFF)
                if 0x80000000 <= eff < 0x81000000:
                    xref[eff].append((va0 + j * 4, LOADSTORE[op], ij))
                continue
            if op == 0x09 and rs == rt:
                base = base + SEXT(ij & 0xFFFF)
                if 0x80000000 <= base < 0x81000000:
                    xref[base].append((va0 + j * 4, "addiu", ij))
                continue
            if op == 0x0D and rs == rt and rtj == rt:
                base = base | (ij & 0xFFFF)
                continue
            if op in ITYPE_WRITES_RT and rtj == rt:
                break
            if op == 0x09 and rtj == rt:
                break
    return xref


def disasm_func(text, va0, pc, before=0x40, after=0xC0):
    lo = max(0, pc - va0 - before)
    hi = min(len(text), pc - va0 + after)
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    md.skipdata = True
    return [(i.address, i.mnemonic, i.op_str)
            for i in md.disasm(text[lo:hi], va0 + lo)]


def globals_in(window):
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
            parts = op.replace(",", " ").replace("(", " ").replace(
                ")", "").split()
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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exe", default=None,
                    help="owner-local PS-X EXE file")
    ap.add_argument("--game", default=None,
                    help="owner-local cue/bin — exe is extracted via "
                         "ISO records (preferred, complete)")
    ap.add_argument("--out", default=os.path.join(
        _REPO, "ps1play", "re"),
        help="output dir (default: <repo>/ps1play/re; large runs should "
             "pass an external workspace)")
    ap.add_argument("--json-out", default=None,
                    help="alternative output file for source_map.json")
    args = ap.parse_args()

    if args.exe:
        raw = open(args.exe, "rb").read()
        origin = args.exe
    elif args.game:
        raw, origin = exe_from_image(args.game)
    elif os.path.exists(LEGACY_EXE):
        raw = open(LEGACY_EXE, "rb").read()
        origin = LEGACY_EXE
        print(f"NOTE: using legacy in-repo exe ({len(raw)} B) — "
              "this copy is missing its final 2048 bytes; prefer "
              "--game/--exe")
    else:
        raise SystemExit("no exe source: pass --exe or --game")

    if raw[:8] != b"PS-X EXE":
        raise SystemExit(f"not a PS-X EXE: {origin}")
    pc0 = struct.unpack_from("<I", raw, 0x10)[0]
    t_addr = struct.unpack_from("<I", raw, 0x18)[0]
    t_size = struct.unpack_from("<I", raw, 0x1C)[0]
    text = raw[0x800:0x800 + t_size]
    va0 = t_addr
    words = np.frombuffer(text[:len(text) // 4 * 4], dtype="<u4")
    print(f"exe: {origin} ({len(raw)} B) text {len(text)} B at "
          f"{va0:#010x} entry {pc0:#010x}")

    xref = scan_xrefs(words, va0)
    print(f"distinct referenced addresses: {len(xref)}")

    gs_xrefs = {}
    for name, va in GS.items():
        hits = xref.get(va, [])
        near = {va + d: len(xref.get(va + d, [])) for d in
                (-2, -1, 1, 2)}
        gs_xrefs[name] = {"va": va, "direct_xrefs": len(hits),
                          "sites": [hex(h[0]) for h in hits[:6]],
                          "near": {hex(k): v for k, v in near.items()}}
        print(f"  {name:15s} {va:#010x}: {len(hits):3d} direct xrefs "
              f"@ {[hex(h[0]) for h in hits[:4]]}")

    hot = sorted(((len(v), a) for a, v in xref.items()), reverse=True)
    print("\n=== top-40 referenced globals ===")
    for n_, a in hot[:40]:
        print(f"  {a:#010x}: {n_}")

    print("\n=== struct field clusters around key sites ===")
    clusters = {}
    for name, va in GS.items():
        hits = xref.get(va, [])
        if not hits:
            continue
        pc = hits[0][0]
        win = disasm_func(text, va0, pc)
        g = globals_in(win)
        if not g:
            continue
        lo_va, hi_va = min(g), max(g)
        fields = {hex(a - (lo_va & ~0xFF)): {"va": hex(a),
                                             "refs": v[:2]}
                  for a, v in sorted(g.items())
                  if lo_va - 0x200 <= a <= hi_va + 0x200}
        clusters[name] = {
            "site_pc": hex(pc), "window_globals": len(g),
            "range": [hex(lo_va), hex(hi_va)],
            "fields": dict(list(fields.items())[:40]),
        }

    os.makedirs(args.out, exist_ok=True)
    srcmap = {
        "exe": {"file": origin,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "t_addr": t_addr, "t_size": t_size, "pc0": pc0,
                "text_len": len(text)},
        "gs_xrefs": gs_xrefs,
        "hot_globals": [{"va": hex(a), "refs": n_} for n_, a in
                        hot[:200]],
        "clusters": clusters,
    }
    out_path = args.json_out or os.path.join(args.out,
                                             "source_map.json")
    with open(out_path, "w") as f:
        json.dump(srcmap, f, indent=1)
    print(f"\nsource map -> {out_path}")


if __name__ == "__main__":
    main()
