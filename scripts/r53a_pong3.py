#!/usr/bin/env python3
"""r53a_pong3.py — Stage A v3: (1) live input->paddle check; (2)
deliberate-miss point protocol for score-word verification (two good
paddles = no points, so the teacher INTENTIONALLY steps away on arrival
windows); (3) final anchor verification."""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    sys.path.insert(0, _p)

from ps1play.learn.games import PongEnv                     # noqa: E402
from ps1play.learn.perception import (pong_ball_centroid,   # noqa: E402
                                      pong_paddle_rows)
from ps1play.learn.teacher import PongTeacher               # noqa: E402
from hellopong_r12_lib import make_jrn, save_png            # noqa: E402

OUT = os.path.join(REPO, "scratch", "r53learn")
BALL_X, BALL_Y = 0x1FFEA0, 0x1FFEA4


def snap(env):
    fr = env.frame()
    return fr, env.p.core.ram.copy()


def ball_truth(ram):
    ix = int(np.frombuffer(ram[BALL_X:BALL_X + 4].tobytes(), "<i4")[0])
    iy = int(np.frombuffer(ram[BALL_Y:BALL_Y + 4].tobytes(), "<i4")[0])
    return ix, iy


def main():
    jr = make_jrn(OUT, "[pongA3]")
    env = PongEnv()
    env.p.core.set_port_device(0, port=1)
    env.settle()
    report = {}

    # ---- 1) input -> paddle movement check (vision + RAM) ----
    fr0, r0 = snap(env)
    y0 = pong_paddle_rows(fr0)[0]
    env.run(15, {"UP"})
    fr1, r1 = snap(env)
    y1 = pong_paddle_rows(fr1)[0]
    d_ram = (r1.view("<i2").astype(int)
             - r0.view("<i2").astype(int))
    movers = np.nonzero(np.abs(d_ram) == 60)[0]     # 4 px/f x 15f
    report["input_check"] = {
        "vision_row_0": y0, "vision_row_1": y1, "moved": (y1 != y0),
        "ram_movers_i2x60": [hex(o * 2) for o in movers[:8]]}
    jr({"ev": "input_check", **report["input_check"]})
    save_png(OUT, fr1, "pong_input_up.png")

    # ---- 2) deliberate-miss point protocol ----
    teacher = PongTeacher(deadband=10.0)
    base_u16 = 0x1FFEB4 // 2
    prev = None
    plus1 = {}
    l_series, r_read = [], []
    miss_mode = True
    for i in range(1400):
        fr, ram = snap(env)
        ix, iy = ball_truth(ram)
        cx, cy, _n = pong_ball_centroid(fr)
        lp, _rp = pong_paddle_rows(fr)
        # deliberate miss: park the paddle FAR from the ball when the
        # ball approaches the left column; otherwise track (AI scores)
        if miss_mode and cx is not None and cx < 120:
            target = 0 if iy > 120 else 239
            act = "UP" if target < (lp or 120) else "DOWN"
        else:
            act = teacher.act((cx, cy), lp)
        env.run(2, {"UP": {"UP"}, "DOWN": {"DOWN"},
                    "NONE": set()}.get(act, set()))
        v = env.p.core.ram.view("<u2").astype(int)
        if prev is not None:
            d = v - prev
            for off in np.nonzero(d == 1)[0]:
                plus1[off] = plus1.get(off, 0) + 1
        prev = v
        l_series.append(int(v[base_u16]))
        r_read.append(int(v[base_u16 + 1]))
        # stop after 3+ left points or game end
        if len(l_series) > 8 and (max(l_series) >= 3
                                  or max(r_read) >= 5):
            break
    l_ok = max(l_series) >= 1
    co = sorted(off for off, n in plus1.items()
                if n >= 1 and abs(off * 2 - 0x1FFEB4) <= 64)
    report["scores"] = {
        "score_l": hex(0x1FFEB4), "l_ok": l_ok,
        "l_max": max(l_series), "l_series": l_series[:40],
        "r_neighbor_max": max(r_read),
        "score_r_cands": [hex(o * 2) for o in co],
        "plus1_near": {hex(o * 2): n for o, n in plus1.items()
                       if abs(o * 2 - 0x1FFEB4) <= 64}}
    jr({"ev": "scores", **{k: v for k, v in report["scores"].items()
                           if k != "l_series"}})

    env.close()
    with open(os.path.join(OUT, "pong_stage_a3.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
