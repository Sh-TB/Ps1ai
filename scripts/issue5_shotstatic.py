#!/usr/bin/env python3
"""issue5_shotstatic.py — static ENEMY.BIN overlay analysis for enemy-shot
logic (Issue #5 addendum Phase 4/5, static half).

Goal: rank overlay functions most likely to create/steer enemy
projectiles, using ONLY existing indexes + read-only capstone decode of
the owner's local ENEMY.BIN. No new index, no LLM dumps.

Signals used (each recorded per candidate):
  * indegree from overlay_edges (dispatch/update loops call many)
  * references to the player-handle word 0x800C9A98 (AI reads player)
  * stores with velocity-like immediates into a fresh entity base
  * calls into EXE text (engine services: alloc/sprite/sound)
"""
import os
import sys
import sqlite3

WS = "/home/z/my-project/work/msx_recomp"
BIN = "/home/z/my-project/ps1ai/ps1play/re/ENEMY.BIN"
BASE = 0x8009C0E8          # live-verified overlay load address
OFF = 0xD180               # code region file offset
PLAYER_HANDLE = 0x800C9A98

try:
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32
except ImportError:
    sys.exit("capstone missing")


def load():
    db = sqlite3.connect(os.path.join(WS, "index/re_index.sqlite"))
    db.row_factory = sqlite3.Row
    return db


def funcs(db):
    cur = db.execute("SELECT va,size FROM overlay_functions")
    out = []
    for r in cur:
        va = int(str(r["va"]), 16) if isinstance(r["va"], str) else r["va"]
        out.append((va, r["size"]))
    return sorted(out)


def indegree(db):
    ind = {}
    for r in db.execute("SELECT dst FROM overlay_edges"):
        d = r["dst"]
        d = int(str(d), 16) if isinstance(d, str) else d
        ind[d] = ind.get(d, 0) + 1
    return ind


def gref_targets(db):
    """set of overlay PCs that reference PLAYER_HANDLE (direct lui/ori)."""
    hits = {}
    for r in db.execute("SELECT va,pc FROM overlay_grefs"):
        pc = r["pc"]
        pc = int(str(pc), 16) if isinstance(pc, str) else pc
        if pc == PLAYER_HANDLE:
            va = r["va"]
            va = int(str(va), 16) if isinstance(va, str) else va
            hits.setdefault(va, 0)
            hits[va] += 1
    return hits


def into_exe(db):
    """calls from overlay into EXE text, grouped by caller."""
    calls = {}
    for r in db.execute("SELECT src,dst,dst_region FROM overlay_edges"):
        reg = r["dst_region"]
        if reg and "exe" in str(reg).lower():
            s = r["src"]
            s = int(str(s), 16) if isinstance(s, str) else s
            calls[s] = calls.get(s, 0) + 1
    return calls


def disasm_fn(data, va, size, limit=220):
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    off = OFF + (va - BASE)
    code = data[off:off + min(size, limit * 4)]
    out = []
    for i in md.disasm(code, va):
        out.append(f"{i.address:08X}: {i.mnemonic:8s} {i.op_str}")
    return out


def main():
    data = open(BIN, "rb").read()
    db = load()
    fns = funcs(db)
    ind = indegree(db)
    ph = gref_targets(db)          # fn va -> #refs to player handle
    xc = into_exe(db)              # fn va -> #calls into EXE

    def fn_of(addr):
        lo, hi = 0, len(fns) - 1
        while lo <= hi:
            m = (lo + hi) // 2
            if fns[m][0] <= addr < fns[m][0] + max(fns[m][1], 4):
                return fns[m][0]
            if fns[m][0] > addr:
                hi = m - 1
            else:
                lo = m + 1
        return None

    ph_fn = {}
    for va, n in ph.items():
        f = fn_of(va)
        if f is not None:
            ph_fn[f] = ph_fn.get(f, 0) + n

    rows = []
    for va, size in fns:
        rows.append({"va": va, "size": size, "indegree": ind.get(va, 0),
                     "player_refs": ph_fn.get(va, 0),
                     "exe_calls": xc.get(va, 0)})
    rows.sort(key=lambda r: (-r["player_refs"], -r["indegree"]))
    print("== candidates ranked by player-handle refs then indegree")
    for r in rows[:15]:
        print(f"{r['va']:08X} size={r['size']:<5} ind={r['indegree']:<4} "
              f"player_refs={r['player_refs']:<3} exe_calls={r['exe_calls']}")
    print("\n== highest indegree overall")
    for r in sorted(rows, key=lambda r: -r["indegree"])[:8]:
        print(f"{r['va']:08X} size={r['size']:<5} ind={r['indegree']:<4} "
              f"player_refs={r['player_refs']}")
    # dump the top-3 player-ref functions' first stores to immediates
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    print("\n== store signatures of top-6 player-ref functions")
    for r in rows[:6]:
        va, size = r["va"], r["size"]
        off = OFF + (va - BASE)
        stores, spd = [], []
        for i in md.disasm(data[off:off + size], va):
            if i.mnemonic in ("sb", "sh", "sw"):
                stores.append(f"{i.address:08X} {i.mnemonic} {i.op_str}")
            if i.mnemonic in ("lui", "addiu", "ori") and \
                    ("sp" not in i.op_str):
                spd.append(f"{i.address:08X} {i.mnemonic} {i.op_str}")
        print(f"-- {va:08X} size={size} ind={r['indegree']} "
              f"player_refs={r['player_refs']}")
        for s in stores[:12]:
            print("   ", s)
    db.close()


if __name__ == "__main__":
    main()
