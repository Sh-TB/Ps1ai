#!/usr/bin/env python3
"""r55_eval.py — the same-boot head-to-head: the law-on-v7 teacher vs
the v7 student (subprocess brain, frames only) on the identical 5-seed
protocol + DAgger relabel collection on the TRAIN seeds.

Protocol honesty:
  * both agents run in THIS boot, on the same seeds, same budgets,
    same pipe-count proxy (the eval-side full-res band acquisition);
  * the student = the deployed Brain subprocess (frames in / action
    out, no RAM, no emulator state);
  * the DAgger labels = the law-on-v7 teacher acting on the STUDENT's
    own sensory stream (same-sensor relabel, the r54i discipline);
    collected on the TRAIN family (k=6/30/60) ONLY — the held-out
    seeds (90/210) are never labeled for training.
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
sys.path.insert(0, REPO)

from ps1play.learn.games import FlappyEnv, _small_rgb      # noqa: E402
from ps1play.learn.runner import BrainClient               # noqa: E402
from ps1play.learn.perception import (flappy_bird_y,       # noqa: E402
                                      flappy_gap_target_r15,
                                      flappy_green_mask)
from r55g_m1 import LawOnV7Agent                           # noqa: E402

OUT = os.path.join(REPO, "scratch", "r55")
SEEDS = [(6, 6000), (30, 4500), (60, 4500), (90, 4000), (210, 4000)]
TRAIN_K = {6, 30, 60}


def run_life(env, agent, k, budget, tag, dag=None, trace=False):
    env.start_episode(k)
    if hasattr(agent, "reset_history"):
        agent.reset_history()
    frames, acts, t_acts = [], [], []
    pipes = 0
    last_band_x = None
    flaps = 0
    t0 = time.time()
    step = 0
    for step in range(budget):
        fr = env.frame()
        small = _small_rgb(fr)
        action = agent.act(small)
        if action == "FLAP":
            flaps += 1
        if dag is not None or trace:
            frames.append(small)
            acts.append(action)
        if dag is not None:
            t_acts.append(dag.act(small))
        by, _n = flappy_bird_y(fr)
        green = flappy_green_mask(fr)
        _gc, bx = flappy_gap_target_r15(green, by if by is not None
                                        else -1)
        if bx is not None:
            if last_band_x is not None and bx > last_band_x + 60:
                pipes += 1
            last_band_x = bx
        env.run(1, {"B"} if action == "FLAP" else set())
        if env.game_over(env.frame()):
            break
    res = {"tag": tag, "k": k, "result": "death" if step < budget - 1
           else "budget", "pipes": pipes, "steps": step + 1,
           "flaps": flaps, "wall_s": round(time.time() - t0, 1)}
    print(json.dumps(res), flush=True)
    if trace and len(frames):
        np.savez_compressed(
            os.path.join(OUT, f"{tag}.npz"),
            frames=np.asarray(frames, dtype=np.uint8),
            actions=np.asarray(acts))
    if dag is not None and len(frames):
        np.savez_compressed(
            os.path.join(OUT, f"{tag}.npz"),
            frames=np.asarray(frames, dtype=np.uint8),
            actions=np.asarray(acts),
            teacher_actions=np.asarray(t_acts))
    return res


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--art", default=os.path.join(
        REPO, "data", "learn", "flappy_student_feat_p5v7.npz"))
    ap.add_argument("--tag", default="r1")
    ap.add_argument("--agents", default="teacher,student")
    a = ap.parse_args()

    env = FlappyEnv()
    env.reach_ready()
    results = {}
    want = set(a.agents.split(","))

    if "teacher" in want:
        agent = LawOnV7Agent()
        rows = [run_life(env, agent, k, b, f"teacher_v7_k{k}",
                         dag=None, trace=True)
                for k, b in SEEDS]
        results["P_teacher_v7"] = rows

    if "student" in want:
        client = BrainClient(a.art)
        rows = []
        for k, b in SEEDS:
            dag = LawOnV7Agent() if k in TRAIN_K else None
            r = run_life(env, client, k, b,
                         f"dag_{a.tag}_k{k:03d}", dag=dag)
            r["agent"] = "P_student_v7"
            rows.append(r)
        client.close()
        results["P_student_v7"] = rows

    env.close()
    path = os.path.join(OUT, f"r55_eval_{a.tag}.json")
    with open(path, "w") as f:
        json.dump({"tag": a.tag, "artifact": a.art,
                   "results": results}, f, indent=2)
    print("== saved", path, flush=True)
    for name, rows in results.items():
        tot = sum(r["pipes"] for r in rows)
        print(f"{name}: total pipes {tot} "
              f"({[r['pipes'] for r in rows]})")


if __name__ == "__main__":
    main()
