#!/usr/bin/env python3
"""r58_ars.py — ARS round 2 on the REAL emulator, student-only.

Round R58 continues R57's ARS from the PROVENANCE-CORRECTED base
r58_dir2p_true.npz (the reconstructed iter-0 dir-2-plus sample —
r58f proved the r57 champion npz was a mis-save; the true candidate
scores 87/87 on k6/k60 and 42 on k210, teacher-level).

r58 protocol hardening (the lesson of the r57 save incident):
  * fitness = mean over the fixed VAL pair (k90, k210) — the two seeds
    with the largest verified headroom (68 / 42 vs the 10000-frame
    budget ceiling ~87);
  * THE CANDIDATE ARTIFACT IS SAVED AT SELECTION TIME — the exact theta
    whose rollouts produced the iteration's returns is written to
    data/learn/r58_cand_t{t}.npz in the same block, before any gate;
  * every promotion requires a full clean re-eval (r58 gate script),
    never the fitness numbers alone.

Everything else is the r57f ARS V2 verbatim: sigma 0.03, alpha 0.015,
6 directions, top-4, linear utilities, mid-iteration persistence,
teacher import-blocked + hashed traces, in-process FlatPolicy decision
path (proven byte-identical to the deployed BrainClient path on real
episodes — r58b replay: 0/7345 mismatches; k6/k60/k72/k195 exact
reproductions).

Usage:
  python3 scripts/r58_ars.py --iters 2            # resume-safe chunks
  python3 scripts/r58_ars.py --iters 2 --fresh    # restart from base
"""
import argparse
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
from r57f_es_ars import (FlatPolicy, rollout, utilities_2n,  # noqa: E402
                         SIGMA, ALPHA, N_DIRS, TOP_B)

