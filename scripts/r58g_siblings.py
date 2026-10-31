#!/usr/bin/env python3
"""r58g_siblings.py — reconstruct the r57 es2 iter-0 SIBLING candidates
(si_v1 + 0.03*delta_i and si_v1 - 0.03*delta_i, i = 0..5, i != 2-plus)
and measure each on the VAL pair (k90, k210) on the REAL emulator.

Why: the base (dir-2-plus) sits on a collapse plateau (r58 t0: zero
positive signal, k60 collapse). The es2 iter-0 record evaluated the
siblings only on (k6, k60); their (k90, k210) numbers were never
measured. If a sibling dominates (68, 42) without collapsing k6/k60,
it becomes the r58 ARS base.

Student-only: teacher import blocked + hashed traces. Results persist
per candidate (crunk-safe).
"""
import json
import os
import shutil
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.learn.games import FlappyEnv                  # noqa: E402
from ps1play.learn import student_only as SO               # noqa: E402
from r57f_es_ars import FlatPolicy, rollout, SIGMA, N_DIRS  # noqa: E402

DATA = os.path.join(REPO, "data", "learn")
SCR = os.path.join(REPO, "scratch", "r57")
SI = os.path.join(DATA, "r57_si_v1.npz")
OUT = os.path.join(SCR, "r58g_siblings.json")
SEEDS = [90, 210]
BUDGET = 10000


def flat(art):
    z = np.load(art)
    return np.concatenate([z[n].ravel().astype(np.float64)
                           for n in ["W1", "b1", "W2", "b2"]])


def save_theta(theta, path, meta_src):
    z = np.load(meta_src)
    off, rebuilt = 0, {}
    for nm in ["W1", "b1", "W2", "b2"]:
        sz = z[nm].size
        rebuilt[nm] = theta[off:off + sz].astype(np.float32) \
            .reshape(z[nm].shape)
        off += sz
    np.savez_compressed(path, **rebuilt)
    shutil.copyfile(meta_src + ".json", path + ".json")


def main():
    th_si = flat(SI)
    n = len(th_si)
    rng = np.random.default_rng(57 + 0 * 1_000_003)
    deltas = np.asarray([rng.standard_normal(n) for _ in range(N_DIRS)])

    cands = []
    for i in range(N_DIRS):
        for sign in (+1, -1):
            if i == 2 and sign == +1:
                continue          # the base itself (dir-2-plus)
            cands.append((f"dir{i}_{'p' if sign > 0 else 'm'}",
                          th_si + sign * SIGMA * deltas[i]))

    done = {}
    if os.path.exists(OUT):
        with open(OUT) as f:
            done = json.load(f)

    trace = SO.NoTeacherTrace(os.path.join(
        SCR, f"noteacher_trace_r58g_{int(time.time())}.jsonl"))
    SO.install_teacher_blocker(trace)
    trace.event("SIBLINGS_START", n=len(cands))

    env = FlappyEnv()
    env.reach_ready()
    pol = FlatPolicy(SI)
    for name, theta in cands:
        if name in done:
            print(f"skip {name}", flush=True)
            continue
        art = os.path.join(SCR, f"r58sib_{name}.npz")
        save_theta(theta, art, SI)
        pol.set(theta)
        rows = []
        for k in SEEDS:
            r, steps, wall = rollout(env, pol, k, BUDGET)
            rows.append({"k": k, "pipes": int(r), "steps": int(steps)})
            trace.event("ROLLOUT", cand=name, k=k, pipes=int(r),
                        steps=int(steps))
            print(json.dumps({"cand": name, "k": k, "pipes": int(r),
                              "steps": int(steps)}), flush=True)
        fit = sum(r["pipes"] for r in rows) / len(rows)
        done[name] = {"rows": rows, "fitness": fit,
                      "sha256": SO.sha256_file(art)}
        with open(OUT, "w") as f:
            json.dump(done, f, indent=2)
    env.close()
    trace.event("SIBLINGS_DONE")
    print("TRACE_SHA:", trace.finish())
    print(json.dumps(done, indent=1))


if __name__ == "__main__":
    main()
