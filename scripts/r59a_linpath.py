#!/usr/bin/env python3
"""r59a_linpath.py — R59-A: the linear-path interpolation probe.

The R58 thrice-replicated finding (ARS round 2, sibling sweep, SI round
2): the base r58_dir2p_true is a SHARP local optimum — every tested
ONE-SHOT weight move either lifts mid-depth seeds while collapsing a
razor-edge (k6/k60 87-alive) or does nothing. One-shot moves sample
single points of weight space. The LINEAR PATH

    theta(alpha) = (1-alpha)*base + alpha*cand

samples a 1-D family between two WORKING policies (the base and the
gate-rejected SI fine-tunes e4/e6 whose full steps collapse k60 but
lift k12/k45). If the k60 collapse is not instantaneous along the path
while the k12/k45 gains arrive early, a soup point strictly better
than both endpoints exists. This move class was never tested.

Probe protocol (REAL emulator; the in-process FlatPolicy is the proven
0/7345-mismatch decision path; teacher import-blocked + hashed
no-teacher trace per process):
  1. razor seeds k6, k60 (the two budget-alive 87s that must not
     collapse),
  2. survivors -> k12, k45 (the SI-gain seeds),
  3. full family + regression gate only after that.

Resumable: rows appended to scratch/r59/linpath_results.json keyed by
(cand, alpha, k); one boot per invocation; --max-seconds graceful.
"""
import argparse
import hashlib
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
from r57_lib import PassageCounter                         # noqa: E402
from r57f_es_ars import FlatPolicy                         # noqa: E402

BASE = os.path.join(REPO, "data", "learn", "r58_dir2p_true.npz")
SCR = os.path.join(REPO, "scratch", "r59")
RESULTS = os.path.join(SCR, "linpath_results.json")

NAMES = ["W1", "b1", "W2", "b2"]


def flat(z):
    return np.concatenate([z[n].ravel().astype(np.float64)
                           for n in NAMES])


def save_theta(theta, template_art, path):
    z = np.load(template_art)
    out, off = {}, 0
    for n in NAMES:
        a = z[n]
        out[n] = theta[off:off + a.size].astype(np.float32) \
            .reshape(a.shape)
        off += a.size
    np.savez_compressed(path, **out)
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def rollout(env, policy, k, budget):
    from ps1play.learn.games import _small_rgb
    from ps1play.learn.perception import (flappy_bird_y,
                                          flappy_green_mask,
                                          flappy_gap_target_r15)
    env.start_episode(k)
    policy.reset_obs()
    pc = PassageCounter()
    t0 = time.time()
    step = 0
    for step in range(budget):
        fr = env.frame()
        small = _small_rgb(fr)
        action = policy.act(small)
        env.run(1, {"B"} if action == "FLAP" else set())
        by, _n = flappy_bird_y(env.frame())
        _g, bx = flappy_gap_target_r15(
            flappy_green_mask(env.frame()), by if by is not None else -1)
        pc.fire(bx, step)
        if env.game_over(env.frame()):
            break
    return pc.count, step + 1, round(time.time() - t0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", required=True)
    ap.add_argument("--alphas", required=True)
    ap.add_argument("--seeds", default="6,60")
    ap.add_argument("--budget", type=int, default=10000)
    ap.add_argument("--max-seconds", type=int, default=520)
    a = ap.parse_args()

    os.makedirs(SCR, exist_ok=True)
    rows = []
    if os.path.exists(RESULTS):
        rows = json.load(open(RESULTS))
    done = {(r["cand"], r["alpha"], r["k"]) for r in rows}

    cand_path = os.path.join(REPO, a.cand)
    cand_tag = os.path.basename(a.cand).replace(".npz", "")

    trace = SO.NoTeacherTrace(os.path.join(
        SCR, f"noteacher_lin_{int(time.time())}.jsonl"))
    SO.install_teacher_blocker(trace)
    trace.event("LIN_START", cand=cand_tag, alphas=a.alphas,
                seeds=a.seeds)

    th_base = flat(np.load(BASE))
    th_cand = flat(np.load(cand_path))
    u = th_cand - th_base
    print(f"|u|={np.linalg.norm(u):.4f} cand={cand_tag}", flush=True)

    env = FlappyEnv()
    env.reach_ready()
    pol = FlatPolicy(BASE)

    t_start = time.time()
    try:
        for alpha in [float(x) for x in a.alphas.split(",")]:
            theta = th_base + alpha * u
            art = os.path.join(
                SCR, f"lin_{cand_tag}_a{alpha:g}.npz")
            if not os.path.exists(art):
                art_sha = save_theta(theta, BASE, art)
            else:
                art_sha = hashlib.sha256(
                    open(art, "rb").read()).hexdigest()[:16]
            pol.set(theta)
            for k in [int(x) for x in a.seeds.split(",")]:
                if (cand_tag, alpha, k) in done:
                    continue
                if time.time() - t_start > a.max_seconds:
                    print("GRACE_STOP time budget", flush=True)
                    raise KeyboardInterrupt
                pipes, steps, wall = rollout(env, pol, k, a.budget)
                row = {
                    "cand": cand_tag, "alpha": alpha, "k": k,
                    "pipes": int(pipes), "steps": int(steps),
                    "result": ("alive" if steps >= a.budget
                               else "death"),
                    "budget": a.budget, "wall_s": wall,
                    "art": os.path.basename(art),
                    "art_sha256_16": art_sha,
                    "ts": int(time.time()),
                }
                rows.append(row)
                json.dump(rows, open(RESULTS, "w"), indent=1)
                trace.event("LIN_EPISODE", **{kk: row[kk] for kk in
                                              ("cand", "alpha", "k",
                                               "pipes", "steps")})
                print(json.dumps(row), flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        env.close()
        sha = trace.finish()
    print("TRACE_SHA", sha, flush=True)


if __name__ == "__main__":
    main()
