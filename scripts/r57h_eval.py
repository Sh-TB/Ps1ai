#!/usr/bin/env python3
"""r57h_eval.py — the R57 closed-loop evaluator (visual-only, teacher-off).

One boot per invocation; episodes from the pre-seed anchor. Every run:
  * installs the teacher import blocker + writes a hashed no-teacher
    trace (the PART 4 runtime evidence),
  * counts pipes with the single-source-of-truth PassageCounter,
  * detects death visually only (NO RAM reads anywhere),
  * optionally saves the per-episode lives (frames + the agent's OWN
    actions) for the failure/latch analysis and student mining.

Usage:
  python3 scripts/r57h_eval.py --model data/learn/r57_bootstrap_bc.npz \
      --seeds 90,210 --reps 2 --budget 10000 --tag bootstrap
"""
import argparse
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.learn.games import FlappyEnv, _small_rgb      # noqa: E402
from ps1play.learn.brain_client import BrainClient  # noqa: E402
from ps1play.learn import student_only as SO               # noqa: E402
from r57_lib import PassageCounter, jsave, sha256_file     # noqa: E402

SCR = os.path.join(REPO, "scratch", "r57")


class BrainAgent:
    """The deployed-path agent (subprocess brain) + the visual-only
    passage counter wiring, wrapped so run_episode can drive it."""

    def __init__(self, artifact):
        self.brain = BrainClient(artifact)
        self.counter = PassageCounter()
        self._step = 0

    def reset_history(self):
        self.brain.reset_history()
        self.counter.last = None
        self.counter.count = 0
        self.counter.events = []
        self._step = 0

    def act(self, small):
        return self.brain.act(small)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--seeds", default="90,210")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--budget", type=int, default=10000)
    ap.add_argument("--tag", default="eval")
    ap.add_argument("--save-lives", action="store_true")
    a = ap.parse_args()

    trace = SO.NoTeacherTrace(os.path.join(
        SCR, f"noteacher_trace_{a.tag}_{int(time.time())}.jsonl"))
    SO.install_teacher_blocker(trace)
    trace.event("EVAL_START", model=os.path.basename(a.model),
                seeds=a.seeds, reps=a.reps, budget=a.budget)

    env = FlappyEnv()
    env.reach_ready()
    agent = BrainAgent(a.model)
    rows = []
    try:
        for k in [int(x) for x in a.seeds.split(",")]:
            for rep in range(a.reps):
                agent.reset_history()
                pc = agent.counter
                frames, acts, obs_ys, bxs = [], [], [], []
                from ps1play.learn.perception import (
                    flappy_bird_y, flappy_green_mask,
                    flappy_gap_target_r15)
                env.start_episode(k)

                class _OnStep:
                    def __call__(self, step, small, action, fr):
                        frames.append(small)
                        acts.append(action)
                        by, _n = flappy_bird_y(fr)
                        obs_ys.append(float(by) if by is not None else -1.0)
                        _g, bx = flappy_gap_target_r15(
                            flappy_green_mask(fr),
                            by if by is not None else -1)
                        bxs.append(float(bx) if bx is not None else -1.0)

                from r57_lib import run_episode
                r = run_episode(env, agent, k, a.budget, passage=pc,
                                on_step=_OnStep(), tag=f"{a.tag}_k{k}_r{rep}")
                r.pop("passage_events", None)
                if a.save_lives:
                    lp = os.path.join(
                        SCR, f"life_{a.tag}_k{k}_r{rep}.npz")
                    np.savez_compressed(
                        lp, frames=np.asarray(frames, dtype=np.uint8),
                        actions=np.asarray(acts),
                        beak_y=np.asarray(obs_ys, dtype=np.float32),
                        band_x=np.asarray(bxs, dtype=np.float32))
                    r["life_npz"] = os.path.basename(lp)
                    r["life_sha256"] = sha256_file(lp)
                rows.append(r)
                trace.event("EPISODE_DONE", **{kk: r[kk] for kk in
                                               ("tag", "k", "result",
                                                "pipes", "steps")})
                print(json.dumps(r), flush=True)
    finally:
        agent.brain.close()
        env.close()
        sha = trace.finish()

    pipes = [r["pipes"] for r in rows]
    summary = {
        "round": "R57", "tag": a.tag,
        "model": os.path.basename(a.model),
        "model_sha256": sha256_file(a.model),
        "seeds": [int(x) for x in a.seeds.split(",")],
        "reps": a.reps, "budget": a.budget,
        "rows": rows,
        "per_seed_pipes": {r["k"]: r["pipes"] for r in rows},
        "total_pipes": sum(pipes),
        "mean_pipes": round(float(np.mean(pipes)), 2) if pipes else 0,
        "no_teacher_trace_sha256": sha,
    }
    jsave(os.path.join(SCR, f"eval_{a.tag}.json"), summary)
    print("SUMMARY:", json.dumps({k: v for k, v in summary.items()
                                  if k not in ("rows",)}))


if __name__ == "__main__":
    main()
