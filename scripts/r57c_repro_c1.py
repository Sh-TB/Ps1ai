#!/usr/bin/env python3
"""r57c_repro_c1.py — R57 PART 1 item 8: the C1 reproduction protocol.

The mission says "reproduce the reported R56 C1 result if possible" —
the review made it a defined protocol: N=3 fresh boots... executed as
3 RESTORED episodes per dev seed from ONE boot (the restore-is-not-a-
boot discipline; the anchor is pre-seed so each episode's k press
creates its own RNG). 5 dev seeds x 3 = 15 episodes of the FROZEN
champion (data/learn/flappy_student_feat_r56_c1.npz, NEVER rewritten),
deployed exactly as in R56: the subprocess brain (BrainClient).

Output: scratch/r57/r57c_repro.json (+ the boot-variance record that
every later cross-round comparison uses). No training, no claims.
"""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.learn.games import FlappyEnv                 # noqa: E402
from ps1play.learn.brain_client import BrainClient  # noqa: E402
from r57_lib import PassageCounter, run_episode, jsave    # noqa: E402

C1 = os.path.join(REPO, "data", "learn", "flappy_student_feat_r56_c1.npz")
SEEDS = [(6, 6000), (30, 4500), (60, 4500), (90, 4000), (210, 4000)]
REPS = 3
OUT = os.path.join(REPO, "scratch", "r57")


def main():
    env = FlappyEnv()
    env.reach_ready()
    rows = []
    brain = BrainClient(C1)
    try:
        for k, budget in SEEDS:
            for rep in range(REPS):
                pc = PassageCounter()
                r = run_episode(env, brain, k, budget,
                                passage=pc, tag=f"c1_repro_k{k}_r{rep}")
                r.pop("passage_events", None)
                rows.append(r)
                print(json.dumps(r), flush=True)
    finally:
        brain.close()
    env.close()

    agg = {}
    for k, _b in SEEDS:
        pipes = [r["pipes"] for r in rows if r["k"] == k]
        agg[k] = {"pipes": pipes, "mean": round(sum(pipes) / len(pipes), 2),
                  "results": sorted({r["result"] for r in rows
                                     if r["k"] == k})}
    rep = {"round": "R57 P0", "artifact": C1,
           "sha256": __import__("hashlib").sha256(
               open(C1, "rb").read()).hexdigest(),
           "protocol": "3 restored episodes per dev seed, one boot",
           "rows": rows, "agg": agg,
           "total_pipes": sum(r["pipes"] for r in rows),
           "r56_reported_c1": {"k6": 51, "k30": 37, "k60": 38,
                               "k90": 34, "k210": 13, "total": 173}}
    jsave(os.path.join(OUT, "r57c_repro.json"), rep)
    print(json.dumps(agg, indent=2), flush=True)
    print("TOTAL:", rep["total_pipes"], "(R56 reported 173)", flush=True)


if __name__ == "__main__":
    main()
