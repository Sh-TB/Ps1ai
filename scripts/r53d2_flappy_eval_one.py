#!/usr/bin/env python3
"""r53d2_flappy_eval_one.py — ONE eval life per invocation (FOREGROUND,
the R48 lesson: background launches die silently in this sandbox).
Appends its result to flappy_eval.json incrementally.
Usage: r53d2_flappy_eval_one.py <agent> <k> <steps>
  agent in {teacher, student_feat, student_raw}
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    sys.path.insert(0, _p)

from ps1play.learn.games import FlappyEnv, _small_rgb      # noqa: E402
from ps1play.learn.teacher import FlappyTeacherAgent       # noqa: E402
from ps1play.learn.runner import BrainClient               # noqa: E402
from ps1play.learn.perception import (flappy_bird_y,       # noqa: E402
                                      flappy_gap_target_r15,
                                      flappy_green_mask)
from hellopong_r12_lib import make_jrn, save_png           # noqa: E402

OUT = os.path.join(REPO, "scratch", "r53learn")
EVAL_JSON = os.path.join(OUT, "flappy_eval.json")


def main():
    agent_name, k, max_steps = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    jr = make_jrn(OUT, "[flapE1]")
    env = FlappyEnv()
    env.reach_ready()
    env.start_episode(k)        # restore ready -> k idle -> r15 pulses
    if agent_name == "teacher":
        agent = FlappyTeacherAgent()
    else:
        agent = BrainClient(os.path.join(
            OUT, f"flappy_student_{agent_name.split('_')[1]}.npz"))
    if hasattr(agent, "reset_history"):
        agent.reset_history()
    pipes = flaps = 0
    last_band_x = None
    prev_by = None
    t0 = time.time()
    tag = f"{agent_name}_k{k}"
    for step in range(max_steps):
        fr = env.frame()
        small = _small_rgb(fr)
        if hasattr(agent, "act_full"):
            action = agent.act_full(fr)
        else:
            action = agent.act(small)
        if action == "FLAP":
            flaps += 1
        by, _n = flappy_bird_y(fr)
        green = flappy_green_mask(fr)
        _gc, bx = flappy_gap_target_r15(green, by)
        if bx is not None:
            if last_band_x is not None and bx > last_band_x + 60:
                pipes += 1
            last_band_x = bx
        prev_by = by
        env.run(1, {"B"} if action == "FLAP" else set())
        if step % 1500 == 0 and step:
            save_png(OUT, fr, f"eval_{tag}_{step:05d}.png")
        if env.game_over(env.frame()):
            break
    r = {"tag": tag, "k": k, "agent": agent_name,
         "result": "death" if step < max_steps - 1 else "budget",
         "pipes": pipes, "steps": step + 1, "flaps": flaps,
         "wall_s": round(time.time() - t0, 1)}
    jr({"ev": "eval", **r})
    rows = []
    if os.path.exists(EVAL_JSON):
        rows = json.load(open(EVAL_JSON))
    rows = [x for x in rows if x.get("tag") != tag]
    rows.append(r)
    with open(EVAL_JSON, "w") as f:
        json.dump(rows, f, indent=2)
    if hasattr(agent, "close"):
        agent.close()
    env.close()
    print(json.dumps(r))


if __name__ == "__main__":
    main()
