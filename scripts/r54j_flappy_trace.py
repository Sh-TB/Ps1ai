#!/usr/bin/env python3
"""r54j_flappy_trace.py — one-life trace: the BRAIN vs the sf teacher
on the SAME frame stream, dumping the first divergences and the death
sequence. Diagnostic only (assisted observation side)."""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    sys.path.insert(0, _p)

from ps1play.learn.games import FlappyEnv, _small_rgb      # noqa: E402
from ps1play.learn.teacher import FlappyTeacher            # noqa: E402
from ps1play.learn.runner import BrainClient               # noqa: E402
from ps1play.learn import visual_only as VO                # noqa: E402

OUT = os.path.join(REPO, "scratch", "r54")


def main():
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    art = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        OUT, "flappy_student_feat_p4sf5.npz")
    env = FlappyEnv()
    env.reach_ready()
    env.start_episode(k)
    brain = BrainClient(art)
    teacher = FlappyTeacher()
    prev_fr = None
    prev_by = None
    rows = []
    for step in range(2500):
        fr = env.frame()
        small = _small_rgb(fr)
        b_act = brain.act(small)
        f = VO.features_flappy(small, prev_fr)
        tby, tvy, tgc = teacher.observe(fr, prev_by)
        t_act = teacher.act(tby, tvy if tvy is not None else 0.0, tgc)
        rows.append({
            "step": step, "b_act": b_act, "t_act": t_act,
            "f_by": round(float(f[0]), 1), "f_vy": round(float(f[1]), 1),
            "f_gc": round(float(f[2]), 1), "f_dx": round(float(f[3]), 1),
            "t_by": -1 if tby is None else round(float(tby), 1),
            "t_gc": -1 if tgc is None else round(float(tgc), 1),
            "dead": bool(env.game_over(fr))})
        prev_fr = small
        prev_by = tby
        env.run(1, {"B"} if b_act == "FLAP" else set())
        if env.game_over(env.frame()):
            rows[-1]["dead"] = True
            break
    brain.close()
    env.close()
    # divergences
    divs = [r for r in rows if r["b_act"] != r["t_act"]]
    print(f"k={k} steps={len(rows)} divergences={len(divs)}")
    for r in divs[:12]:
        print("DIV", json.dumps(r))
    print("--- death sequence (last 30):")
    for r in rows[-30:]:
        print(json.dumps(r))
    with open(os.path.join(OUT, f"trace_k{k}.json"), "w") as fjs:
        json.dump(rows, fjs)


if __name__ == "__main__":
    main()
