#!/usr/bin/env python3
"""r53d_flappy_eval.py — Stage D/E: closed-loop visual-only evaluation.

Agents (SAME protocol: restore ready anchor -> seed k -> r15 start):
  P1 teacher       @ k=6 budget 9000  -> the 56-pipe teacher evidence
  P1 teacher       @ k=90 (held-out seed family) -> honest distribution
  P2 student-feat  via BrainClient subprocess (frame-only) @ k=6, k=90
  P2 student-raw   via BrainClient subprocess (frame-only) @ k=6, k=90

Pass counting = the vision band-acquisition proxy (new tracked band
well right of the last one), disclosed. Deaths = the beige-panel test.
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    sys.path.insert(0, _p)

from ps1play.learn.games import FlappyEnv                 # noqa: E402
from ps1play.learn.teacher import FlappyTeacher           # noqa: E402
from ps1play.learn.runner import BrainClient              # noqa: E402
from ps1play.learn.perception import (flappy_bird_y,      # noqa: E402
                                      flappy_gap_target_r15,
                                      flappy_green_mask)
from ps1play.learn.games import _small_rgb                # noqa: E402
from hellopong_r12_lib import make_jrn, save_png          # noqa: E402

OUT = os.path.join(REPO, "scratch", "r53learn")


def run_life(env, agent, k, max_steps, tag, jr, save_frames=False):
    env.start_episode(k)
    if hasattr(agent, "reset_history"):
        agent.reset_history()
    teacher_obs = FlappyTeacher()          # for the gap/bird observation
    pipes = 0
    flaps = 0
    last_band_x = None
    prev_by = None
    t0 = time.time()
    for step in range(max_steps):
        fr = env.frame()
        small = _small_rgb(fr)
        if hasattr(agent, "act_full"):
            action = agent.act_full(fr)   # native-sensor baseline tier
        else:
            action = agent.act(small)     # frame-only student tier
        buttons = {"B"} if action == "FLAP" else set()
        if action == "FLAP":
            flaps += 1
        # vision bookkeeping (evaluation-side; never sent to the agent)
        by, _n = flappy_bird_y(fr)
        green = flappy_green_mask(fr)
        _gc, bx = flappy_gap_target_r15(green, by)
        if bx is not None:
            if last_band_x is not None and bx > last_band_x + 60:
                pipes += 1
            last_band_x = bx
        prev_by = by
        env.run(1, buttons)
        if save_frames and step % 900 == 0:
            save_png(OUT, fr, f"eval_{tag}_{step:05d}.png")
        if env.game_over(env.frame()):
            break
    return {"tag": tag, "k": k, "result": "death" if step < max_steps - 1
            else "budget", "pipes": pipes, "steps": step + 1,
            "flaps": flaps, "wall_s": round(time.time() - t0, 1)}


def main():
    jr = make_jrn(OUT, "[flapE]")
    env = FlappyEnv()
    env.reach_ready()
    from ps1play.learn.teacher import FlappyTeacherAgent
    teacher = FlappyTeacherAgent()
    results = []

    # P1: the 56-pipe teacher evidence (long budget, train-family seed)
    r = run_life(env, teacher, 6, 9000, "teacher_k6_long", jr,
                 save_frames=True)
    results.append(r)
    jr({"ev": "eval", **r})
    # P1 held-out seed family
    for k in (90, 210):
        r = run_life(env, teacher, k, 4000, f"teacher_k{k}", jr)
        results.append(r)
        jr({"ev": "eval", **r})

    # P2 students via the subprocess brain (frame-only decisions)
    for which in ("feat", "raw"):
        art = os.path.join(OUT, f"flappy_student_{which}.npz")
        client = BrainClient(art)
        for k in (6, 90):
            r = run_life(env, client, k, 4000,
                         f"student_{which}_k{k}", jr, save_frames=(k == 6))
            r["agent"] = f"student_{which}"
            results.append(r)
            jr({"ev": "eval", **r})
        client.close()

    with open(os.path.join(OUT, "flappy_eval.json"), "w") as f:
        json.dump(results, f, indent=2)
    env.close()
    for r in results:
        print(f"{r['tag']:22s} k={r['k']:3d} {r['result']:6s} "
              f"pipes={r['pipes']:3d} steps={r['steps']:5d} "
              f"flaps={r['flaps']}")


if __name__ == "__main__":
    main()
