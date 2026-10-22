#!/usr/bin/env python3
"""w2_grenade_assault.py — the lock assault WITH grenades.

All previous lock arms had an EMPTY grenade stock (the mosque volley
spent it). This run:
  1. arena2 -> kill the mosque with the MINIMUM volley (stop at the
     first +32) -> traverse right to the clamp -> save `lock2`
     (grenade stock u8@0xEDCF4 recorded!)
  2. arms from `lock2` (fresh each):
     a  lob LEFT 600f    (the soldier/truck at ~1126)
     b  jumpshot LEFT    (B then UP-LEFT+Y at the soldier's height)
     c  bedwalk          (jump onto the truck top from the left, then
                          LEFT+Y point-blank along the bed)
     d  lob UP           (the chopper at top-left)
  watch: grenade stock, score, ALL slot hp deltas, the player's TRUE x
  (u32 bytes), the camera u32, max_x (limit lift = >1200), PNGs.
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
A_GRENS = 0x0EDCF4


def cam(m):
    return int.from_bytes(m.ram[0x0CA2E0:0x0CA2E4].tobytes(),
                          "little") / 65536.0


def px(m):
    return int.from_bytes(m.ram[TABLE + 0x78:TABLE + 0x7C].tobytes(),
                          "little") / 65536.0


def hgt(m):
    return int.from_bytes(m.ram[TABLE + 0x7E:TABLE + 0x80].tobytes(),
                          "little")


def slots(m):
    d = {}
    for s in range(40):
        base = TABLE + s * STRIDE
        hp = int.from_bytes(m.ram[base + 0x8E:base + 0x90].tobytes(),
                            "little")
        if hp:
            d[s] = hp
    return d


def reach_lock(p, m, session, frame0=0):
    frame = frame0
    for _ in range(10):
        p.core.set_buttons({"LEFT"})
        p.core.run_frame()
        session.gs.tick()
        frame += 1
    for _ in range(240):
        x = px(m)
        if 22.0 <= x <= 28.0:
            break
        p.core.set_buttons({"LEFT"} if x > 28.0 else {"RIGHT"})
        p.core.run_frame()
        session.gs.tick()
        frame += 1
    score0 = int.from_bytes(m.ram[0x0EE318:0x0EE31A].tobytes(), "little")
    for k in range(45 * 80):
        cyc = k % 80
        btns = {"A"} if cyc < 8 else ({"LEFT"} if cyc < 24 else set())
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
        frame += 1
        if k % 80 == 8:
            sc = int.from_bytes(m.ram[0x0EE318:0x0EE31A].tobytes(),
                                "little")
            if (sc - score0) & 0xFF == 32:
                gp.log(f"f{frame}: mosque down (+800), grenades left "
                       f"={m.ram[A_GRENS]}")
                break
    stall = 0
    last_x = None
    hop_until = -1
    for k in range(700):
        x = px(m)
        btns = {"RIGHT", "B"} if k < hop_until else {"RIGHT"}
        if last_x is not None and abs(x - last_x) < 0.5:
            stall += 1
        else:
            stall = 0
        if stall >= 45 and k >= hop_until:
            hop_until = k + 18
            stall = 0
        last_x = x
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
        frame += 1
        if abs(x - 1164.0) < 4:
            break
    return frame


def main():
    p, fw = gp.boot()
    m = p.mem
    p.load_state("arena2")
    session = gp.freeze_now(p, "w2ga_reach")
    frame = reach_lock(p, m, session)
    gp.log(f"lock2 reached at f{frame}: x={px(m):.1f} cam={cam(m):.1f} "
           f"grenades={m.ram[A_GRENS]}")
    p.save_state("lock2")
    gp.png(p, "w2ga_lock2.png")

    arms = {
        "lobL": lambda k: ({"A"} if k % 80 < 8 else
                           ({"LEFT"} if k % 80 < 24 else set())),
        "jumpshot": lambda k: ({"B", "LEFT"} if k % 60 < 16 else
                               ({"LEFT", "Y"} if k % 60 < 40 else set())),
        "bedwalk": lambda k: ({"B", "RIGHT"} if k % 90 < 16 else
                              ({"LEFT", "Y"} if k % 90 < 50 else set())),
        "lobUp": lambda k: ({"A", "UP"} if k % 80 < 8 else set()),
    }
    results = {}
    for name, ctrl in arms.items():
        p.load_state("lock2")
        session = gp.freeze_now(p, f"w2ga_{name}")
        for _ in range(2):
            p.core.run_frame()
            session.gs.tick()
        s0 = slots(m)
        sc0 = int.from_bytes(m.ram[0x0EE318:0x0EE31A].tobytes(), "little")
        g0 = int(m.ram[A_GRENS])
        max_x = px(m)
        for k in range(600):
            p.core.set_buttons(ctrl(k))
            p.core.run_frame()
            session.gs.tick()
            max_x = max(max_x, px(m))
            if k % 200 == 0:
                gp.png(p, f"w2ga_{name}_f{k:03d}.png")
        s1 = slots(m)
        sc1 = int.from_bytes(m.ram[0x0EE318:0x0EE31A].tobytes(), "little")
        deltas = {s: (s0.get(s, 0), s1.get(s, 0))
                  for s in set(s0) | set(s1) if s0.get(s, 0) != s1.get(s, 0)}
        results[name] = {"score": [sc0, sc1], "grenades": [g0,
                         int(m.ram[A_GRENS])], "deltas": deltas,
                         "max_x": round(max_x, 1), "cam": round(cam(m), 1),
                         "limit_lifted": max_x > 1200}
        gp.png(p, f"w2ga_{name}_end.png")
        r = results[name]
        gp.log(f"arm {name}: score {r['score']} grens {r['grenades']} "
               f"max_x={r['max_x']} cam={r['cam']} "
               f"lifted={r['limit_lifted']}")
        gp.log(f"   deltas: {deltas}")
    gp.unfreeze(session, "w2ga")
    json.dump(results, open(os.path.join(EVID, "w2_grenade_assault.json"),
                            "w"), indent=1)
    gp.log("saved w2_grenade_assault.json")


if __name__ == "__main__":
    main()
