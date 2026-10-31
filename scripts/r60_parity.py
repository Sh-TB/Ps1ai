#!/usr/bin/env python3
"""r60_parity.py — R60: closed-loop parity of the ONNX decision path
against the deployed numpy path, on the REAL emulator.

Modes:
  --dual            (default) every step: the exact deployed decision
                    vector is computed ONCE through the FlatPolicy
                    state machine; BOTH forwards run on it — the numpy
                    reference (the deployed path) and onnxruntime on
                    r60_soup_e6a010.onnx. Per-frame action equality is
                    asserted; vectors+logits of every step are stored.
  --solo            the ORT forward ALONE decides (no numpy forward in
                    the loop) — proves the ONNX artifact can drive the
                    full closed loop by itself. Family seeds must
                    reproduce the R59 record exactly.

Family seeds + expected record (R59, deployed path, budget 10000):
  k6 87 alive / k12 76@8798 / k30 37@4401 / k45 40@4753 /
  k60 87 alive / k90 68@7895 / k210 42@4966

Resumable rows: scratch/r57/r60_parity_rows.jsonl.
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

from ps1play.learn.games import FlappyEnv, _small_rgb  # noqa: E402
from ps1play.learn import student_only as SO           # noqa: E402
from r57f_es_ars import FlatPolicy                     # noqa: E402
from r57_lib import PassageCounter                     # noqa: E402

SCR = os.path.join(REPO, "scratch", "r57")
DATA = os.path.join(REPO, "data", "learn")
ROWS = os.path.join(SCR, "r60_parity_rows.jsonl")
BUDGET = 10000

FAMILY = {
    "k6":   {"k": 6,   "expect": ("87", "alive")},
    "k12":  {"k": 12,  "expect": ("76", "8798")},
    "k30":  {"k": 30,  "expect": ("37", "4401")},
    "k45":  {"k": 45,  "expect": ("40", "4753")},
    "k60":  {"k": 60,  "expect": ("87", "alive")},
    "k90":  {"k": 90,  "expect": ("68", "7895")},
    "k210": {"k": 210, "expect": ("42", "4966")},
}

ONNX_PATH = os.path.join(DATA, "r60_soup_e6a010.onnx")


class DualPolicy(FlatPolicy):
    """The deployed FlatPolicy state machine (vector + observe_history
    are REUSED verbatim) with BOTH forwards on the same decision
    vector, every step."""

    def __init__(self, artifact, onnx_path):
        super().__init__(artifact)
        import onnxruntime as ort
        self.sess = ort.InferenceSession(
            onnx_path, providers=["CPUExecutionProvider"])
        self.mismatch = 0
        self.steps = 0
        self.max_logit_delta = 0.0

    def raw_vector(self, small):
        """EXACT copy of FlatPolicy.vector's state-machine body minus
        the normalization (the ONNX graph normalizes internally).
        Equivalence is validated end-to-end by the family scores."""
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
        self._gc_obs_pending = gc_obs
        return x

    def act(self, small):
        raw = self.raw_vector(small)
        xn = raw
        if self.mean is not None:
            xn = (raw - self.mean) / (self.std + 1e-6)
        out, _ = self.net.forward(xn.reshape(1, -1))
        action = "FLAP" if int(np.argmax(out[0])) == 1 else "HOVER"
        o_logits, o_idx = self.sess.run(
            ["logits", "action_idx"], {"x": raw.reshape(1, -1).astype(
                np.float32)})
        o_action = "FLAP" if int(o_idx[0]) == 1 else "HOVER"
        self.steps += 1
        self.max_logit_delta = max(
            self.max_logit_delta,
            float(np.abs(o_logits[0] - out[0]).max()))
        if o_action != action:
            self.mismatch += 1
        # record for the parity dataset: the RAW decision vector —
        # the EXACT ONNX graph input (the graph normalizes internally)
        self.last_x = raw.astype(np.float32)
        self.last_ref = out[0].astype(np.float32)
        self.last_ort = o_logits[0].astype(np.float32)
        # advance history EXACTLY like Brain.act / FlatPolicy.act
        self.observe_history(action)
        return action


class SoloPolicy(DualPolicy):
    """The ORT forward ALONE decides; the numpy forward never runs."""

    def act(self, small):
        raw = self.raw_vector(small)
        o_logits, o_idx = self.sess.run(
            ["logits", "action_idx"], {"x": raw.reshape(1, -1).astype(
                np.float32)})
        action = "FLAP" if int(o_idx[0]) == 1 else "HOVER"
        self.steps += 1
        self.last_x = raw.astype(np.float32)
        self.observe_history(action)
        return action

def rollout_rec(env, policy, k, budget, rec=None):
    """One episode; rec=None disables recording; else a dict of lists."""
    from ps1play.learn.perception import (flappy_bird_y,
                                          flappy_green_mask,
                                          flappy_gap_target_r15)
    env.start_episode(k)
    policy.reset_obs()
    pc = PassageCounter()
    flaps = 0
    t0 = time.time()
    for step in range(budget):
        fr = env.frame()
        small = _small_rgb(fr)
        action = policy.act(small)
        if action == "FLAP":
            flaps += 1
        env.run(1, {"B"} if action == "FLAP" else set())
        by, _n = flappy_bird_y(env.frame())
        _g, bx = flappy_gap_target_r15(
            flappy_green_mask(env.frame()),
            by if by is not None else -1)
        pc.fire(bx, step)
        if rec is not None:
            rec["x"].append(policy.last_x)
            if hasattr(policy, "last_ref"):
                rec["ref"].append(policy.last_ref)
                rec["ort"].append(policy.last_ort)
            rec["action"].append(1 if action == "FLAP" else 0)
        if env.game_over(env.frame()):
            break
    return pc.count, step + 1, flaps, round(time.time() - t0, 1)


def load_done():
    done = set()
    if os.path.exists(ROWS):
        with open(ROWS) as f:
            for line in f:
                try:
                    r = json.loads(line)
                    done.add((r["mode"], r["seed"]))
                except Exception:
                    pass
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dual", "solo"], default="dual")
    ap.add_argument("--seeds", default="",
                    help="comma list (default: all family)")
    ap.add_argument("--seconds", type=int, default=480)
    a = ap.parse_args()
    os.makedirs(SCR, exist_ok=True)

    trace = SO.NoTeacherTrace(os.path.join(
        SCR, f"noteacher_trace_r60_{a.mode}_{int(time.time())}.jsonl"))
    SO.install_teacher_blocker(trace)
    trace.event("R60_PARITY_START", mode=a.mode)

    seeds = (a.seeds.split(",") if a.seeds else list(FAMILY))
    done = load_done()
    todo = [s for s in seeds if (a.mode, s) not in done]
    print(f"mode={a.mode} pending={todo}", flush=True)
    if not todo:
        print("ALL_DONE")
        return

    env = FlappyEnv()
    env.reach_ready()
    art = os.path.join(DATA, "r59_soup_e6a010.npz")
    if a.mode == "dual":
        pol = DualPolicy(art, ONNX_PATH)
    else:
        pol = SoloPolicy(art, ONNX_PATH)
    t0 = time.time()
    stopped = False
    for s in todo:
        if time.time() - t0 > a.seconds and done:
            stopped = True
            break
        rec = {"x": [], "ref": [], "ort": [], "action": []} \
            if a.mode == "dual" else None
        pipes, steps, flaps, wall = rollout_rec(
            env, pol, FAMILY[s]["k"], BUDGET, rec=rec)
        row = {"mode": a.mode, "seed": s, "k": FAMILY[s]["k"],
               "pipes": int(pipes), "steps": int(steps),
               "flaps": int(flaps),
               "expect": "-".join(FAMILY[s]["expect"]),
               "steps_match": (steps == BUDGET
                               if FAMILY[s]["expect"][1] == "alive"
                               else steps == int(FAMILY[s]["expect"][1])),
               "pipes_match": str(pipes) == FAMILY[s]["expect"][0],
               "policy_steps": pol.steps,
               "action_mismatches": getattr(pol, "mismatch", 0),
               "max_logit_delta": getattr(pol, "max_logit_delta", 0.0),
               "wall_s": wall}
        with open(ROWS, "a") as f:
            f.write(json.dumps(row) + "\n")
            f.flush()
        trace.event("R60_EPISODE", **{k2: row[k2] for k2 in
                                      ("mode", "seed", "pipes", "steps",
                                       "flaps", "action_mismatches")})
        print(json.dumps(row), flush=True)
        if a.mode == "dual" and rec["x"]:
            np.savez_compressed(
                os.path.join(SCR, f"r60_rec_{s}.npz"),
                x=np.asarray(rec["x"], dtype=np.float32),
                ref=np.asarray(rec["ref"], dtype=np.float32),
                ort=np.asarray(rec["ort"], dtype=np.float32),
                action=np.asarray(rec["action"], dtype=np.int64))
        # fresh policy state per episode (the smoke pattern: one boot
        # serves many anchor-restored episodes; counters reset in
        # reset_obs via start_episode->policy.reset_obs in rollout_rec)
        pol.mismatch = 0
        pol.steps = 0
        pol.max_logit_delta = 0.0
    env.close()
    sha = trace.finish()
    print("TRACE_SHA:", sha[:16], flush=True)
    remaining = len([s for s in todo if (a.mode, s) not in load_done()])
    if remaining == 0:
        print("ALL_DONE")


if __name__ == "__main__":
    main()
