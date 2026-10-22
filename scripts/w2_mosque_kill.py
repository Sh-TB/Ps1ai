#!/usr/bin/env python3
"""w2_mosque_kill.py — destroy the mosque, then measure the RAIN with
the CORRECT signature (bomb fallers = slots whose 0x7E word falls),
not churn (churn counts fire/rubble effects too — the previous
session's 'rain never stopped' verdict is suspect because of that).

Protocol from `arena2` (freeze on):
  BASE  200f idle: log bomb-faller spawns (expect 914.8 saturation)
  KILL  dismount 20f LEFT -> grenade lobs LEFT (A, period 80f, the
        proven mosque_grenade pattern); watch slot6 (X~776px = the
        mosque) HP word + score (+800 expected) + PNGs
  POST  800f: does the 914.8 rain stop? does the truck move? does
        prog unlock? does the player walk right past 37.5?
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
PX_PER_TILE = 24.39


def slot_words(m, s):
    base = TABLE + s * STRIDE
    return m.ram[base:base + STRIDE].view("<u2").astype(np.int32).tolist()


def xfix(w):
    return ((int(w[61]) << 16) | int(w[60])) / 65536.0


class RainLogger:
    """Bomb fallers = alive slots with 0x7E > 64 that DECREASE."""
    def __init__(self, m):
        self.m = m
        self.prev = {s: slot_words(m, s) for s in range(40)}

    def poll(self, frame, tag, ppx=None):
        evs = []
        for s in range(1, 40):
            w = slot_words(self.m, s)
            h, hp = w[63], w[71]
            ph = self.prev[s][63]
            if hp and 0 < ph - h <= 20 and h > 60 and ph > 70:
                evs.append({"tag": tag, "f": frame, "slot": s,
                            "X": xfix(w), "h": h, "hp": hp})
            self.prev[s] = w
        return evs


def main(base_f=200, kill_f=900, post_f=800):
    t0 = time.time()
    p, fw = gp.boot()
    m = p.mem
    p.load_state("arena2")
    session = gp.freeze_now(p, "w2_mosquekill")
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()

    rain = RainLogger(m)
    out = open(os.path.join(EVID, "w2_mosque_kill.jsonl"), "w")
    score0 = m.u16(gp.A_SCORE)
    s6_hp0 = slot_words(m, 6)[71]
    gp.log(f"baseline: score={score0} slot6_hp={s6_hp0} "
           f"slot6_X={xfix(slot_words(m, 6)):.1f}")

    frame = 0
    # ---- BASE: idle 200f ----
    for _ in range(base_f):
        p.core.set_buttons(set())
        p.core.run_frame()
        session.gs.tick()
        for e in rain.poll(frame, "BASE"):
            out.write(json.dumps(e) + "\n")
        frame += 1
    gp.png(p, "w2mk_base_end.png")

    # ---- KILL: dismount + grenade lobs toward the mosque (LEFT) ----
    for _ in range(20):
        p.core.set_buttons({"LEFT"})
        p.core.run_frame()
        session.gs.tick()
        frame += 1
    w0 = slot_words(m, 0)
    gp.log(f"dismounted to tile {xfix(w0):.1f}")
    grenade_frames = 0
    s6_hist = []
    for k in range(kill_f):
        cyc = k % 80
        btns = {"A"} if cyc < 8 else ({"LEFT"} if cyc < 24 else set())
        if cyc < 8:
            grenade_frames += 1
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
        for e in rain.poll(frame, "KILL"):
            out.write(json.dumps(e) + "\n")
        frame += 1
        if k % 40 == 0:
            w6 = slot_words(m, 6)
            sc = m.u16(gp.A_SCORE)
            s6_hist.append({"f": frame, "s6_hp": w6[71],
                            "s6_X": xfix(w6), "score": sc})
            if len(s6_hist) >= 2 and s6_hist[-1]["score"] != \
                    s6_hist[-2]["score"]:
                gp.log(f"f{frame}: score {s6_hist[-2]['score']}->"
                       f"{s6_hist[-1]['score']} s6_hp={w6[71]}")
        if k % 150 == 0:
            gp.png(p, f"w2mk_kill_f{frame:05d}.png")
            w6 = slot_words(m, 6)
            gp.log(f"f{frame} kill-phase: s6_hp={w6[71]} "
                   f"s6_X={xfix(w6):.1f} score={m.u16(gp.A_SCORE)} "
                   f"grenades={grenade_frames}")
    gp.png(p, "w2mk_kill_end.png")
    score1 = m.u16(gp.A_SCORE)
    s6_hp1 = slot_words(m, 6)[71]
    gp.log(f"after kill phase: score {score0}->{score1} "
           f"slot6_hp {s6_hp0}->{s6_hp1}")

    # ---- POST: 800f — rain stopped? truck moves? camera unlocks? ----
    # walk right with hop anti-stall (the cross4 control law)
    stall = 0
    last_x = None
    hop_until = -1
    max_tile = 0.0
    for k in range(post_f):
        w0 = slot_words(m, 0)
        ptile = xfix(w0)
        btns = {"RIGHT", "B"} if k < hop_until else {"RIGHT"}
        if abs(ptile - (last_x if last_x is not None else -1)) < 0.01:
            stall += 1
        else:
            stall = 0
            max_tile = max(max_tile, ptile)
        last_x = ptile
        if stall >= 45 and k >= hop_until:
            hop_until = k + 18
            stall = 0
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
        for e in rain.poll(frame, "POST"):
            out.write(json.dumps(e) + "\n")
        frame += 1
        if k % 200 == 0:
            gp.png(p, f"w2mk_post_f{frame:05d}.png")
            gp.log(f"f{frame} post: tile={ptile:.1f} "
                   f"prog={m.u16(gp.A_PROGRESS)} "
                   f"maxTile={max_tile:.1f} "
                   f"score={m.u16(gp.A_SCORE)}")
    out.close()
    gp.unfreeze(session, "w2_mosquekill")
    gp.png(p, "w2mk_end.png")
    json.dump({"s6_hist": s6_hist, "grenade_frames": grenade_frames,
               "max_tile": max_tile,
               "wall_s": round(time.time() - t0, 1)},
              open(os.path.join(EVID, "w2_mosque_kill.json"), "w"),
              indent=1)
    gp.log("done")


if __name__ == "__main__":
    main()