SCR = os.path.join(REPO, "scratch", "r57")
DATA = os.path.join(REPO, "data", "learn")
BASE = os.path.join(DATA, "r58_dir2p_true.npz")
STATE = os.path.join(SCR, "es_state_r58.json")
THETA = os.path.join(SCR, "es_theta_r58.npz")
FITNESS_SEEDS = [90, 210]          # the VAL pair, fixed before any run
TRAIN_BUDGET = 10000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=1)
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--max-seconds", type=int, default=480)
    ap.add_argument("--init", default=BASE)
    a = ap.parse_args()

    trace = SO.NoTeacherTrace(os.path.join(
        SCR, f"noteacher_trace_r58ars_{int(time.time())}.jsonl"))
    SO.install_teacher_blocker(trace)
    trace.event("R58_ES_START", iters=a.iters, sigma=SIGMA,
                alpha=ALPHA, n_dirs=N_DIRS, fitness_seeds=FITNESS_SEEDS)

    env = FlappyEnv()
    env.reach_ready()
    pol = FlatPolicy(a.init)
    theta = pol.get()
    n_params = len(theta)
    it0, hist, cum = 0, [], {"episodes": 0, "frames": 0}
    deltas, pend = None, None
    if os.path.exists(STATE) and not a.fresh:
        with open(STATE) as f:
            st = json.load(f)
        theta = np.load(THETA)["theta"].astype(np.float64)
        it0, hist, cum = st["iter"], st["history"], st["cum"]
        if st.get("pend"):
            pz = np.load(os.path.join(SCR, "es_pend_r58.npz"))
            deltas = pz["deltas"].astype(np.float64)
            pend = st["pend"]
        print(f"resume at iter {it0} ({len(hist)} rows; "
              f"pend={bool(pend)})", flush=True)

    budget_iters = it0 + a.iters
    cum0 = cum["episodes"]
    while True:
        if pend is None:
            if it0 >= budget_iters:
                break
            rng = np.random.default_rng(58 + it0 * 1_000_003)
            t = it0
            deltas = np.asarray([rng.standard_normal(n_params)
                                 for _ in range(N_DIRS)])
            pend = {"iter": t, "rp": {}, "rm": {},
                    "rp2": {}, "rm2": {}}
        t = pend["iter"]
        pol.set(theta)
        t_iter = time.time()
        t_call = time.time()
        chunk_end = False
        for i in range(N_DIRS):
            for sign, tag in ((+1.0, "plus"), (-1.0, "minus")):
                key = "rp" if sign > 0 else "rm"
                key2 = "rp2" if sign > 0 else "rm2"
                if str(i) in pend[key]:
                    continue
                pol.set(theta + sign * SIGMA * deltas[i])
                acc = 0.0
                for k in FITNESS_SEEDS:
                    r, steps, wall = rollout(env, pol, k, TRAIN_BUDGET)
                    acc += r
                    cum["episodes"] += 1
                    cum["frames"] += steps
                    trace.event("ROLLOUT", iter=t, dir=i, sign=tag,
                                k=k, pipes=int(r), steps=int(steps),
                                wall_s=wall)
                    print(json.dumps({"iter": t, "dir": i, "sign": tag,
                                      "k": k, "pipes": int(r),
                                      "steps": int(steps),
                                      "wall_s": wall}), flush=True)
                fit = acc / len(FITNESS_SEEDS)
                pend[key][str(i)] = float(fit)
                pend[key2][str(i)] = int(acc)
                # persist mid-iteration progress
                np.savez_compressed(THETA,
                                    theta=theta.astype(np.float32))
                np.savez_compressed(
                    os.path.join(SCR, "es_pend_r58.npz"),
                    deltas=deltas.astype(np.float32))
                with open(STATE, "w") as f:
                    json.dump({"iter": it0, "history": hist, "cum": cum,
                               "pend": pend, "sigma": SIGMA,
                               "alpha": ALPHA, "n_dirs": N_DIRS,
                               "top_b": TOP_B,
                               "fitness_seeds": FITNESS_SEEDS,
                               "base": os.path.basename(a.init),
                               "theta_sha256":
                                   SO.sha256_file(THETA)}, f, indent=2)
                if (time.time() - t_call > a.max_seconds):
                    chunk_end = True
                    break
            if chunk_end:
                break
        if chunk_end:
            print("CHUNK_END", json.dumps({"iter": t}), flush=True)
            break
        # ---- iteration complete: the ARS V2 update ----
        rp = {int(i): r for i, r in pend["rp"].items()}
        rm = {int(i): r for i, r in pend["rm"].items()}
        ranks = np.asarray([rp.get(i, 0) + rm.get(i, 0)
                            for i in range(N_DIRS)])
        S = np.asarray([rp.get(i, 0) - rm.get(i, 0)
                        for i in range(N_DIRS)])
        u = utilities_2n(ranks, TOP_B)
        all_r = np.asarray([rp.get(i, 0), rm.get(i, 0)],
                           dtype=np.float64).ravel()
        sigma_r = max(all_r.std(), 1.0)
        upd = np.zeros_like(theta)
        for i in range(N_DIRS):
            if u[i] > 0:
                upd += u[i] * S[i] * deltas[i]
        theta_new = theta + (ALPHA / (TOP_B * sigma_r)) * upd
        pol.set(theta_new)
        # ---- SAVE AT SELECTION TIME: the exact evaluated update ----
        cand_path = os.path.join(DATA, f"r58_cand_t{t}.npz")
        names = ["W1", "b1", "W2", "b2"]
        off, rebuilt = 0, {}
        base_z = np.load(a.init)
        for nm in names:
            sh = base_z[nm].shape
            sz = base_z[nm].size
            rebuilt[nm] = theta_new[off:off + sz].astype(
                np.float32).reshape(sh)
            off += sz
        np.savez_compressed(cand_path, **rebuilt)
        shutil.copyfile(a.init + ".json", cand_path + ".json")
        row = {"iter": t,
               "rp": [round(float(rp.get(i, 0)), 2) for i in
                      range(N_DIRS)],
               "rm": [round(float(rm.get(i, 0)), 2) for i in
                      range(N_DIRS)],
               "mean_ret": round(float(all_r.mean()), 2),
               "max_ret": round(float(all_r.max()), 2),
               "sigma_r": round(float(sigma_r), 2),
               "upd_norm": round(float(np.linalg.norm(upd)), 4),
               "step_norm": round(float(np.linalg.norm(
                   theta_new - theta)), 4),
               "candidate": os.path.basename(cand_path),
               "candidate_sha256": SO.sha256_file(cand_path),
               "wall_s": round(time.time() - t_iter, 1)}
        hist.append(row)
        print("ITER:", json.dumps(row), flush=True)
        trace.event("ITER_DONE", **{k: v for k, v in row.items()})
        np.savez_compressed(THETA, theta=theta_new.astype(np.float32))
        theta = theta_new
        it0 = t + 1
        pend = None
        if os.path.exists(os.path.join(SCR, "es_pend_r58.npz")):
            os.remove(os.path.join(SCR, "es_pend_r58.npz"))
        with open(STATE, "w") as f:
            json.dump({"iter": it0, "history": hist, "cum": cum,
                       "pend": None, "sigma": SIGMA, "alpha": ALPHA,
                       "n_dirs": N_DIRS, "top_b": TOP_B,
                       "fitness_seeds": FITNESS_SEEDS,
                       "base": os.path.basename(a.init),
                       "theta_sha256": SO.sha256_file(THETA)}, f,
                      indent=2)
    env.close()
    trace.event("R58_ES_STOP", iters_run=len(hist))
    print("TRACE_SHA:", trace.finish())


if __name__ == "__main__":
    main()
