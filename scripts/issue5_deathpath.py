#!/usr/bin/env python3
"""issue5_deathpath.py — static death-path analysis for SLUS_012.12
(issue #5 continuation §4).

Finds every instruction in the MAIN EXE and the ENEMY.BIN overlay that
REFERENCES the live-verified player-HP pair (0x800CA2F6 / 0x800CA2FE)
via lui+base/offset addressing (the grefs index only has the single
absolute lhu reader — writers use register bases), then reconstructs
the containing functions and call graph.

Method (no new index, reuse re_index.sqlite for functions/edges):
  scan text words for store/load encodings with a signed 16-bit offset
  that hits the target VA when added to a 0x800C0000/0x800D0000-style
  lui base; pair each hit with the nearest preceding lui of that base
  register; attribute hits to functions via the function index.
"""
import json
import os
import sqlite3
import struct
import sys

REPO = "/home/z/my-project/ps1ai"
WORK = "/home/z/my-project/work/msx_recomp"
DB = os.path.join(WORK, "index", "re_index.sqlite")
EXE = os.path.join(WORK, "SLUS_012.12.full")
OUT = os.path.join(REPO, "data/games/SLUS-01212/death_path.json")

TEXT_VA = 0x80010000
HP0, HP1 = 0x800CA2F6, 0x800CA2FE
ROOT = 0x800C9A98
PER_LIFE = 0x800CA2E0
TARGETS = {HP0: "hp_word_0xCA2F6", HP1: "hp_word_0xCA2FE",
           PER_LIFE: "per_life_0xCA2E0"}

OPC = lambda w: (w >> 26) & 0x3F
RS = lambda w: (w >> 21) & 0x1F
RT = lambda w: (w >> 16) & 0x1F
IMM = lambda w: w & 0xFFFF
SIMM = lambda w: IMM(w) - 0x10000 if IMM(w) & 0x8000 else IMM(w)
FUNCT = lambda w: w & 0x3F

LOADS = {0x20: "lb", 0x21: "lh", 0x24: "lbu", 0x25: "lhu", 0x23: "lw"}
STORES = {0x28: "sb", 0x29: "sh", 0x2B: "sw"}


def base_hint_ok(reg_base, base_reg, w):
    """True when this lw's effective VA is the player-root pointer slot
    (0x800C9A98) reached via a tracked lui chain."""
    if base_reg not in reg_base:
        return False
    va = (reg_base[base_reg][0] + SIMM(w)) & 0xFFFFFFFF
    return va == ROOT


def scan_segment(words, base_va, module, db, targets=TARGETS):
    """Scan a code segment for memory ops reaching the target VAs via:
    (a) lui base + signed offset memop;
    (b) lui + addiu/ori pointer chains + offset-0/near memop;
    (c) the player-root pointer (0x800C9A98) loaded from a lui-chain
        followed by root-relative field memops (target - root = 0x85E
        / 0x866 / 0x848)."""
    hits = []
    reg_base = {}          # reg -> (base_va, pc_of_last_setter)
    reg_root = {}          # reg -> True (holds player root ptr)
    ROOT_OFF = {TARGETS[HP0]: HP0 - ROOT, TARGETS[HP1]: HP1 - ROOT,
                TARGETS[PER_LIFE]: PER_LIFE - ROOT}
    for i, w in enumerate(words):
        op = OPC(w)
        pc = base_va + i * 4
        if op == 0x0F:                       # lui rt, imm
            reg_base[RT(w)] = (IMM(w) << 16, pc)
            reg_root.pop(RT(w), None)
            continue
        if op == 0x09 or op == 0x0D:         # addiu/ori rt, rs, imm
            rs, rt = RS(w), RT(w)
            if rs in reg_base:
                delta = IMM(w) if op == 0x0D else SIMM(w)
                reg_base[rt] = ((reg_base[rs][0] + delta) & 0xFFFFFFFF,
                                pc)
                reg_root.pop(rt, None)
            elif rs in reg_root:
                reg_root[rt] = True
                reg_base.pop(rt, None)
            continue
        if op == 0x23 and base_hint_ok(reg_base, RS(w), w):
            # lw $rX, <off>(lui-chain base) -> player root pointer load
            reg_root[RT(w)] = True
            reg_base.pop(RT(w), None)
            continue
        table = LOADS.get(op) or STORES.get(op)
        if table is None:
            continue
        base = RS(w)
        off = SIMM(w)
        if base in reg_base:
            va = (reg_base[base][0] + off) & 0xFFFFFFFF
            if va in targets:
                hits.append({"module": module, "pc": pc,
                             "lui_pc": reg_base[base][1], "kind": table,
                             "target": hex(va), "role": targets[va],
                             "is_write": op in STORES,
                             "width": {"sb": 1, "sh": 2, "sw": 4,
                                       "lb": 1, "lbu": 1, "lh": 2,
                                       "lhu": 2, "lw": 4}[table]})
        elif base in reg_root:
            for role, doff in ROOT_OFF.items():
                if off == doff:
                    hits.append({"module": module, "pc": pc,
                                 "kind": table, "target": hex(ROOT + off),
                                 "role": f"root_rel_{role}(+{doff:#x})",
                                 "is_write": op in STORES,
                                 "width": {"sb": 1, "sh": 2, "sw": 4,
                                           "lb": 1, "lbu": 1, "lh": 2,
                                           "lhu": 2, "lw": 4}[table]})
    return hits


