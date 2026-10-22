#!/usr/bin/env python3
"""w2_find_bombs.py — locate the FALLING entities in RAM directly.

Method: from `arena2` (camera locked, bombs visible mid-fall on screen),
dump candidate memory windows at f0 / f10 / f20 / f30 and find u16
words whose per-frame delta matches falling motion (x ~constant,
y changes 1..8/frame monotonic). Dump the full 40-slot x 0x14C table
PLUS a wider scan of the ENEMY.BIN data region.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import msx_gate_probe as gp                     # noqa: E402

EVID = gp.EVID
TABLE, STRIDE = gp.TABLE, gp.STRIDE


def snap_u16(mem, lo, hi):
    return mem.ram[lo:hi].view("<u2").astype(np.int32)


def main():
    p, fw = gp.boot()
    m = p.mem
    p.load_state("arena2")
    session = gp.freeze_now(p, "w2_findbombs")
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()
    gp.png(p, "w2fb_f0.png")

    LO, HI = 0x0C9000, 0x0E0000        # entity table + overlay data zone
    snaps = []
    for k in range(4):
        snaps.append(snap_u16(m, LO, HI))
        if k < 3:
            p.core.set_buttons(set())
            p.core.run(10, set())
            session.gs.tick()
    gp.png(p, "w2fb_f30.png")

    s0, s1, s2, s3 = snaps
    d1 = s1 - s0
    d2 = s2 - s1
    d3 = s3 - s2
    # falling candidate (measured from screen: bombs move +40..50 y
    # over 30f -> |d| ~13-17 per 10f window; x drifts -3..-5): accept
    # |d| in 2..40 with SAME SIGN on every consecutive pair
    same_sign = (np.sign(d1) == np.sign(d2)) & (np.sign(d2) == np.sign(d3))
    mag = (np.abs(d1) >= 2) & (np.abs(d1) <= 40) & \
          (np.abs(d2) >= 2) & (np.abs(d2) <= 40) & \
          (np.abs(d3) >= 2) & (np.abs(d3) <= 40)
    cand = np.flatnonzero(same_sign & mag)
    rows = []
    for i in cand:
        addr = LO + int(i) * 2
        rows.append({
            "addr": hex(addr),
            "in_table_slot": (addr - TABLE) // STRIDE
            if TABLE <= addr < TABLE + 40 * STRIDE else None,
            "table_off": (addr - TABLE) % STRIDE
            if TABLE <= addr < TABLE + 40 * STRIDE else None,
            "vals": [int(s0[i]), int(s1[i]), int(s2[i]), int(s3[i])],
        })
    gp.log(f"falling-motion candidates: {len(rows)}")
    for r in rows[:60]:
        gp.log("  ", json.dumps(r))

    # also: ANY changed word in the zone (coarse map, first/last only)
    changed = np.flatnonzero(s3 != s0)
    gp.log(f"changed words over 30f in [0x{LO:X},0x{HI:X}): {len(changed)}")
    # cluster by 0x100 region
    clusters = {}
    for i in changed:
        clusters[hex((LO + i * 2) >> 8 << 8)] = \
            clusters.get(hex((LO + i * 2) >> 8 << 8), 0) + 1
    top = sorted(clusters.items(), key=lambda kv: -kv[1])[:20]
    gp.log("top changed clusters: " + json.dumps(top))

    json.dump({"falling": rows,
               "clusters": top},
              open(os.path.join(EVID, "w2_find_bombs.json"), "w"),
              indent=1)
    gp.unfreeze(session, "w2_findbombs")
    gp.log("saved w2_find_bombs.json")


if __name__ == "__main__":
    main()
