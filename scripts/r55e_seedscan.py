#!/usr/bin/env python3
"""r55e_seedscan.py — probe the full-res teacher across many seeds
(short 1500-step budgets: the r53 first-pipe hazard killed early) to
map where the honest r15-law teacher DIES vs flies. Teacher-death
seeds are the cleanest 'student must exceed teacher' showcase.
One boot. Also re-runs k=6 with a LONG budget (12000) to measure the
teacher's real ceiling when not budget-capped.
"""
import json
import os
import sys
import time

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.learn.games import FlappyEnv, _small_rgb        # noqa: E402
from r54g_flappy_eval import FlappyTeacherAgentFull          # noqa: E402
from ps1play.learn.perception import (flappy_bird_y,         # noqa: E402
                                      flappy_gap_target_r15,
                                      flappy_green_mask)

OUT = os.path.join(REPO, "scratch", "r55")
os.makedirs(OUT, exist_ok=True)

SEEDS = [6, 18, 30, 42, 54, 66, 78, 90, 102, 114, 126, 150,
         174, 198, 222, 246, 270, 294]
BUDGET = 1500
LONG_K = 6
LONG_BUDGET = 12000


def run_life(env, agent, k, budget, tag):
    env.start_episode(k)
    if hasattr(agent, "reset_history"):
        agent.reset_history()
    pipes = 0
    last_band_x = None
    t0 = time.time()
    step = 0
    for step in range(budget):
        fr = env.frame()
        action = agent.act_full(fr)
        by, _n = flappy_bird_y(fr)
        green = flappy_green_mask(fr)
        _gc, bx = flappy_gap_target_r15(green, by if by is not None else -1)
        if bx is not None:
            if last_band_x is not None and bx > last_band_x + 60:
                pipes += 1
            last_band_x = bx
        env.run(1, {"B"} if action == "FLAP" else set())
        if env.game_over(env.frame()):
            break
    res = {"tag": tag, "k": k, "result": "death" if step < budget - 1
           else "budget", "pipes": pipes, "steps": step + 1,
           "wall_s": round(time.time() - t0, 1)}
    print(json.dumps(res), flush=True)
    return res


def main():
    env = FlappyEnv()
    env.reach_ready()
    agent = FlappyTeacherAgentFull()
    rows = []
    for k in SEEDS:
        rows.append(run_life(env, agent, k, BUDGET, f"probe_k{k}"))
    long_row = run_life(env, agent, LONG_K, LONG_BUDGET,
                        f"long_k{LONG_K}")
    env.close()
    with open(os.path.join(OUT, "r55e_seedscan.json"), "w") as f:
        json.dump({"probe_budget": BUDGET, "probe": rows,
                   "long": long_row}, f, indent=2)
    print("== saved r55e_seedscan.json", flush=True)


if __name__ == "__main__":
    main()
