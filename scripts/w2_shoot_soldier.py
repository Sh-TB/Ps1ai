#!/usr/bin/env python3
"""w2_shoot_soldier.py — the untried arm: LEFT+Y (horizontal fire at
the soldier standing on the parked truck at ~1126-1140) from `lock`.

Arms (fresh from `lock` each):
  lgun   LEFT+Y 600f   (close in + shoot the soldier)
  lgun2  LEFT+Y 900f   (longer, if the first is slow)
Watch: ALL slots' hp deltas (find the soldier's slot + death), score,
prog, pX. Success = a kill (+score) and/or prog != 139.
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
TABLE, STRIDE = gp.TABLE, gp.STRIDE


def slot_words(m, s):
    base = TABLE + s * STRIDE
    return m.ram[base:base + STRIDE].view("<u2").astype(np.int32).tolist()


def xfix(w):
    return ((int(w[61]) << 16) | int(w[60])) / 65536.0


def dump(m):
    return {s: {"X": round(xfix(slot_words(m, s)), 1),
                "hp": slot_words(m, s)[71], "h": slot_words(m, s)[63]}
            for s in range(40) if slot_words(m, s)[71]}


def main():
    p, fw = gp.boot()
    m = p.mem
    results = {}
    frame = 0
    for name, frames in (("lgun", 600), ("lgun2", 900)):
        p.load_state("lock")
        session = gp.freeze_now(p, f"w2ss_{name}")
        for _ in range(2):
            p.core.run_frame()
            session.gs.tick()
        before = dump(m)
        sc0 = m.u16(gp.A_SCORE)
        for k in range(frames):
            p.core.set_buttons({"LEFT", "Y"})
            p.core.run_frame()
            session.gs.tick()
            frame += 1
            if k % 300 == 0:
                gp.png(p, f"w2ss_{name}_f{k:04d}.png")
                gp.log(f"{name} f{k}: pX={xfix(slot_words(m, 0)):.1f} "
                       f"prog={m.u16(gp.A_PROGRESS)} "
                       f"score={m.u16(gp.A_SCORE)}")
        after = dump(m)
        deltas = {}
        for s in set(before) | set(after):
            h0 = before.get(s, {}).get("hp", 0)
            h1 = after.get(s, {}).get("hp", 0)
            if h0 != h1:
                deltas[s] = (h0, h1)
        results[name] = {"score": [sc0, m.u16(gp.A_SCORE)],
                         "prog": m.u16(gp.A_PROGRESS),
                         "pX": xfix(slot_words(m, 0)),
                         "deltas": deltas,
                         "after": after}
        gp.png(p, f"w2ss_{name}_end.png")
        gp.log(f"arm {name}: score {sc0}->{m.u16(gp.A_SCORE)} "
               f"prog={results[name]['prog']} "
               f"pX={results[name]['pX']:.1f}")
        gp.log(f"   deltas: {deltas}")
        gp.log(f"   after: {json.dumps(after)}")
    gp.unfreeze(session, "w2ss")
    json.dump(results, open(os.path.join(EVID, "w2_shoot_soldier.json"),
                            "w"), indent=1)
    gp.log("saved w2_shoot_soldier.json")


if __name__ == "__main__":
    main()