def func_of(db, va, module):
    """Nearest function at or below va (string hex compare = numeric
    for fixed-width 0x8xxxxxx strings)."""
    t = "functions" if module == "EXE" else "overlay_functions"
    h = f"0x{va:08X}"
    row = db.execute(
        f"SELECT va, size, name FROM {t} WHERE va <= ? ORDER BY va DESC "
        "LIMIT 1", (h,)).fetchone()
    if not row:
        return None
    start = int(row[0], 16)
    if va < start + row[1]:
        return {"va": row[0], "name": row[2], "size": row[1]}
    return {"va": None, "name": f"UNINDEXED_{h}", "size": None}


def callers(db, fva):
    if fva is None:
        return []
    return [r[0] for r in db.execute(
        "SELECT src FROM edges WHERE dst=?", (fva,)).fetchall()]


def main():
    db = sqlite3.connect(DB)
    out = {"targets": {hex(k): v for k, v in TARGETS.items()},
           "exe_identity": "sha256 1508b532 (canonical, Phase 0)",
           "hits": []}

    # ---- main EXE text ----
    blob = open(EXE, "rb").read()
    seg = blob[2048:]                    # 2048-byte PS-X EXE header
    n = (len(seg) // 4) * 4
    words = struct.unpack(f"<{n//4}I", seg[:n])
    exe_hits = scan_segment(words, TEXT_VA, "EXE", db)
    # EXE text hi = 0x800A7800; ENEMY.BIN loads verbatim at 0x8009C0E8
    # and REPLACES live RAM in 0x8009C0E8..0x800A7800 — mark those hits
    ov_base = 0x8009C0E8
    for h in exe_hits:
        h["live"] = not (ov_base <= h["pc"] < 0x800A7800)
    out["hits"] += exe_hits

    # ---- ENEMY.BIN overlay (live-verified VA 0x8009C0E8) ----
    ov_path = os.path.join(REPO, "ps1play", "re", "ENEMY.BIN")
    ov = open(ov_path, "rb").read()
    n = (len(ov) // 4) * 4
    ov_words = struct.unpack(f"<{n//4}I", ov[:n])
    out["hits"] += scan_segment(ov_words, ov_base, "ENEMY.BIN", db)

    # ---- attribute to functions + callers ----
    for h in out["hits"]:
        f = func_of(db, h["pc"], h["module"])
        h["function"] = f
        h["callers"] = callers(db, f["va"]) if f else []

    with open(OUT, "w") as fp:
        json.dump(out, fp, indent=1)

    for h in out["hits"]:
        print(f"{h['module']:9s} {h['pc']:#x} {h['kind']:<3s} "
              f"{h['target']} {h['role']:<18s} fn={h['function']['name']} "
              f"callers={h['callers'][:4]}")
    print(f"\ntotal {len(out['hits'])} hits -> {OUT}")


if __name__ == "__main__":
    main()
