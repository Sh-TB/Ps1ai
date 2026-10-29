#!/usr/bin/env python3
"""r53a_pong.py — Stage A (explore_assisted) for hello_pong.

Hunts the RAM truth anchors the teachers/datasets need:
  ball.x / ball.y / left-paddle.y / right-paddle.y / score_l / score_r

Method (all reads at REST — read frame+RAM without advancing frames so
they describe the same simulated instant):
  1. boot -> settle -> anchor (pong_anchor)
  2. BALL: 30 samples across natural drift; per sample, candidates =
     u16/i32 words equal to round(visual cx|cy) (±1); intersect over
     samples with MOVEMENT (candidates must track). Verify the winner
     by predicting 60 frames of vision from RAM.
  3. PADDLES: hold UP/DOWN; words moving exactly ±4 per frame with the
     input, stable range 0..180 -> left pad; same on port-1 UP/DOWN ->
     right pad.
  4. SCORES: diff u16 words across a natural point (left scores
     passively vs the static right paddle).
Evidence -> scratch/r53learn/pong_stage_a.json + events.jsonl
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.learn.games import PongEnv                # noqa: E402
from ps1play.learn.perception import (pong_ball_centroid,  # noqa: E402
                                      pong_paddle_rows)
from hellopong_r12_lib import make_jrn, save_png       # noqa: E402

OUT = os.path.join(REPO, "scratch", "r53learn")


def snap(p):
    """frame + ram at the SAME simulated instant (no run in between)."""
    fr = p.frame()
    ram = p.p.core.ram.copy()
    return fr, ram


def hunt_ball(env, jrn, samples=24):
    cands_x = None
    cands_y = None
    obs = []
    for i in range(samples):
        env.run(6, set())
        fr, ram = snap(env)
        cx, cy, n = pong_ball_centroid(fr)
        if cx is None:
            continue
        obs.append((cx, cy))
        ix = set(np.nonzero(
            np.abs(ram.view("<u2").astype(int) - int(round(cx))) <= 1)[0])
        iy = set(np.nonzero(
            np.abs(ram.view("<u2").astype(int) - int(round(cy))) <= 1)[0])
        cands_x = ix if cands_x is None else (cands_x & ix)
        cands_y = iy if cands_y is None else (cands_y & iy)
    jrn({"ev": "ball_cand_sizes", "x": len(cands_x or []),
         "y": len(cands_y or []), "samples": len(obs)})
    # disambiguate x vs y by byte-offset alignment: the Ball struct is
    # {x, y, vel_x, vel_y} — x at offset o, y at o+4 (i32) or o+2 (u16).
    hits = []
    for xo in sorted(cands_x or []):
        for stride in (2, 4):
            yo = xo + stride
            if yo in (cands_y or set()):
                hits.append((xo, yo, stride))
    # verify: predict vision from RAM across 40 fresh frames
    verified = []
    for xo, yo, stride in hits[:8]:
        err = 0.0
        cnt = 0
        for _ in range(40):
            env.run(3, set())
            fr, ram = snap(env)
            cx, cy, n = pong_ball_centroid(fr)
            if cx is None:
                continue
            rx = int(ram.view("<u2")[xo])
            ry = int(ram.view("<u2")[yo])
            err += abs(rx - cx) + abs(ry - cy)
            cnt += 1
        if cnt and err / cnt < 3.0:
            verified.append({"x_off_u16": xo, "y_off_u16": yo,
                             "stride": stride,
                             "mean_abs_err": round(err / cnt, 3)})
    return verified, len(obs)


def hunt_paddle(env, jrn, port):
    """Find the paddle-y word driven by port's UP/DOWN: two full
    cycles of (up 8f = -32, down 8f = +32); the word must move +32
    on BOTH cycles (source: Paddle.y is int, PADDLE_SPEED 4)."""
    def go(frames, btn):
        if port == 0:
            env.run(frames, btn, set())
        else:
            env.run(frames, set(), btn)
    go(8, {"UP"})
    _, ram2 = snap(env)
    go(8, {"DOWN"})
    _, ram3 = snap(env)
    go(8, {"UP"})
    go(8, {"DOWN"})
    _, ram4 = snap(env)
    d_a = (ram3.view("<i2").astype(int)
           - ram2.view("<i2").astype(int))
    d_b = (ram4.view("<i2").astype(int)
           - ram3.view("<i2").astype(int))
    cands = (set(np.nonzero(d_a == 32)[0].tolist())
             & set(np.nonzero(d_b == 32)[0].tolist()))
    return sorted(cands)[:12]


def verify_scores(env, jrn):
    """r14 recorded SCORE_L = 0x1FFEB4. Verify it tracks the left
    score across natural points and locate score_r by +1 co-moves in
    the neighbouring words."""
    base = 0x1FFEB4
    prev = None
    plus1_hist = {}
    t0 = time.time()
    seen_l = []
    while time.time() - t0 < 100:
        env.run(60, set())
        _, ram = snap(env)
        v = ram.view("<u2").astype(int)
        if prev is not None:
            d = v - prev
            for off in np.nonzero(d == 1)[0]:
                plus1_hist[off] = plus1_hist.get(off, 0) + 1
            seen_l.append((int(v[base // 2]),
                           int(v[base // 2 + 1])))
        prev = v
    # score_l must have progressed through 0..5 (or as far as it got)
    l_vals = [a for a, _b in seen_l]
    l_ok = (len(set(l_vals)) >= 2 and max(l_vals) >= 1
            and all(0 <= x <= 5 for x in l_vals))
    # score_r = +1 co-movers near base (struct-adjacent), never > 5
    co = [off for off, n in plus1_hist.items()
          if n >= 2 and abs(off * 2 - base) <= 32]
    return {"score_l_addr": hex(base), "l_progress": l_vals[:24],
            "l_ok": l_ok,
            "score_r_cands": [hex(o * 2) for o in co]}


def main():
    os.makedirs(OUT, exist_ok=True)
    jr = make_jrn(OUT, "[pongA]")
    report = {}
    env = PongEnv()
    # THE KEY MOVE (r14 precedent): disconnect pad2 -> the game's OWN AI
    # plays the right paddle (source else-branch, speed 3 px/f). The
    # agent then plays the single left paddle against a real opponent.
    env.p.core.set_port_device(0, port=1)
    jr({"ev": "pad2_disconnected_ai_mode"})
    report["ai_mode"] = True
    jr({"ev": "boot", "core": env.boot_info})
    f = env.settle()
    jr({"ev": "settled", "frames": f})
    fr = env.frame()
    save_png(OUT, fr, "pong_stageA_settled.png")

    verified, nobs = hunt_ball(env, jr)
    report["ball"] = verified
    jr({"ev": "ball_verified", "hits": verified})

    lcands = hunt_paddle(env, jr, 0)
    report["paddle_l_cands"] = lcands
    jr({"ev": "paddle_l", "cands": lcands})

    scores = verify_scores(env, jr)
    report["scores"] = scores
    jr({"ev": "scores", "verified": scores})

    env.close()
    with open(os.path.join(OUT, "pong_stage_a.json"), "w") as fp:
        json.dump(report, fp, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
