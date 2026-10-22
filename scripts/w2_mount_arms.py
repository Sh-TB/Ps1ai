#!/usr/bin/env python3
"""w2_mount_arms.py — at the `lock` state (player at 1164px INSIDE the
parked truck's span, truck slot5 alive at 1126.5, prog locked 139):

  arms x 300f each, fresh from `lock`:
    up       hold UP            (mount / enter vehicle?)
    jumpspam B every 40f        (clear the truck by hopping)
    down     hold DOWN          (crouch passthrough?)
    upjump   UP+B alternating   (mount + hop)
    walk     RIGHT only         (control — known stall)

  watch: slot5 X+hp (the truck), prog, slot0 X, score, churn.
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
TABLE, STRIDE = gp.TABLE, gp.STRIDE


def slot_words(m, s):
    base = TABLE + s * STRIDE
    return m.ram[base:base + STRIDE].view("<u2").astype(np.int32).tolist()


def xfix(w):
    return ((int(w[61]) << 16) | int(w[60])) / 65536.0


ARMS = {
    "up": lambda k: {"UP"},
    "jumpspam": lambda k: {"B"} if k % 40 < 14 else {"RIGHT"},
    "down": lambda k: {"DOWN"},
    "upjump": lambda k: ({"UP", "B"} if k % 60 < 20 else
                         ({"UP"} if k % 60 < 40 else {"RIGHT", "B"})),
    "walk": lambda k: {"RIGHT"},
}


def main():
    t0 = time.time()
    p, fw = gp.boot()
    m = p.mem
    results = {}
    frame = 0
    for name, ctrl in ARMS.items():
        p.load_state("lock")
        session = gp.freeze_now(p, f"w2m_{name}")
        for _ in range(2):
            p.core.run_frame()
            session.gs.tick()
        s5_0 = slot_words(m, 5)
        sc0 = m.u16(gp.A_SCORE)
        for k in range(300):
            p.core.set_buttons(ctrl(k))
            p.core.run_frame()
            session.gs.tick()
            frame += 1
        s5_1 = slot_words(m, 5)
        results[name] = {
            "prog": m.u16(gp.A_PROGRESS),
            "pX": xfix(slot_words(m, 0)),
            "truckX0": xfix(s5_0), "truckX1": xfix(s5_1),
            "truckHP": s5_1[71],
            "score": [sc0, m.u16(gp.A_SCORE)],
            "churn": idle_churn(p, 20),
        }
        gp.png(p, f"w2m_{name}.png")
        r = results[name]
        gp.log(f"arm {name:8s}: prog={r['prog']} pX={r['pX']:.1f} "
               f"truck {r['truckX0']:.1f}->{r['truckX1']:.1f} "
               f"(hp={r['truckHP']}) score={r['score']} "
               f"churn={r['churn']}")
    gp.unfreeze(session, "w2m")
    json.dump(results, open(os.path.join(EVID, "w2_mount_arms.json"),
                            "w"), indent=1)
    gp.log("saved w2_mount_arms.json")


if __name__ == "__main__":
    main()
