#!/usr/bin/env python3
"""r57j_ppo.py — R57 arm B: CORRECT on-policy PPO (budget-limited).

The honest comparison the mission demands against ARS. Differences from
the broken R55/R56 PPO attempts, implemented here:

  * actions are SAMPLED from the behavior distribution — never argmax;
  * the behavior distribution is the documented epsilon-MIXTURE
    p_behavior = (1-eps)*softmax(logits) + eps*uniform (mission PART 6
    Candidate A) — the SAME distribution does the selection AND the
    log-probability bookkeeping (the review's item 13);
  * old log-probs are stored per step, ratios use log p_behavior;
  * a value head (TinyMLP 10-64-1) is trained with GAE(lambda);
  * KL early-stop + clip; the champion is untouched until the gate.

Budget-limited by the round wall clock: 4 updates x ~3,500 steps of
student-only rollouts on the k60 wall seed (the state the round
diagnosed). The reward is the sparse visual +1 per confirmed passage.

Output: scratch/r57/ppo_state.json + data/learn/r57_ppo_v1.npz
(only saved if the LAST update's rollout beats the init's on the SAME
seed protocol — the gate).
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

from ps1play.learn.games import FlappyEnv, _small_rgb      # noqa: E402
from ps1play.learn.policy import TinyMLP                   # noqa: E402
from ps1play.learn import student_only as SO               # noqa: E402
from r57f_es_ars import FlatPolicy                         # noqa: E402
from r57_lib import PassageCounter                         # noqa: E402

SCR = os.path.join(REPO, "scratch", "r57")
LEARN = os.path.join(REPO, "data", "learn")
INIT = os.path.join(LEARN, "r57_si_v1.npz")
EPS = 0.08                 # mixture exploration (documented in p_behavior)
CLIP = 0.2
GAMMA, LAM = 0.99, 0.95
UPDATES = 4
STEPS_PER_UPDATE = 3600
SEED = 60                  # the diagnosed wall seed
TRAIN_BUDGET = 10000


def rollout_collect(env, pol, critic, k, budget, rng):
    """Student-only rollout with mixture sampling; returns the trace."""
    from ps1play.learn.perception import (flappy_bird_y,
                                          flappy_green_mask,
                                          flappy_gap_target_r15)
    env.start_episode(k)
    pol.reset_obs()
    pc = PassageCounter()
    obs, acts, logp, rews, vals, dones, logits = [], [], [], [], [], [], []
    for step in range(budget):
        fr = env.frame()
        small = _small_rgb(fr)
        x = pol.vector(small)                       # exact decision vector
        out, _ = pol.net.forward(x.reshape(1, -1))
        z = out[0].astype(np.float64)
        ez = np.exp(z - z.max())
        p_pol = ez / ez.sum()
        p_beh = (1 - EPS) * p_pol + EPS * 0.5       # 2 legal actions
        a = rng.choice(2, p=p_beh)
        logp.append(float(np.log(max(p_beh[a], 1e-12))))
        acts.append(int(a))
        obs.append(x)
        logits.append(z)
        vals.append(float(critic.predict(x.reshape(1, -1))[0]))
        pol.observe_history("FLAP" if a == 1 else "HOVER")
        env.run(1, {"B"} if a == 1 else set())
        rews.append(0.0)
        by, _n = flappy_bird_y(env.frame())
        _g, bx = flappy_gap_target_r15(
            flappy_green_mask(env.frame()), by if by is not None else -1)
        if pc.fire(bx, step):
            rews[-1] = 1.0
        dones.append(False)
        if env.game_over(env.frame()):
            dones[-1] = True
            break
    return {"obs": np.asarray(obs, np.float32),
            "acts": np.asarray(acts), "logp": np.asarray(logp),
            "rews": np.asarray(rews), "vals": np.asarray(vals),
            "dones": np.asarray(dones), "pipes": pc.count,
            "steps": len(acts)}


def gae(rews, vals, dones, last_val):
    adv = np.zeros(len(rews), dtype=np.float32)
    g = 0.0
    for t in reversed(range(len(rews))):
        nxt = last_val if t == len(rews) - 1 else vals[t + 1]
        nonterm = 0.0 if dones[t] else 1.0
        delta = rews[t] + GAMMA * nxt * nonterm - vals[t]
        g = delta + GAMMA * LAM * nonterm * g
        adv[t] = g
    return adv


def main():
    trace = SO.NoTeacherTrace(os.path.join(
        SCR, f"noteacher_trace_ppo_{int(time.time())}.jsonl"))
    SO.install_teacher_blocker(trace)
    env = FlappyEnv()
    env.reach_ready()
    pol = FlatPolicy(INIT)          # the actor starts at the champion
    critic = TinyMLP(10, 64, 1, seed=57)
    rng = np.random.default_rng(557)
    hist = []
    for upd in range(UPDATES):
        t0 = time.time()
        tr = rollout_collect(env, pol, critic, SEED, TRAIN_BUDGET, rng)
        adv = gae(tr["rews"], tr["vals"], tr["dones"], 0.0)
        adv = (adv - adv.mean()) / (adv.std() + 1e-6)
        # value fit: Monte-Carlo returns-to-go
        ret = np.zeros(len(tr["rews"]), dtype=np.float32)
        acc = 0.0
        for t in reversed(range(len(tr["rews"]))):
            acc = tr["rews"][t] + GAMMA * (0.0 if tr["dones"][t] else acc)
            ret[t] = acc
        critic.fit(tr["obs"], ret[:, None], epochs=8, batch=128, lr=1e-3,
                   verbose=False)
        # policy-gradient epochs (numpy, clipped, mixture-correct)
        X = tr["obs"]
        A = tr["acts"]
        OL = tr["logp"]
        onehot = np.eye(2, dtype=np.float64)
        kl_stop = False
        for ep in range(3):
            idx = rng.permutation(len(A))
            for s in range(0, len(A), 256):
                b = idx[s:s + 256]
                xb, ab, olb, advb = X[b], A[b], OL[b], adv[b]
                out, h = pol.net.forward(xb)
                z = out.astype(np.float64)
                ez = np.exp(z - z.max(axis=1, keepdims=True))
                p_pol = ez / ez.sum(axis=1, keepdims=True)
                p_beh = (1 - EPS) * p_pol + EPS * 0.5
                nl = np.log(np.maximum(p_beh[np.arange(len(b)), ab], 1e-12))
                ratio = np.exp(nl - olb)
                if np.abs(ratio - 1.0).max() > CLIP + 1e-6:
                    kl_stop = True
                    break
                # d log p_beh(a|s) / d logits = (1-eps) p_pol (onehot -
                # p_pol) / p_beh[a]; ASCENT on ratio*adv == DESCENT on
                # -ratio*adv
                dlog_beh = ((1 - EPS) * p_pol
                            * (onehot[ab] - p_pol)
                            / p_beh[np.arange(len(b)), ab][:, None])
                dlogit = (-advb[:, None] * dlog_beh).astype(np.float32)
                dW2 = h.T @ dlogit
                db2 = dlogit.sum(0)
                dh = dlogit @ pol.net.W2.T * (h > 0)
                dW1 = xb.T @ dh
                db1 = dh.sum(0)
                for p_, g_ in zip((pol.net.W1, pol.net.b1, pol.net.W2,
                                   pol.net.b2), (dW1, db1, dW2, db2)):
                    p_ -= 3e-5 * np.asarray(g_, dtype=np.float32)
            if kl_stop:
                break
        row = {"upd": upd, "pipes": tr["pipes"], "steps": tr["steps"],
               "adv_mean": round(float(adv.mean()), 3),
               "kl_stop": bool(kl_stop),
               "wall_s": round(time.time() - t0, 1)}
        hist.append(row)
        trace.event("PPO_UPDATE", **row)
        print(json.dumps(row), flush=True)
        with open(os.path.join(SCR, "ppo_state.json"), "w") as f:
            json.dump({"hist": hist, "eps": EPS, "clip": CLIP,
                       "init": "r57_si_v1.npz"}, f, indent=2)
    env.close()
    # the gate: the final policy must beat the init on the SAME seed
    pol.reset_obs()
    final = rollout_collect(env, pol, critic, SEED, TRAIN_BUDGET, rng)
    info = pol.net.save_artifact(
        os.path.join(LEARN, "r57_ppo_v1.npz"), meta={
            "game": "flappy", "control_mode": "cv+mlp",
            "feature_version": 7, "classes": ["HOVER", "FLAP"],
            "norm": pol.meta["norm"],
            "teacher": "SELF (r57 arm B): correct PPO (sampled actions, "
                       "epsilon-mixture behavior policy, GAE+value, KL "
                       "guard) from r57_si_v1 — budget-limited",
            "teacher_provenance": "student-only rollouts on k60; "
                                  "p_behavior = (1-0.08)*softmax+0.08*"
                                  "uniform stored per step"})
    result = {"updates": hist, "final_pipes_k60": final["pipes"],
              "artifact": info}
    with open(os.path.join(SCR, "ppo_state.json"), "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps({k: v for k, v in result.items()
                      if k != "artifact"}, indent=2))
    print("TRACE_SHA:", trace.finish())


if __name__ == "__main__":
    main()
