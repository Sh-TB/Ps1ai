#!/usr/bin/env python3
"""w2_chopper_hp.py — find the CHOPPER's HP in the OVERLAY data arrays.

Context: at the lock (1164px/prog139, rain resumed at 915-984) the
twin-rotor hovers at screen top-LEFT == world ~920-970 == exactly the
resumed rain zone. Historical arms scanned only the 0x14C table (zero
deltas) — the chopper's HP was never looked for OUTSIDE it.

Protocol from `lock`:
  A  120f idle            -> reference dumps
  B  500f UP+LEFT+Y sustained (bullets INTO the chopper)
  C  diff 0xC8000..0xE0000 between A-end and B-end:
       words that DECREASED monotonically-ish by 1..200 = HP candidates
  D  re-arm 500f UP+LEFT+Y: do candidates keep decreasing? -> HP word
  E  if a candidate hits ~0 / a big change: prog unlocked? PNGs.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import msx_gate_probe as gp                     # noqa: E402
from mission import idle_churn                  # noqa: E402

EVID = gp.EVID
LO, HI = 0x0C8000, 0x0E0000


def snap():
    return gp.p_mem_snapshot() if hasattr(gp, "p_mem_snapshot") else None


def u16_view(m):
    return m.ram[LO:HI].view("<u2").astype(np.int32)


def main():
    t0 = time.time()
    p, fw = gp.boot()
    m = p.mem
    p.load_state("lock")
    session = gp.freeze_now(p, "w2_chopper")
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()
    frame = 0

    # ---- A: idle reference ----
    for _ in range(120):
        p.core.set_buttons(set())
        p.core.run_frame()
        session.gs.tick()
        frame += 1
    sA = u16_view(m).copy()
    gp.png(p, "w2ch_before.png")
    gp.log(f"f{frame}: reference taken. prog={m.u16(gp.A_PROGRESS)}")

    # ---- B: fire UP+LEFT+Y into the chopper ----
    for _ in range(500):
        p.core.set_buttons({"UP", "LEFT", "Y"})
        p.core.run_frame()
        session.gs.tick()
        frame += 1
    sB = u16_view(m)
    gp.png(p, "w2ch_afterfire.png")
    gp.log(f"f{frame}: fired. prog={m.u16(gp.A_PROGRESS)} "
           f"score={m.u16(gp.A_SCORE)}")

    # ---- C: diff ----
    d = sB - sA
    # HP candidates: decreased by 1..200 total, i.e. sB < sA, delta small
    cand = np.flatnonzero((d <= -1) & (d >= -200))
    rows = []
    for i in cand:
        addr = LO + int(i) * 2
        rows.append({"addr": hex(addr),
                     "valA": int(sA[i]), "valB": int(sB[i]),
                     "delta": int(d[i])})
    gp.log(f"HP candidates (decreased 1..200): {len(rows)}")
    for r in rows[:40]:
        gp.log("  ", json.dumps(r))

    # keep firing and see which candidates CONTINUE to decrease
    sB0 = sB.copy()
    for _ in range(500):
        p.core.set_buttons({"UP", "LEFT", "Y"})
        p.core.run_frame()
        session.gs.tick()
        frame += 1
    sC = u16_view(m)
    d2 = sC - sB0
    cont = []
    for r in rows:
        i = (int(r["addr"], 16) - LO) // 2
        if d2[i] <= -1:
            cont.append({"addr": r["addr"], "valA": r["valA"],
                         "valB": r["valB"], "valC": int(sC[i]),
                         "d1": r["delta"], "d2": int(d2[i])})
    gp.log(f"CONTINUING decrements: {len(cont)}")
    for r in cont[:25]:
        gp.log("  ", json.dumps(r))
    gp.png(p, "w2ch_afterfire2.png")

    json.dump({"cands": rows, "continuing": cont,
               "prog": m.u16(gp.A_PROGRESS),
               "score": m.u16(gp.A_SCORE),
               "wall_s": round(time.time() - t0, 1)},
              open(os.path.join(EVID, "w2_chopper_hp.json"), "w"),
              indent=1)
    gp.unfreeze(session, "w2_chopper")
    gp.log("saved w2_chopper_hp.json")


if __name__ == "__main__":
    main()
