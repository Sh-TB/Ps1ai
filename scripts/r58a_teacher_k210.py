#!/usr/bin/env python3
"""r58a_teacher_k210.py — ASSISTED DIAGNOSTIC ONLY (not student training
data): one LawOnV7Agent (flappy_law_on_v7) episode on k210 with the life
recorded, for the k210-deficit divergence analysis.

Boundary disclosure: this process NEVER imports ps1play.learn.student_only
and produces NO student labels — the saved life is a diagnostic trajectory
of the teacher for comparison only (mission PART 2 allows teacher demos
for the bootstrap; this run is not even that — it is failure forensics).
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

from ps1play.learn.games import FlappyEnv, _small_rgb       # noqa: E402
from r55g_m1 import LawOnV7Agent                            # noqa: E402
from r57_lib import PassageCounter, gap_band_x, sha256_file  # noqa: E402
from ps1play.learn.perception import (flappy_bird_y, flappy_green_mask,  # noqa: E402
                                      flappy_gap_target_r15)

SCR = os.path.join(REPO, "scratch", "r57")
K = 210
BUDGET = 10000


def main():
    env = FlappyEnv()
    env.reach_ready()
    agent = LawOnV7Agent()
    agent.reset_history()
    pc = PassageCounter()
    frames, acts, obs_ys, bxs = [], [], [], []

    env.start_episode(K)
    t0 = time.time()
    result = "budget"
    step = 0
    for step in range(BUDGET):
        fr = env.frame()
        small = _small_rgb(fr)
        action = agent.act(small)
        frames.append(small)
        acts.append(action)
        pre = flappy_bird_y(fr)
        by = pre[0] if isinstance(pre, tuple) else None
        obs_ys.append(float(by) if by is not None else -1.0)
        _g, bx = flappy_gap_target_r15(flappy_green_mask(fr),
                                       by if by is not None else -1)
        bxs.append(float(bx) if bx is not None else -1.0)
        env.run(1, {"B"} if action == "FLAP" else set())
        post = flappy_bird_y(env.frame())
        by2 = post[0] if isinstance(post, tuple) else None
        pc.fire(gap_band_x(env, env.frame(), by2), step)
        if env.game_over(env.frame()):
            result = "death"
            break
    wall = round(time.time() - t0, 1)
    env.close()

    lp = os.path.join(SCR, f"life_teacher_k210_r0.npz")
    np.savez_compressed(lp, frames=np.asarray(frames, dtype=np.uint8),
                        actions=np.asarray(acts),
                        beak_y=np.asarray(obs_ys, dtype=np.float32),
                        band_x=np.asarray(bxs, dtype=np.float32))
    out = {"tag": "r58_teacher_k210_diag", "k": K, "result": result,
           "pipes": pc.count, "steps": step + 1,
           "passage_events": list(pc.events), "wall_s": wall,
           "life_npz": os.path.basename(lp),
           "life_sha256": sha256_file(lp),
           "disclosure": "ASSISTED diagnostic, teacher-only process, "
                         "no student labels"}
    with open(os.path.join(SCR, "r58_teacher_k210_diag.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
