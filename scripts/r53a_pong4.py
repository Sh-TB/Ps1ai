#!/usr/bin/env python3
"""r53a_pong4.py — Stage A final: teacher plays PROPERLY (both paddles
return) with occasional deliberate left-misses; verifies the full RAM
anchor set against vision/events; writes pong_ram_anchors.json (the
verified teacher-side truth contract) and refreshes pong_anchor."""
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
PAD_L, SCORE_L = 0x1FFEB0, 0x1FFEB4
PAD_R, SCORE_R = 0x1FFEB8, 0x1FFEBC


def i32(ram, a):
    return int(np.frombuffer(ram[a:a + 4].tobytes(), "<i4")[0])


def main():
    jr = make_jrn(OUT, "[pongA4]")
    env = PongEnv()
    env.p.core.set_port_device(0, port=1)
    env.settle()
    teacher = PongTeacher(deadband=10.0)
    miss_counter = [0]

    def policy(cx, cy, lp, ram):
        """Teacher + a deliberate miss every 3rd approach (left gives
        the AI a point so BOTH score words get events)."""
        iy = i32(ram, BALL_Y)
        if cx is not None and cx < 130:
            miss_counter[0] += 1
            if miss_counter[0] % 3 == 0:
                target = 0 if iy > 120 else 220
                return "UP" if target < (lp or 120) else "DOWN"
        return teacher.act((cx, cy), lp)

    rows = []
    prev_scores = (0, 0)
    events = []
    err_x, err_y, err_pl, err_pr = [], [], [], []
    for i in range(2600):
        fr, ram = snap = (env.frame(), env.p.core.ram.copy())
        cx, cy, _n = pong_ball_centroid(fr)
        lp_v, rp_v = pong_paddle_rows(fr)
        lp_r, rp_r = i32(ram, PAD_L), i32(ram, PAD_R)
        sl, sr = i32(ram, SCORE_L), i32(ram, SCORE_R)
        bx, by = i32(ram, BALL_X), i32(ram, BALL_Y)
        if cx is not None:
            err_x.append(abs(bx - cx))
            err_y.append(abs(by - cy))
        if lp_v is not None:
            err_pl.append(abs(lp_r - lp_v))
        if rp_v is not None:
            err_pr.append(abs(rp_r - rp_v))
        if (sl, sr) != prev_scores:
            events.append({"step": i, "score_l": sl, "score_r": sr,
                           "ball_x": bx})
            prev_scores = (sl, sr)
        act = policy(cx, cy, lp_v, ram)
        env.run(2, {"UP": {"UP"}, "DOWN": {"DOWN"},
                    "NONE": set()}.get(act, set()))
        if sl >= 3 or sr >= 3:
            break
    report = {
        "n_steps": i + 1,
        "final_scores": {"l": sl, "r": sr},
        "events": events,
        "err_mean": {"ball_x_vs_vision": round(float(np.mean(err_x)), 2),
                     "ball_y_vs_vision": round(float(np.mean(err_y)), 2),
                     "pad_l_vs_vision": round(float(np.mean(err_pl)), 2),
                     "pad_r_vs_vision": round(float(np.mean(err_pr)), 2)},
    }
    # verifications
    sls = [e["score_l"] for e in events]
    srs = [e["score_r"] for e in events]
    report["score_l_ok"] = len(set(sls)) >= 2 and max(sls) >= 1
    report["score_r_ok"] = len(set(srs)) >= 2 and max(srs) >= 1
    report["pad_err_ok"] = (report["err_mean"]["pad_l_vs_vision"] < 12
                            and report["err_mean"]["pad_r_vs_vision"] < 12)
    report["ball_err_ok"] = (report["err_mean"]["ball_x_vs_vision"] < 12
                             and report["err_mean"]["ball_y_vs_vision"] < 12)
    jr({"ev": "final", **{k: v for k, v in report.items()
                          if k != "events"}})
    anchors = {
        "game": "pong",
        "endian": "little",
        "ball_x": {"addr": BALL_X, "fmt": "i32", "role": "teacher_label",
                   "err_px": report["err_mean"]["ball_x_vs_vision"]},
        "ball_y": {"addr": BALL_Y, "fmt": "i32", "role": "teacher_label",
                   "err_px": report["err_mean"]["ball_y_vs_vision"]},
        "paddle_l": {"addr": PAD_L, "fmt": "i32", "role": "teacher_label",
                     "err_px": report["err_mean"]["pad_l_vs_vision"]},
        "paddle_r": {"addr": PAD_R, "fmt": "i32", "role": "teacher_label",
                     "err_px": report["err_mean"]["pad_r_vs_vision"]},
        "score_l": {"addr": SCORE_L, "fmt": "i32",
                    "role": "evaluation_only"},
        "score_r": {"addr": SCORE_R, "fmt": "i32",
                    "role": "evaluation_only"},
        "ai_opponent": ("pad2 disconnected via set_port_device(0, port=1) "
                        "-> source else-branch AI (3 px/f, deadband 10); "
                        "MUST be re-applied after every boot"),
        "verified": all(report[k] for k in
                        ("score_l_ok", "score_r_ok", "pad_err_ok",
                         "ball_err_ok")),
    }
    with open(os.path.join(OUT, "pong_ram_anchors.json"), "w") as f:
        json.dump(anchors, f, indent=2)
    with open(os.path.join(OUT, "pong_stage_a4.json"), "w") as f:
        json.dump(report, f, indent=2)
    env.close()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
