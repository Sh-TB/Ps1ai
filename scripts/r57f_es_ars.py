#!/usr/bin/env python3
"""r57f_es_ars.py — R57 P3 arm C: Augmented Random Search on the REAL
emulator, student-only (teacher import-blocked + traced).

Why ARS first (the review's evidence-grounded order): the episodic
objective (visually confirmed pipes) is directly measurable; the policy
is tiny (1,466 params); the environment is deterministic per
(anchor, k, actions) within a boot, so paired +/- rollouts give exact
contrasts; and ARS never differentiates through the saturated BC logits
that broke the earlier PPO attempts.

Algorithm (ARS V2, linear utility):
  for iter t:
    sample N directions delta_i ~ N(0, I) in the flat parameter space
    for each: evaluate theta +/- sigma*delta_i on ONE training episode
      (k alternates 6/60 by iteration parity; budget 6000)
      fitness = visually confirmed pipes (PassageCounter)
    rank the 2N returns, take the top b, utilities u_j = (b-j+1)/b
    theta += (alpha / (b * sigma_R)) * sum_j u_j * S_j * delta_j
      S_j = r+ - r-, sigma_R = std of the 2N returns (floor 1.0)

Resume: scratch/r57/es_state.json (+ theta .npz) after EVERY iteration.
The bootstrap artifact is NEVER written by this script.

Usage:
  python3 scripts/r57f_es_ars.py --iters 2          # run 2 iterations
  python3 scripts/r57f_es_ars.py --iters 2 --fresh  # restart from theta0
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

from ps1play.learn.games import FlappyEnv                  # noqa: E402
from ps1play.learn.policy import TinyMLP                   # noqa: E402
from ps1play.learn import student_only as SO               # noqa: E402
from r57_lib import PassageCounter                         # noqa: E402

SCR = os.path.join(REPO, "scratch", "r57")
DEFAULT_INIT = os.path.join(REPO, "data", "learn",
                            "r57_bootstrap_bc.npz")
STATE = os.path.join(SCR, "es_state.json")
THETA = os.path.join(SCR, "es_theta.npz")

SIGMA = 0.03
ALPHA = 0.015
N_DIRS = 6
TOP_B = 4
TRAIN_BUDGET = 10000   # the mission frame budget: 50+ pipes headroom
TRAIN_SEEDS = [6, 60]


class FlatPolicy:
    """The bootstrap TinyMLP with flat get/set for ARS — the EXACT
    Brain.act decision path (artifact norm + v7 observer features +
    the policy's own history), in-process, frames only."""

    def __init__(self, artifact):
        self.net, meta = TinyMLP.load_artifact(artifact)
        self.meta = meta
        norm = meta.get("norm", {})
        self.mean = (np.asarray(norm["mean"], dtype=np.float32)
                     if "mean" in norm else None)
        self.std = (np.asarray(norm["std"], dtype=np.float32)
                    if "std" in norm else None)
        self.names = ["W1", "b1", "W2", "b2"]
        self.sizes = [self.net.W1.size, self.net.b1.size,
                      self.net.W2.size, self.net.b2.size]
        self.shapes = [self.net.W1.shape, self.net.b1.shape,
                       self.net.W2.shape, self.net.b2.shape]
        self._obs = None

    def get(self):
        return np.concatenate([
            getattr(self.net, n).ravel().astype(np.float64)
            for n in self.names])

    def set(self, theta):
        off = 0
        for n, sh, sz in zip(self.names, self.shapes, self.sizes):
            setattr(self.net, n,
                    theta[off:off + sz].astype(np.float32).reshape(sh))
            off += sz

    def reset_obs(self):
        self._obs = None

    def vector(self, small):
        """The exact decision vector (v7 features + artifact norm) —
        the PPO arm reuses the same sensory pathway. Read-only (does
        NOT advance the policy history; the PPO loop owns it)."""
        from ps1play.learn import visual_only as VO
        if self._obs is None:
            self._obs = VO.BirdObserverV7()
            self._gtr = VO.GapTrackerV7()
            self._since_flap, self._flap_run = 99, 0
            self._last_gc, self._since_gap = -1.0, 40
            self._prev_action = None
        by_obs, vy_obs = self._obs.step(small, self._prev_action)
        gc_raw, dx, g0, g1, _b = VO._flappy_gap_raw2(small, by_hint=by_obs)
        gc_obs = self._gtr.step((gc_raw, g0, g1, dx + 160.0))
        x = VO.features_flappy_v7(
            small, by_obs, vy_obs, since_flap=self._since_flap,
            last_gc=self._last_gc, since_gap=self._since_gap,
            flap_run=self._flap_run, gc_obs=gc_obs)
        if self.mean is not None:
            x = (x - self.mean) / (self.std + 1e-6)
        self._gc_obs_pending = gc_obs
        return x

    def observe_history(self, action):
        """Advance the policy-owned history exactly like Brain.act."""
        self._prev_action = action
        if action == "FLAP":
            self._since_flap = 0
            self._flap_run = min(self._flap_run + 1, 9)
        else:
            self._since_flap = min(self._since_flap + 1, 99)
            self._flap_run = 0
        gc_obs = getattr(self, "_gc_obs_pending", None)
        if gc_obs is not None:
            self._last_gc = float(gc_obs)
            self._since_gap = 0
        else:
            self._since_gap = min(self._since_gap + 1, 40)

    def act(self, small):
        from ps1play.learn import visual_only as VO
        if self._obs is None:
            self._obs = VO.BirdObserverV7()
            self._gtr = VO.GapTrackerV7()
            self._since_flap, self._flap_run = 99, 0
            self._last_gc, self._since_gap = -1.0, 40
            self._prev_action = None
        by_obs, vy_obs = self._obs.step(small, self._prev_action)
        gc_raw, dx, g0, g1, _b = VO._flappy_gap_raw2(small,
                                                     by_hint=by_obs)
        gc_obs = self._gtr.step((gc_raw, g0, g1, dx + 160.0))
        x = VO.features_flappy_v7(
            small, by_obs, vy_obs, since_flap=self._since_flap,
            last_gc=self._last_gc, since_gap=self._since_gap,
            flap_run=self._flap_run, gc_obs=gc_obs)
        if self.mean is not None:
            x = (x - self.mean) / (self.std + 1e-6)
        out, _ = self.net.forward(x.reshape(1, -1))
        action = "FLAP" if int(np.argmax(out[0])) == 1 else "HOVER"
        self._prev_action = action
        if action == "FLAP":
            self._since_flap = 0
            self._flap_run = min(self._flap_run + 1, 9)
        else:
            self._since_flap = min(self._since_flap + 1, 99)
            self._flap_run = 0
        if gc_obs is not None:
            self._last_gc = float(gc_obs)
            self._since_gap = 0
        else:
            self._since_gap = min(self._since_gap + 1, 40)
        return action


def rollout(env, policy, k, budget):
    """One student-only training episode. Visual-only: the PassageCounter
    is the score, FlappyEnv.game_over the death. NO assisted reads."""
    from ps1play.learn.games import _small_rgb
    from ps1play.learn.perception import (flappy_bird_y,
                                          flappy_green_mask,
                                          flappy_gap_target_r15)
    env.start_episode(k)
    policy.reset_obs()
    pc = PassageCounter()
    t0 = time.time()
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


def utilities_2n(ranks, b):
    """Linear utilities over the top-b of 2N directions."""
    u = np.zeros(len(ranks))
    for j, i in enumerate(sorted(range(len(ranks)),
                                 key=lambda i: -ranks[i])[:b]):
        u[i] = (b - j) / b
    return u


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=1)
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--max-seconds", type=int, default=480,
                    help="graceful foreground chunk limit")
    ap.add_argument("--max-rollouts", type=int, default=0,
                    help="optional per-call rollout cap (0 = none)")
    ap.add_argument("--init", default=DEFAULT_INIT)
    ap.add_argument("--state", default="",
                    help="state file name inside scratch/r57 (default "
                         "es_state.json)")
    ap.add_argument("--seeds-per-cand", type=int, default=1,
                    help="rollout seeds per candidate (2 = mean fitness "
                         "over the pair = the discriminating protocol)")
    a = ap.parse_args()
    SCR = os.path.join(REPO, "scratch", "r57")
    STATE = os.path.join(SCR, a.state or "es_state.json")
    THETA = STATE.replace(".json", ".npz")

    trace = SO.NoTeacherTrace(os.path.join(
        SCR, f"noteacher_trace_es_{int(time.time())}.jsonl"))
    SO.install_teacher_blocker(trace)
    trace.event("ES_START", iters=a.iters, sigma=SIGMA, alpha=ALPHA,
                n_dirs=N_DIRS)

    env = FlappyEnv()
    env.reach_ready()
    pol = FlatPolicy(a.init)
    theta = pol.get()
    n_params = len(theta)
    it0, hist, cum = 0, [], {"episodes": 0, "frames": 0}
    # mid-iteration state: the delta matrix + the returns gathered so far
    deltas = None
    pend = None          # {"iter": t, "k": k, "rp": {i: r}, "rm": {i: r}}
    rng_state = None
    if os.path.exists(STATE) and not a.fresh:
        with open(STATE) as f:
            st = json.load(f)
        z = np.load(THETA)
        theta = z["theta"].astype(np.float64)
        it0, hist, cum = st["iter"], st["history"], st["cum"]
        if st.get("pend"):
            pz = np.load(os.path.join(SCR, "es_pend.npz"))
            deltas = pz["deltas"].astype(np.float64)
            pend = st["pend"]
            rng_state = st.get("rng_state")
        print(f"resume at iter {it0} ({len(hist)} rows; pend="
              f"{bool(pend)})", flush=True)

    budget_iters = it0 + a.iters
    cum0 = cum["episodes"]
    while True:
        if pend is None:
            if it0 >= budget_iters:
                break
            rng = np.random.default_rng(57 + it0 * 1_000_003)
            t = it0
            deltas = np.asarray([rng.standard_normal(n_params)
                                 for _ in range(N_DIRS)])
            k = TRAIN_SEEDS[t % 2]
            pend = {"iter": t, "k": k, "rp": {}, "rm": {},
                    "rp2": {}, "rm2": {}}
            pol.set(theta)
        t = pend["iter"]
        k = pend["k"]
        pol.set(theta)
        t_iter = time.time()
        t_call = time.time()
        chunk_end = False
        for i in range(N_DIRS):
            for sign, tag in ((+1.0, "plus"), (-1.0, "minus")):
                key = "rp" if sign > 0 else "rm"
                if str(i) in pend[key]:
                    continue
                pol.set(theta + sign * SIGMA * deltas[i])
                r, steps, wall = rollout(env, pol, k, TRAIN_BUDGET)
                if a.seeds_per_cand == 2:
                    k2 = TRAIN_SEEDS[(TRAIN_SEEDS.index(k) + 1) % 2]
                    r2, steps2, wall2 = rollout(env, pol, k2, TRAIN_BUDGET)
                    trace.event("ROLLOUT", iter=t, dir=i, sign=tag,
                                k=k2, pipes=r2, steps=steps2, wall_s=wall2)
                    print(json.dumps({"iter": t, "dir": i, "sign": tag,
                                      "k": k2, "pipes": r2,
                                      "steps": steps2, "wall_s": wall2}),
                          flush=True)
                    cum["episodes"] += 1
                    cum["frames"] += steps2
                    pend["rp2" if sign > 0 else "rm2"][str(i)] = int(r2)
                    r = (r + r2) / 2.0   # mean fitness over the pair
                pend[key][str(i)] = float(r)
                cum["episodes"] += 1
                cum["frames"] += steps
                trace.event("ROLLOUT", iter=t, dir=i, sign=tag, k=k,
                            pipes=r, steps=steps, wall_s=wall)
                print(json.dumps({"iter": t, "dir": i, "sign": tag,
                                  "k": k, "pipes": r, "steps": steps,
                                  "wall_s": wall}), flush=True)
                # persist mid-iteration progress so a foreground chunk
                # boundary loses nothing
                np.savez_compressed(THETA, theta=theta.astype(np.float32))
                np.savez_compressed(
                    os.path.join(SCR, "es_pend.npz"),
                    deltas=deltas.astype(np.float32))
                with open(STATE, "w") as f:
                    json.dump({"iter": it0, "history": hist, "cum": cum,
                               "pend": pend, "sigma": SIGMA,
                               "alpha": ALPHA, "n_dirs": N_DIRS,
                               "top_b": TOP_B,
                               "train_seeds": TRAIN_SEEDS,
                               "theta_sha256": SO.sha256_file(THETA)},
                              f, indent=2)
                if (time.time() - t_call > a.max_seconds
                        or (a.max_rollouts > 0
                            and cum["episodes"] - cum0 >= a.max_rollouts)):
                    chunk_end = True
                    break
        if chunk_end:
            print("CHUNK_END", json.dumps({"iter": t, "done": [
                int(x) for x in list(pend["rp"].keys())
                + list(pend["rm"].keys())]}), flush=True)
            break
        # ---- iteration complete: the ARS update ----
        rp = {int(i): r for i, r in pend["rp"].items()}
        rm = {int(i): r for i, r in pend["rm"].items()}
        rets = ([(i, +1, rp[i]) for i in rp] + [(i, -1, rm[i]) for i in rm])
        ranks = [max(rp.get(i, 0), rm.get(i, 0)) for i in range(N_DIRS)]
        S = np.asarray([rp.get(i, 0) - rm.get(i, 0)
                        for i in range(N_DIRS)])
        u = utilities_2n(np.asarray(ranks), TOP_B)
        all_r = np.asarray([r for _i, _s, r in rets], dtype=np.float64)
        sigma_r = max(all_r.std(), 1.0)
        upd = np.zeros_like(theta)
        for i in range(N_DIRS):
            if u[i] > 0:
                upd += u[i] * S[i] * deltas[i]
        theta = theta + (ALPHA / (TOP_B * sigma_r)) * upd
        pol.set(theta)
        row = {"iter": t, "k": k,
               "seeds_per_cand": a.seeds_per_cand,
               "returns": [round(r, 2) for _i, _s, r in rets],
               "mean_ret": round(float(all_r.mean()), 2),
               "max_ret": int(all_r.max()),
               "sigma_r": round(float(sigma_r), 2),
               "upd_norm": round(float(np.linalg.norm(upd)), 4),
               "wall_s": round(time.time() - t_iter, 1)}
        hist.append(row)
        print("ITER:", json.dumps(row), flush=True)
        trace.event("ITER_DONE", **row)
        np.savez_compressed(THETA, theta=theta.astype(np.float32))
        it0 = t + 1
        pend = None
        if os.path.exists(os.path.join(SCR, "es_pend.npz")):
            os.remove(os.path.join(SCR, "es_pend.npz"))
        with open(STATE, "w") as f:
            json.dump({"iter": it0, "history": hist, "cum": cum,
                       "pend": None, "sigma": SIGMA, "alpha": ALPHA,
                       "n_dirs": N_DIRS, "top_b": TOP_B,
                       "train_seeds": TRAIN_SEEDS,
                       "theta_sha256": SO.sha256_file(THETA)}, f, indent=2)
    env.close()
    trace.event("ES_STOP", iters_run=len(hist))
    print("TRACE_SHA:", trace.finish())


if __name__ == "__main__":
    main()
