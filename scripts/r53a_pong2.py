#!/usr/bin/env python3
"""r53a_pong2.py — Stage A v2: keep the game ALIVE (PongTeacher drives
pad1 visually; the game AI drives the right side after the pad2
disconnect) and identify the RAM truth block by CORRELATION:

  * the diag run found the ball-x word at byte 0x1FFEA0 (u16 108 ==
    vision cx). The Ball struct (source: {x, y, vel_x, vel_y} ints)
    must therefore straddle 0x1FFEA0..0x1FFEAF — correlate the whole
    i32 window 0x1FFE80..0x1FFED0 against vision cx/cy/deltas over 90
    frames and assign x/y/vel_x/vel_y by best correlation.
  * left paddle: 2-cycle +-32 hunt (teacher paused for ~2.5 s)
  * scores: score_l = 0x1FFEB4 (r14 record) verified over natural
    points; score_r = the +1 co-mover.

Evidence -> scratch/r53learn/pong_stage_a2.json + pong_ram_anchors.json
"""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    sys.path.insert(0, _p)

from ps1play.learn.games import PongEnv                # noqa: E402
from ps1play.learn.perception import pong_ball_centroid  # noqa: E402
from ps1play.learn.teacher import PongTeacher          # noqa: E402
from hellopong_r12_lib import make_jrn, save_png       # noqa: E402

OUT = os.path.join(REPO, "scratch", "r53learn")
BASE = 0x1FFEA0


def snap(env):
    fr = env.frame()
    ram = env.p.core.ram.copy()
    return fr, ram


def main():
    jr = make_jrn(OUT, "[pongA2]")
    env = PongEnv()
    env.p.core.set_port_device(0, port=1)     # AI opponent
    env.settle()
    teacher = PongTeacher(deadband=10.0)
    report = {}

    # ---------- 1) correlate the i32 window with vision ----------
    series = []                                # (i32 words, cx, cy)
    prev_by = None
    for i in range(90):
        fr, ram = snap(env)
        cx, cy, n = pong_ball_centroid(fr)
        words = np.frombuffer(ram[0x1FFE80:0x1FFED0].tobytes(),
                              dtype="<i4")
        series.append((words, cx, cy))
        # teacher keeps the rally alive
        lp, _rp = __import__(
            "ps1play.learn.perception",
            fromlist=["pong_paddle_rows"]).pong_paddle_rows(fr)
        act = teacher.act((cx, cy), lp)
        env.run(2, {"UP": {"UP"}, "DOWN": {"DOWN"},
                    "NONE": set()}.get(act, set()))
    offs = list(range(0x1FFE80, 0x1FFED0, 4))
    corr_x, corr_y = {}, {}
    for k, off in enumerate(offs):
        xs = np.array([s[0][k] for s in series], dtype=float)
        cxs = np.array([s[1] if s[1] is not None else np.nan
                        for s in series])
        cys = np.array([s[2] if s[2] is not None else np.nan
                        for s in series])
        ok = ~np.isnan(cxs)
        if ok.sum() < 30:
            continue
        err_x = np.abs(xs[ok] - cxs[ok]).mean()
        err_y = np.abs(xs[ok] - cys[ok]).mean()
        corr_x[off] = round(float(err_x), 2)
        corr_y[off] = round(float(err_y), 2)
    ball_x = min(corr_x, key=corr_x.get)
    ball_y = min(corr_y, key=corr_y.get)
    report["ball_x"] = {"addr": hex(ball_x), "err": corr_x[ball_x],
                        "all": {hex(k): v for k, v in corr_x.items()}}
    report["ball_y"] = {"addr": hex(ball_y), "err": corr_y[ball_y],
                        "all": {hex(k): v for k, v in corr_y.items()}}
    jr({"ev": "ball_block", "x": report["ball_x"]["addr"],
        "y": report["ball_y"]["addr"]})

    # ---------- 2) left paddle hunt (teacher paused) ----------
    def go(frames, btn):
        env.run(frames, btn, set())
    go(8, {"UP"})
    _, r2 = snap(env)
    go(8, {"DOWN"})
    _, r3 = snap(env)
    go(8, {"UP"})
    go(8, {"DOWN"})
    _, r4 = snap(env)
    da = r3.view("<i2").astype(int) - r2.view("<i2").astype(int)
    db = r4.view("<i2").astype(int) - r3.view("<i2").astype(int)
    pcands = sorted((set(np.nonzero(da == 32)[0].tolist())
                     & set(np.nonzero(db == 32)[0].tolist())))[:12]
    report["paddle_l_cands"] = [hex(o * 2) for o in pcands]
    jr({"ev": "paddle_l", "cands": report["paddle_l_cands"]})

    # ---------- 3) score verification over natural play ----------
    base_u16 = 0x1FFEB4 // 2
    l_series = []
    plus1 = {}
    prev = None
    for i in range(220):                    # ~440 frames, teacher-driven
        fr, ram = snap(env)
        v = ram.view("<u2").astype(int)
        if prev is not None:
            d = v - prev
            for off in np.nonzero(d == 1)[0]:
                plus1[off] = plus1.get(off, 0) + 1
        prev = v
        l_series.append(int(v[base_u16]))
        cx, cy, _n = pong_ball_centroid(fr)
        lp, _rp = __import__(
            "ps1play.learn.perception",
            fromlist=["pong_paddle_rows"]).pong_paddle_rows(fr)
        act = teacher.act((cx, cy), lp)
        env.run(2, {"UP": {"UP"}, "DOWN": {"DOWN"},
                    "NONE": set()}.get(act, set()))
    l_ok = (max(l_series) >= 1 and min(l_series) >= 0
            and max(l_series) <= 5 and len(set(l_series)) >= 2)
    co = sorted(off for off, n in plus1.items()
                if n >= 2 and abs(off * 2 - 0x1FFEB4) <= 64)
    report["scores"] = {"score_l": hex(0x1FFEB4), "l_ok": l_ok,
                        "l_series": l_series[:40],
                        "score_r_cands": [hex(o * 2) for o in co]}
    jr({"ev": "scores", "l_ok": l_ok, "r": report["scores"]["score_r_cands"]})

    env.close()
    anchors = {
        "game": "pong",
        "ball_x": {"addr": ball_x, "fmt": "i32", "err_px": corr_x[ball_x]},
        "ball_y": {"addr": ball_y, "fmt": "i32", "err_px": corr_y[ball_y]},
        "paddle_l": {"addr": pcands[0] * 2 if pcands else None,
                     "fmt": "i32"},
        "score_l": {"addr": 0x1FFEB4, "fmt": "u16"},
        "score_r": {"addr": co[0] * 2 if co else None, "fmt": "u16"},
        "ai_opponent": "pad2 disconnected (source else-branch, 3 px/f)",
        "note": "teacher-driven Stage A; all reads at REST (no run "
                "between frame and RAM grab)",
    }
    with open(os.path.join(OUT, "pong_ram_anchors.json"), "w") as f:
        json.dump(anchors, f, indent=2)
    with open(os.path.join(OUT, "pong_stage_a2.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps({k: (v if k != "scores" else
                          {kk: vv for kk, vv in v.items()
                           if kk != "l_series"})
                      for k, v in report.items()}, indent=2))


if __name__ == "__main__":
    main()
