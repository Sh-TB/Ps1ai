#!/usr/bin/env python3
"""r55g_m1.py — MILESTONE 1: the r15 play law driven by the v7 observer
(small frames + own action history ONLY) on the identical 5-seed
protocol. Target: match the full-res teacher (51/38/38/34/34, alive).
One boot."""
import json
import os
import sys
import time

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                             # noqa: E402

from ps1play.learn.games import FlappyEnv, _small_rgb          # noqa: E402
from ps1play.learn.teacher import FlappyTeacher                # noqa: E402
from ps1play.learn import visual_only as VO                    # noqa: E402
from ps1play.learn.perception import (flappy_bird_y,           # noqa: E402
                                      flappy_gap_target_r15,
                                      flappy_green_mask)

OUT = os.path.join(REPO, "scratch", "r55")
os.makedirs(OUT, exist_ok=True)
SEEDS = [(6, 6000), (30, 4500), (60, 4500), (90, 4000), (210, 4000)]


class LawOnV7Agent:
    """r15 law on the v7 observer state + the GapTrackerV7-filtered
    gap center (the same feature pathway the feature_version-7 student
    will consume — same-sensor discipline)."""

    name = "flappy_law_on_v7"

    def __init__(self, record=False):
        # fb/eb = the r55k sim sweep winner (14/26 = the teacher
        # defaults; fb=16 measured 6/10 vs 7/10 alive in the sweep)
        self.t = FlappyTeacher(flap_below=14.0, emergency_below=26.0)
        self.obs = VO.BirdObserverV7()
        self.gtr = VO.GapTrackerV7()
        self._vo = VO
        self.prev_action = None
        self.record = record
        self.rec = []

    def reset_history(self):
        self.t.reset_history()
        self.obs.reset()
        self.gtr.reset()
        self.prev_action = None
        self.rec = []

    def act(self, small):
        by, vy = self.obs.step(small, self.prev_action)
        gc_raw, dx, g0, g1, _raw = self._vo._flappy_gap_raw2(
            small, by_hint=by)
        gc = self.gtr.step((gc_raw, g0, g1, dx + 160.0))
        a = self.t.act(by if by >= 0 else None, vy, gc)
        self.prev_action = a
        if self.record:
            self.rec.append((small, a, by, vy, gc, dx, g0, g1))
        return a


def run_life(env, agent, k, budget, tag, trace_path=None):
    env.start_episode(k)
    agent.reset_history()
    pipes = 0
    last_band_x = None
    flaps = 0
    t0 = time.time()
    step = 0
    trace = []
    for step in range(budget):
        fr = env.frame()
        small = _small_rgb(fr)
        action = agent.act(small)
        if action == "FLAP":
            flaps += 1
        by, _n = flappy_bird_y(fr)
        green = flappy_green_mask(fr)
        _gc, bx = flappy_gap_target_r15(green, by if by is not None else -1)
        if bx is not None:
            if last_band_x is not None and bx > last_band_x + 60:
                pipes += 1
            last_band_x = bx
        if trace_path is not None:
            trace.append((small, action,
                          float(agent.obs.y) if agent.obs.y is not None
                          else -1.0, float(agent.obs.vy),
                          int(agent.obs.since_trust),
                          -1.0 if by is None else float(by), _gc, bx,
                          float(agent.gtr.gc)
                          if agent.gtr.gc is not None else -1.0))
        env.run(1, {"B"} if action == "FLAP" else set())
        if env.game_over(env.frame()):
            break
    res = {"tag": tag, "k": k, "result": "death" if step < budget - 1
           else "budget", "pipes": pipes, "steps": step + 1,
           "flaps": flaps, "wall_s": round(time.time() - t0, 1)}
    print(json.dumps(res), flush=True)
    if trace_path is not None:
        np.savez_compressed(
            trace_path,
            frames=np.asarray([t[0] for t in trace], dtype=np.uint8),
            action=np.asarray([t[1] for t in trace]),
            obs_y=np.asarray([t[2] for t in trace], dtype=np.float32),
            obs_vy=np.asarray([t[3] for t in trace], dtype=np.float32),
            since_trust=np.asarray([t[4] for t in trace], dtype=np.int32),
            beak_y=np.asarray([t[5] for t in trace], dtype=np.float32),
            gap_gc=np.asarray([-1.0 if t[6] is None else t[6]
                               for t in trace], dtype=np.float32),
            gap_bx=np.asarray([-1.0 if t[7] is None else t[7]
                               for t in trace], dtype=np.float32),
            trk_gc=np.asarray([t[8] for t in trace], dtype=np.float32))
    return res


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", default="", help="npz path for a k=6 trace")
    a = ap.parse_args()
    env = FlappyEnv()
    env.reach_ready()
    agent = LawOnV7Agent()
    rows = []
    for k, budget in SEEDS:
        tp = (a.trace + f"_k{k}") if (a.trace and k in (6, 60, 90)) else None
        rows.append(run_life(env, agent, k, budget, f"lawonv7_k{k}",
                             trace_path=tp))
    env.close()
    with open(os.path.join(OUT, "r55g_m1.json"), "w") as f:
        json.dump({"rows": rows}, f, indent=2)
    print("== saved r55g_m1.json", flush=True)


if __name__ == "__main__":
    main()
