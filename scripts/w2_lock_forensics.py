#!/usr/bin/env python3
"""w2_lock_forensics.py — the SECOND gate condition at 1164px/prog139.

From `arena2`: kill the mosque (proven 3x), INSTANT traverse right
(proven survivable), then AT THE LOCK:
  * dump all 40 slots (X, hp, h, a0, a4) every 50f x 6 samples
  * PNGs every 100f
  * then one-factor weapon arms from the lock state (savestate `lock`):
      idle / vulcan UP+Y / vulcan RIGHT+Y / grenade LEFT / grenade RIGHT
      each 400f, watching every alive slot's HP + prog + score
The immune-slot question (historical 14/17/18/5) gets a direct answer
in THIS state.
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


def dump_slots(m):
    d = {}
    for s in range(40):
        w = slot_words(m, s)
        if w[71] or w[63]:
            d[s] = {"X": round(xfix(w), 1), "hp": w[71], "h": w[63],
                    "a0": w[80], "a4": w[82]}
    return d


def main():
    t0 = time.time()
    p, fw = gp.boot()
    m = p.mem
    p.load_state("arena2")
    session = gp.freeze_now(p, "w2_lock")
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()
    frame = 0

    # ---- kill the mosque (proven recipe) ----
    for _ in range(10):
        p.core.set_buttons({"LEFT"})
        p.core.run_frame()
        session.gs.tick()
        frame += 1
    for _ in range(240):
        t = xfix(slot_words(m, 0))
        if 22.0 <= t <= 28.0:
            break
        p.core.set_buttons({"LEFT"} if t > 28.0 else {"RIGHT"})
        p.core.run_frame()
        session.gs.tick()
        frame += 1
    score0 = m.u16(gp.A_SCORE)
    for k in range(45 * 80):
        cyc = k % 80
        btns = {"A"} if cyc < 8 else ({"LEFT"} if cyc < 24 else set())
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
        frame += 1
        if k % 80 == 8 and (m.u16(gp.A_SCORE) - score0) & 0xFF == 32:
            gp.log(f"f{frame}: mosque down (+800)")
            break
    # ---- instant traverse right ----
    stall = 0
    last_x = None
    hop_until = -1
    for k in range(700):
        w0 = slot_words(m, 0)
        ptile = xfix(w0)
        btns = {"RIGHT", "B"} if k < hop_until else {"RIGHT"}
        if last_x is not None and abs(ptile - last_x) < 0.01:
            stall += 1
        else:
            stall = 0
        if stall >= 45 and k >= hop_until:
            hop_until = k + 18
            stall = 0
        last_x = ptile
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
        frame += 1
        if abs(ptile - 1164.0) < 3 and m.u16(gp.A_PROGRESS) == 139:
            break
    gp.log(f"f{frame}: at lock tile={xfix(slot_words(m, 0)):.1f} "
           f"prog={m.u16(gp.A_PROGRESS)}")
    p.save_state("lock")
    gp.png(p, "w2lf_lock.png")

    # ---- 6 slot dumps x 50f ----
    dumps = []
    for i in range(6):
        dumps.append({"f": frame + i * 50, "slots": dump_slots(m),
                      "prog": m.u16(gp.A_PROGRESS),
                      "score": m.u16(gp.A_SCORE),
                      "churn": idle_churn(p, 20)})
        for _ in range(50):
            p.core.set_buttons(set())
            p.core.run_frame()
            session.gs.tick()
            frame += 1
    gp.png(p, "w2lf_after_dumps.png")
    for d in dumps:
        gp.log(f"dump f{d['f']}: prog={d['prog']} churn={d['churn']} "
               f"slots={json.dumps(d['slots'])}")

    # ---- weapon arms from `lock` ----
    arms = {"idle": set(), "upy": {"UP", "Y"}, "rgun": {"RIGHT", "Y"},
            "grenL": None, "grenR": None}
    results = {}
    for name, btns in arms.items():
        p.load_state("lock")
        session = gp.freeze_now(p, f"w2_lock_{name}")
        for _ in range(2):
            p.core.run_frame()
            session.gs.tick()
        before = dump_slots(m)
        sc0 = m.u16(gp.A_SCORE)
        for k in range(400):
            if name == "grenL":
                cyc = k % 80
                b = {"A"} if cyc < 8 else ({"LEFT"} if cyc < 24 else set())
            elif name == "grenR":
                cyc = k % 80
                b = {"A"} if cyc < 8 else ({"RIGHT"} if cyc < 24 else set())
            else:
                b = btns
            p.core.set_buttons(b)
            p.core.run_frame()
            session.gs.tick()
            frame += 1
        after = dump_slots(m)
        sc1 = m.u16(gp.A_SCORE)
        deltas = {}
        for s in set(before) | set(after):
            h0 = before.get(s, {}).get("hp", 0)
            h1 = after.get(s, {}).get("hp", 0)
            if h0 != h1:
                deltas[s] = (h0, h1)
        results[name] = {"score": [sc0, sc1], "hp_deltas": deltas,
                         "prog": m.u16(gp.A_PROGRESS),
                         "tile": xfix(slot_words(m, 0))}
        gp.log(f"arm {name}: score {sc0}->{sc1} prog="
               f"{results[name]['prog']} tile="
               f"{results[name]['tile']:.1f} deltas={deltas}")
        gp.png(p, f"w2lf_arm_{name}.png")
    json.dump({"dumps": dumps, "arms": results,
               "wall_s": round(time.time() - t0, 1)},
              open(os.path.join(EVID, "w2_lock_forensics.json"), "w"),
              indent=1)
    gp.log("saved w2_lock_forensics.json")


if __name__ == "__main__":
    main()
