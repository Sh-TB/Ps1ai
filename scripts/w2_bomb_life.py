#!/usr/bin/env python3
"""w2_bomb_life.py — full life-cycle of ONE falling bomb, all words.

From `arena2`: freeze, then every frame for 420 frames dump ALL u16
words of the slots that showed falling motion (12/25 pool) — plus a
light scan of all 40 slots to catch whichever slots carry the fallers
this run. Output: JSONL keyed (frame, slot) -> 166 words.

Post-processing (offline) finds:
  * the X word (small |delta|, drifts while 0x7E falls fast)
  * the spawn X (origin) per bomb  -> rain-source answer
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

EVID = gp.EVID
TABLE, STRIDE, HP_OFF = gp.TABLE, gp.STRIDE, gp.HP_OFF
NW = STRIDE // 2                                 # 166 u16 words


def words(m, slot):
    base = TABLE + slot * STRIDE
    return m.ram[base:base + STRIDE].view("<u2").astype(np.int32).tolist()


def main(frames=420):
    t0 = time.time()
    p, fw = gp.boot()
    m = p.mem
    p.load_state("arena2")
    session = gp.freeze_now(p, "w2_bomblife")
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()

    # discover faller slots live: track the 0x7E word across slots
    fallers = set()
    prev = {s: words(m, s) for s in range(40)}
    out = open(os.path.join(EVID, "w2_bomb_life.jsonl"), "w")
    for f in range(frames):
        cur = {}
        for s in range(40):
            w = words(m, s)
            cur[s] = w
            if s in prev:
                d = w[63] - prev[s][63]          # word 63 = off 0x7E
                if abs(d) >= 3 and prev[s][63] > 20:
                    fallers.add(s)
            if s in fallers or s in (0,):
                out.write(json.dumps({
                    "f": f, "slot": s, "w": w}) + "\n")
        prev = cur
        p.core.set_buttons(set())
        p.core.run_frame()
        session.gs.tick()
        if f % 100 == 0:
            gp.png(p, f"w2bl_f{f:04d}.png")
            gp.log(f"f{f} fallers={sorted(fallers)}")
    out.close()
    gp.unfreeze(session, "w2_bomblife")
    gp.png(p, "w2bl_end.png")
    json.dump({"frames": frames, "faller_slots": sorted(fallers),
               "wall_s": round(time.time() - t0, 1)},
              open(os.path.join(EVID, "w2_bomb_life.json"), "w"), indent=1)
    gp.log("done, fallers:", sorted(fallers))


if __name__ == "__main__":
    main()
