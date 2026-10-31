#!/usr/bin/env python3
"""r59b_test.py — the R59 fresh-TEST evaluator: chunked, resumable,
persist-per-episode, teacher-off (blocked import + hashed trace per
process).

Protocol (committed in data/learn/r59_seed_splits.json BEFORE any
collection):
  * 20 unseen seeds (multiples-of-4 rule, all prior uses excluded),
  * candidate r59_soup_e6a010.npz n=3,
  * references n=1: r58_dir2p_true.npz (the R58 champion / the soup
    base) and flappy_student_feat_r56_c1.npz (the frozen R56 ref),
  * budget 10000, the single-source-of-truth PassageCounter,
  * rows persist to scratch/r57/r59_test_rows.jsonl; resume skips done
    (model, k, rep) triples.

Usage: python3 scripts/r59b_test.py --seconds 500
Repeat until it prints ALL_DONE.
"""
import argparse
import json
import os
import sys
import time

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.learn.games import FlappyEnv                  # noqa: E402
from ps1play.learn import student_only as SO               # noqa: E402
from r57f_es_ars import FlatPolicy, rollout                # noqa: E402

SCR = os.path.join(REPO, "scratch", "r57")
ROWS = os.path.join(SCR, "r59_test_rows.jsonl")
DATA = os.path.join(REPO, "data", "learn")
BUDGET = 10000

PLAN = [("r59_soup_e6a010.npz", 3),
        ("r58_dir2p_true.npz", 1),
        ("flappy_student_feat_r56_c1.npz", 1)]


def load_done():
    done = set()
    if os.path.exists(ROWS):
        with open(ROWS) as f:
            for line in f:
                try:
                    r = json.loads(line)
                    done.add((r["model"], r["k"], r["rep"]))
                except Exception:
                    pass
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=500)
    a = ap.parse_args()

    with open(os.path.join(DATA, "r59_seed_splits.json")) as f:
        splits = json.load(f)
    seeds = splits["test_never_used_before_this_round"]

    todo = []
    for model, reps in PLAN:
        for k in seeds:
            for rep in range(reps):
                todo.append((model, k, rep))
    done = load_done()
    todo = [t for t in todo if t not in done]
    if not todo:
        print("ALL_DONE")
        return

    trace = SO.NoTeacherTrace(os.path.join(
        SCR, f"noteacher_trace_r59test_{int(time.time())}.jsonl"))
    SO.install_teacher_blocker(trace)
    trace.event("R59_TEST_CHUNK", pending=len(todo))
    print(f"pending episodes: {len(todo)}", flush=True)

    env = FlappyEnv()
    env.reach_ready()
    cache = {}
    t0 = time.time()
    stopped = False
    for model, k, rep in todo:
        if time.time() - t0 > a.seconds and done:
            stopped = True
            break
        if model not in cache:
            art = os.path.join(DATA, model)
            cache[model] = FlatPolicy(art)
        pol = cache[model]
        pipes, steps, wall = rollout(env, pol, k, BUDGET)
        row = {"model": model, "k": int(k), "rep": rep,
               "pipes": int(pipes), "steps": int(steps),
               "result": "alive" if steps >= BUDGET else "death",
               "wall_s": wall, "ts": int(time.time())}
        with open(ROWS, "a") as f:
            f.write(json.dumps(row) + "\n")
        done.add((model, k, rep))
        trace.event("R59_TEST_EPISODE", **{kk: row[kk] for kk in
                                           ("model", "k", "rep",
                                            "pipes", "steps")})
        print(json.dumps(row), flush=True)
    env.close()
    print("TRACE", trace.finish(), flush=True)
    print("ALL_DONE" if not stopped else f"CHUNK_STOPPED "
          f"({len(load_done())}/{len(PLAN) * 20 * 1 + 40} rows)",
          flush=True)


if __name__ == "__main__":
    main()
