#!/usr/bin/env python3
"""r58d_lineage_reval.py — re-validate the r57 lineage dev-family numbers
under the clean session protocol (fresh boots, deterministic episodes,
hashed no-teacher traces).

Motivation (the r58 finding): the champion's 24 TEST numbers, k90=68 and
k210=13 reproduce EXACTLY, but the ARS iter-0 pair-eval claims k6=87 and
k60=87 do NOT (k6 = 63 death@7345 through BOTH decision paths and
restore #1). This script re-measures the dev family for all three
lineage models so the r58 evidence carries only reproducible numbers.
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

from ps1play.learn.games import FlappyEnv                  # noqa: E402
from ps1play.learn import student_only as SO               # noqa: E402
from r57f_es_ars import FlatPolicy, rollout                # noqa: E402

import argparse

SCR = os.path.join(REPO, "scratch", "r57")
DATA = os.path.join(REPO, "data", "learn")

MODELS = {
    "r57_es2_dir2p": {"seeds": [60, 12, 90]},
    "r57_si_v1": {"seeds": [6, 60, 90]},
    "r57_bootstrap_bc": {"seeds": [6, 60, 90]},
}
BUDGET = 10000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="all",
                    help="comma list or 'all'")
    a = ap.parse_args()
    names = (list(MODELS) if a.models == "all"
             else [x.strip() for x in a.models.split(",")])
    out_path = os.path.join(SCR, "r58d_lineage_reval.json")
    results = {}
    if os.path.exists(out_path):
        with open(out_path) as f:
            results = json.load(f)
    for name in names:
        if name in results:
            print(f"skip {name} (done)", flush=True)
            continue
        spec = MODELS[name]
        art = os.path.join(DATA, f"{name}.npz")
        trace = SO.NoTeacherTrace(os.path.join(
            SCR, f"noteacher_trace_r58d_{name}.jsonl"))
        SO.install_teacher_blocker(trace)
        trace.event("REVAL_START", model=name, seeds=spec["seeds"])
        env = FlappyEnv()
        env.reach_ready()
        pol = FlatPolicy(art)
        rows = []
        for k in spec["seeds"]:
            r, steps, wall = rollout(env, pol, k, BUDGET)
            rows.append({"k": k, "pipes": int(r), "steps": int(steps),
                         "wall_s": wall})
            trace.event("EPISODE", k=k, pipes=int(r), steps=int(steps))
            print(f"{name} k{k}: {r} pipes @ {steps}", flush=True)
        env.close()
        sha = trace.finish()
        results[name] = {"rows": rows,
                         "no_teacher_trace_sha256": sha,
                         "model_sha256": SO.sha256_file(art)}
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2)
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
