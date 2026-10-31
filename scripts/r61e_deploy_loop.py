#!/usr/bin/env python3
"""r61e_deploy_loop.py — R61 Section 7: the emulator-in-the-loop
validator that drives the REAL game through the INDEPENDENT deployment
package (the ONNX consumer in deployment/flappybird_policy/), with the
host-side perception as the documented adapter (INTERFACE.md).

Two policy interfaces are supported:
  * a deployment-package policy (has .predict(x)) — the runner owns a
    fresh BirdObserverV7 + GapTrackerV7 per episode and feeds the RAW
    v7 vector; the ONNX graph is the ONLY decider (no numpy forward
    exists in this path);
  * a reference FlatPolicy-style policy (has .act(small)) — the
    deployed numpy path, used for the baseline comparison rows.

Episode record (per mission Section 7): seed, policy hash, emulator
tag, result, pipes, frames, flaps, death reason, errors, action count,
trace hash, evidence reference. The runner never swallows environment
failures (LoopError) and never reuses perception state across episodes.
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

PKG = os.path.join(REPO, "deployment", "flappybird_policy")
if PKG not in sys.path:
    sys.path.insert(0, PKG)

from ps1play.learn.games import _small_rgb                  # noqa: E402
from ps1play.learn.perception import (                      # noqa: E402
    flappy_bird_y, flappy_gap_target_r15, flappy_green_mask)
from r57_lib import PassageCounter                          # noqa: E402

BUDGET = 10000


class LoopError(RuntimeError):
    """An environment failure during a closed-loop episode."""


# ------------------------------------------------------------------
# the host-side perception adapter (the ONLY place it exists for the
# deployment path; mirrors the deployed state machine exactly —
# vector BEFORE the action update, history AFTER it)
# ------------------------------------------------------------------
def build_vector(small, observer, tracker, since_flap, flap_run,
                 last_gc, since_gap, prev_action):
    """The RAW v7 decision vector from one small frame + the policy's
    own history. Returns (x_float32[10], pending_gc)."""
    from ps1play.learn import visual_only as VO
    by_obs, vy_obs = observer.step(small, prev_action)
    gc_raw, dx, g0, g1, _b = VO._flappy_gap_raw2(small, by_hint=by_obs)
    gc_obs = tracker.step((gc_raw, g0, g1, dx + 160.0))
    x = VO.features_flappy_v7(
        small, by_obs, vy_obs, since_flap=since_flap,
        last_gc=last_gc, since_gap=since_gap, flap_run=flap_run,
        gc_obs=gc_obs)
    return np.asarray(x, dtype=np.float32), gc_obs


def advance_history(action, since_flap, flap_run, last_gc, since_gap,
                    pending_gc):
    """The exact deployed history update (FlatPolicy.observe_history
    semantics). Returns (since_flap, flap_run, last_gc, since_gap)."""
    if action == "FLAP":
        since_flap = 0
        flap_run = min(flap_run + 1, 9)
    else:
        since_flap = min(since_flap + 1, 99)
        flap_run = 0
    if pending_gc is not None:
        last_gc = float(pending_gc)
        since_gap = 0
    else:
        since_gap = min(since_gap + 1, 40)
    return since_flap, flap_run, last_gc, since_gap


def fresh_perception():
    from ps1play.learn import visual_only as VO
    return (VO.BirdObserverV7(), VO.GapTrackerV7(),
            99, 0, -1.0, 40)  # observer, tracker, since_flap, flap_run,
                              # last_gc, since_gap


# ------------------------------------------------------------------
# one closed-loop episode
# ------------------------------------------------------------------
def run_episode(env, policy, k, budget=BUDGET, record_rows=None,
                trace_dir=None, tag="deploy", policy_sha=None):
    """One episode: perception -> package -> legal input -> emulator.

    record_rows: an optional dict column (rows are appended in-place,
    one per frame: step, vector (10), action) for byte-exact replay
    comparison. trace_dir: when given, the rows are ALSO written to
    <trace_dir>/<tag>_k<k>.jsonl after the episode.
    policy_sha: the identity of the loaded policy (the caller hashes
    the artifact; when None the package model_sha256 is used, else a
    type-name fallback for duck-typed test fakes).
    Returns the episode record dict. Raises LoopError on ANY
    environment failure (never swallowed, never retried silently).
    """
    uses_package = hasattr(policy, "predict") and not hasattr(
        policy, "act")
    if policy_sha is None:
        if uses_package:
            pol_sha = getattr(policy, "model_sha256", None) or \
                ("type:" + type(policy).__name__)
        else:
            pol_sha = "type:" + type(policy).__name__
    else:
        pol_sha = policy_sha

    from flappybird_policy import PolicyError as _PolErr
    try:
        env.start_episode(k)
    except Exception as e:
        raise LoopError(f"episode start failed (k={k}): {e}")
    if uses_package:
        observer, tracker, since_flap, flap_run, last_gc, since_gap = \
            fresh_perception()
        prev_action = None
    else:
        # the numpy policy owns its perception: it MUST be reset per
        # episode exactly like the deployed rollout does (a stale
        # observer/tracker from the previous life is NOT the deployed
        # behavior — regression-tested in test_r61_deployment.py)
        reset = getattr(policy, "reset_obs", None)
        if reset is not None:
            reset()
    pc = PassageCounter()
    flaps = 0
    steps = 0
    errors = []
    th = hashlib.sha256()
    t0 = time.time()
    death = "budget"
    rows = record_rows if record_rows is not None else []
    try:
        for step in range(budget):
            fr = env.frame()
            small = _small_rgb(fr)
            if uses_package:
                x, pend = build_vector(
                    small, observer, tracker, since_flap, flap_run,
                    last_gc, since_gap, prev_action)
                try:
                    action = policy.predict(x)
                except _PolErr:
                    raise
                since_flap, flap_run, last_gc, since_gap = \
                    advance_history(action, since_flap, flap_run,
                                    last_gc, since_gap, pend)
                prev_action = action
            else:
                x = None
                action = policy.act(small)
            th.update(x.tobytes() if x is not None
                      else small.tobytes())
            th.update(action.encode())
            if action == "FLAP":
                flaps += 1
            if rows is not None and record_rows is not None:
                rows.append((int(step),
                             (x.tolist() if x is not None else []),
                             action))
            env.run(1, {"B"} if action == "FLAP" else set())
            steps = step + 1
            nf = env.frame()
            by, _n = flappy_bird_y(nf)
            _g, bx = flappy_gap_target_r15(
                flappy_green_mask(nf), by if by is not None else -1)
            pc.fire(bx, step)
            if env.game_over(nf):
                death = "game_over"
                break
    except LoopError:
        raise
    except Exception as e:  # a real env/policy failure: loud, typed
        raise LoopError(f"episode k={k} failed at step {steps}: "
                        f"{type(e).__name__}: {e}")

    rec = {
        "tag": tag,
        "k": int(k),
        "policy_sha256": pol_sha,
        "emulator": emulator_tag(env),
        "budget": int(budget),
        "result": "alive" if steps >= budget else "death",
        "death_reason": death,
        "pipes": int(pc.count),
        "frames": int(steps),
        "flaps": int(flaps),
        "actions": int(flaps),
        "decisions": int(steps),
        "errors": errors,
        "trace_sha256": th.hexdigest(),
        "wall_s": round(time.time() - t0, 2),
        "ts": int(time.time()),
        "evidence": trace_dir,
    }
    if trace_dir and rows is not None:
        os.makedirs(trace_dir, exist_ok=True)
        path = os.path.join(trace_dir, f"{tag}_k{k}.jsonl")
        with open(path, "w") as f:
            for s, v, a in rows:
                f.write(json.dumps({"step": s, "x": v, "a": a}) + "\n")
        rec["trace_file"] = path
        rec["trace_file_sha256"] = _fsha(path)
    return rec


def _fsha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


_EMU_TAG = {}


def emulator_tag(env):
    """A stable one-line identification of the emulator stack."""
    if "tag" not in _EMU_TAG:
        try:
            bi = getattr(env, "boot_info", {}) or {}
            core = ""
            if hasattr(env, "p"):
                core = os.path.basename(
                    getattr(env.p, "core_path", "") or "")
            boot_s = json.dumps(bi, default=str)[:120]
            _EMU_TAG["tag"] = f"beetle={core}; boot={boot_s}"
        except Exception as e:
            _EMU_TAG["tag"] = f"unknown ({e})"
    return _EMU_TAG["tag"]


# ------------------------------------------------------------------
# CLI: chunked, resumable evaluation runs
# ------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["family", "fresh"], required=True)
    ap.add_argument("--split", default=os.path.join(
        REPO, "data", "learn", "r61_validation_split.json"))
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--seconds", type=int, default=500)
    ap.add_argument("--out", required=True,
                    help="rows jsonl (resumable)")
    ap.add_argument("--trace-dir", default=None)
    ap.add_argument("--policies", default="deploy",
                    help="comma list policy[:reps], e.g. deploy:2,base:1")
    ap.add_argument("--shard", type=int, default=0,
                    help="process only todo items with idx %% shards "
                         "== shard")
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--also-done", default=None,
                    help="extra rows jsonl whose (policy,k,rep) are "
                         "treated as done (parallel workers)")
    ap.add_argument("--workspace", default=None,
                    help="emulator workspace dir; parallel workers "
                         "MUST use distinct workspaces (savestate "
                         "files are per-workspace)")
    a = ap.parse_args()

    from ps1play.learn.games import FlappyEnv   # noqa: E402
    from r57f_es_ars import FlatPolicy          # noqa: E402
    from flappybird_policy import load_policy   # noqa: E402

    DATA = os.path.join(REPO, "data", "learn")
    POL = {
        "deploy": ("package", os.path.join(PKG, "models",
                                           "r60_soup_e6a010.onnx")),
        "soup": ("npz", os.path.join(DATA, "r59_soup_e6a010.npz")),
        "base": ("npz", os.path.join(DATA, "r58_dir2p_true.npz")),
        "c1": ("npz", os.path.join(DATA,
                                   "flappy_student_feat_r56_c1.npz")),
    }
    if a.mode == "family":
        seeds = [6, 12, 30, 45, 60, 90, 210]
    else:
        with open(a.split) as f:
            seeds = json.load(f)["validation_seeds"]
    wanted = []
    for w in a.policies.split(","):
        w = w.strip()
        if ":" in w:
            nm, rp = w.split(":")
            wanted.append((nm, int(rp)))
        else:
            wanted.append((w, a.reps))

    done = set()
    for rf in [a.out] + ([a.also_done] if a.also_done else []):
        if os.path.exists(rf):
            with open(rf) as f:
                for line in f:
                    try:
                        r = json.loads(line)
                        done.add((r["policy"], r["k"], r["rep"]))
                    except Exception:
                        pass

    full = []
    for pname, reps in wanted:
        for k in seeds:
            for rep in range(reps):
                full.append((pname, k, rep))
    # STATIC shard assignment over the FULL grid (independent of done)
    if a.shards > 1:
        full = [t for i, t in enumerate(full)
                if i % a.shards == a.shard]
    todo = [t for t in full if t not in done]
    if not todo:
        print("ALL_DONE")
        return
    print(f"pending episodes: {len(todo)}", flush=True)

    env = (FlappyEnv(workspace=a.workspace) if a.workspace
           else FlappyEnv())
    env.reach_ready()
    cache = {}
    t0 = time.time()
    stopped = False
    for pname, k, rep in todo:
        if time.time() - t0 > a.seconds and done:
            stopped = True
            break
        if pname not in cache:
            kind, path = POL[pname]
            if kind == "package":
                cache[pname] = ("package",
                                load_policy(model_path=path))
            else:
                cache[pname] = ("npz", FlatPolicy(path))
        kind, pol = cache[pname]
        if kind == "package":
            psha = pol.model_sha256
        else:
            psha = _fsha(POL[pname][1])
        rows = ([] if a.trace_dir else None)
        rec = run_episode(env, pol, k, BUDGET, record_rows=rows,
                          trace_dir=a.trace_dir,
                          tag=f"r61_{pname}", policy_sha=psha)
        rec["policy"], rec["rep"] = pname, int(rep)
        with open(a.out, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(json.dumps({kk: rec[kk] for kk in
                          ("policy", "k", "rep", "result", "pipes",
                           "frames", "flaps", "trace_sha256")}),
              flush=True)
    for _kind, pol in cache.values():
        if hasattr(pol, "close"):
            pol.close()
    env.close()
    print("ALL_DONE" if not stopped else
          f"CHUNK_STOPPED (rows now in {a.out})", flush=True)


if __name__ == "__main__":
    main()
