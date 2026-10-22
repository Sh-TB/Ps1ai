#!/usr/bin/env python3
"""w2_unstick.py — the player at `lock` is a statue (frozen HP=35 mid
kill-sequence?). Diff slot0(lock) vs slot0(arena2-walking), then try:
  arm A  force pair = 144/143 (write-codes, per-frame) -> 250f
  arm B  no freeze at all -> 250f (does he die or revive?)
  arm C  pair@144 + poke slot0 state words (top deltas) -> 250f
Metric: does slot0 X move off 1164? does prog move?
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
from ps1play.agent.cheatprof import CheatSession, CHEAT_ASSISTED  # noqa
from ps1play.agent.gameshark import GSCode      # noqa: E402

EVID = gp.EVID
TABLE, STRIDE = gp.TABLE, gp.STRIDE


def slot_words(m, s):
    base = TABLE + s * STRIDE
    return m.ram[base:base + STRIDE].view("<u2").astype(np.int32).tolist()


def xfix(w):
    return ((int(w[61]) << 16) | int(w[60])) / 65536.0


def pair_session(p, tag, v0=0x90, v1=0x8F):
    """CheatSession forcing the HP pair to (v0, v1) every frame."""
    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    session.enable(tag, [GSCode(f"8{gp.PAIR[0]:07X} {v0:04X}"),
                         GSCode(f"8{gp.PAIR[1]:07X} {v1:04X}")])
    return session


def main():
    p, fw = gp.boot()
    m = p.mem

    # ---- reference dumps ----
    p.load_state("lock")
    s_lock = slot_words(m, 0)
    p.load_state("arena2")
    s_arena = slot_words(m, 0)
    diffs = [(2 * i, int(a), int(b)) for i, (a, b) in
             enumerate(zip(s_arena, s_lock)) if a != b]
    gp.log(f"slot0 diffs arena2 vs lock: {len(diffs)}")
    for d in diffs[:30]:
        gp.log(f"   off={d[0]:#05x} arena={d[1]} lock={d[2]}")
    big = sorted(diffs, key=lambda d: -abs(d[1] - d[2]))[:8]

    results = {}
    frame = 0

    # ---- arm A: pair forced 144/143 ----
    p.load_state("lock")
    session = pair_session(p, "w2u_A")
    for _ in range(250):
        p.core.run_frame()
        session.gs.tick()
        frame += 1
    results["A_pair144"] = {"pX": xfix(slot_words(m, 0)),
                            "prog": m.u16(gp.A_PROGRESS),
                            "hp0": slot_words(m, 0)[71]}
    gp.png(p, "w2u_A.png")
    gp.log(f"arm A: {results['A_pair144']}")

    # ---- arm B: no freeze ----
    p.load_state("lock")
    for _ in range(250):
        p.core.run_frame()
        frame += 1
    results["B_nofreeze"] = {"pX": xfix(slot_words(m, 0)),
                             "prog": m.u16(gp.A_PROGRESS),
                             "hp0": slot_words(m, 0)[71]}
    gp.png(p, "w2u_B.png")
    gp.log(f"arm B: {results['B_nofreeze']}")

    # ---- arm C: pair@144 + poke the top-8 state words ----
    p.load_state("lock")
    session = pair_session(p, "w2u_C")
    for off, arena_v, lock_v in big:
        addr = TABLE + off
        try:
            m.ram[addr:addr + 2] = np.uint16(arena_v).tobytes()
        except Exception as e:                     # noqa: BLE001
            gp.log(f"poke {hex(addr)} failed: {e}")
    for _ in range(250):
        p.core.run_frame()
        session.gs.tick()
        frame += 1
    results["C_poke"] = {"pX": xfix(slot_words(m, 0)),
                         "prog": m.u16(gp.A_PROGRESS),
                         "hp0": slot_words(m, 0)[71]}
    gp.png(p, "w2u_C.png")
    gp.log(f"arm C: {results['C_poke']}")

    json.dump({"diffs": diffs, "results": results},
              open(os.path.join(EVID, "w2_unstick.json"), "w"), indent=1)
    gp.log("saved w2_unstick.json")


if __name__ == "__main__":
    main()
