#!/usr/bin/env python3
"""r55i_divergence.py — record one full-res-teacher life (full frames),
then replay BOTH sensor pipelines offline and find the FIRST decision
divergence between the full-res law and the law-on-v7."""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.learn.games import FlappyEnv, _small_rgb        # noqa: E402
from r54g_flappy_eval import FlappyTeacherAgentFull          # noqa: E402
from ps1play.learn.teacher import FlappyTeacher              # noqa: E402
from ps1play.learn import visual_only as VO                  # noqa: E402

OUT = os.path.join(REPO, "scratch", "r55")
os.makedirs(OUT, exist_ok=True)


def record(env, k, budget):
    env.start_episode(k)
    t = FlappyTeacherAgentFull()
    t.reset_history()
    frames, acts = [], []
    t0 = time.time()
    for step in range(budget):
        fr = env.frame()
        a = t.act_full(fr)
        frames.append(fr)
        acts.append(a)
        env.run(1, {"B"} if a == "FLAP" else set())
        if env.game_over(env.frame()):
            break
    print(json.dumps({"steps": step + 1, "wall_s": round(time.time() - t0, 1)}),
          flush=True)
    return np.asarray(frames, dtype=np.uint8), acts


def replay(frames, acts):
    full_t = FlappyTeacher()
    full_prev = None
    v7_t = FlappyTeacher()
    v7 = VO.BirdObserverV7()
    v7_prev = None
    rows = []
    for i, fr in enumerate(frames):
        by, vy, gc = _full_inputs(fr, full_prev)
        full_prev = by
        a_full = full_t.act(by, vy if vy is not None else 0.0, gc)
        small = _small_rgb(fr)
        by7, vy7 = v7.step(small, v7_prev)
        gc7, dx7, g07, g17, _rb = VO._flappy_gap_raw2(small)
        a_v7 = v7_t.act(by7 if by7 >= 0 else None, vy7,
                        gc7 if gc7 >= 0 else None)
        v7_prev = a_v7
        rows.append((i, acts[i], a_full, a_v7, by, gc, by7, vy7, gc7))
    return rows


def _full_inputs(fr, prev_by):
    from ps1play.learn.perception import (flappy_bird_y,
                                          flappy_gap_target_r15,
                                          flappy_green_mask)
    by, _n = flappy_bird_y(fr)
    vy = (by - prev_by) if (by is not None and prev_by is not None) else None
    green = flappy_green_mask(fr)
    gc, _bx = flappy_gap_target_r15(green, by if by is not None else -1)
    return by, vy, gc


def main():
    env = FlappyEnv()
    env.reach_ready()
    frames, acts = record(env, 6, 1500)
    env.close()
    rows = replay(frames, acts)
    first = None
    for r in rows:
        if r[1] != r[3]:
            first = r
            break
    print("first agent-vs-v7 decision divergence:",
          None if first is None else
          f"step {first[0]} sent={first[1]} full={first[2]} v7={first[3]} "
          f"by_full={first[4]} gc_full={first[5]} by_v7={first[6]} "
          f"vy_v7={first[7]} gc_v7={first[8]}")
    # stats: how often do the two pipelines disagree?
    dis = sum(1 for r in rows if r[1] != r[3])
    print(f"decision disagreements: {dis}/{len(rows)}")
    # nearest 20 steps around the first divergence
    if first is not None:
        i0 = max(0, first[0] - 12)
        print(" step | sent full v7 | by_full gc_full | by_v7 vy_v7 gc_v7")
        for r in rows[i0:i0 + 25]:
            print(f" {r[0]:4d} | {r[1]:4s} {r[2]:4s} {r[3]:4s} | "
                  f"{-1 if r[4] is None else r[4]:7.1f} "
                  f"{-1 if r[5] is None else r[5]:7.1f} | "
                  f"{r[6]:7.1f} {r[7]:5.1f} {r[8]:6.1f}")
    np.savez_compressed(os.path.join(OUT, "r55i_full_life.npz"),
                        frames=frames, actions=np.asarray(acts))


if __name__ == "__main__":
    main()
