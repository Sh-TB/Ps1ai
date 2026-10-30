#!/usr/bin/env python3
"""r55a_collect.py — R55 Stage A: record the overlap-regime evidence.

One boot. For each seed k in {6,30,60,90,210} the SAME-TIER sf teacher
(FlappyTeacherAgent, small-frame features) plays one recorded life:

  per control step we store
    * the small RGB frame 60x80x3 (the student's entire sensory world)
    * the agent action
    * full-res vision bird_y (flappy_bird_y) + pixel count
    * SILVER bird_y = physics-integrated state anchored/corrected by
      trusted vision (occluded steps coast on the source-verified
      dynamics: impulse -8 on the 2nd pulse frame, accel +1/f^2,
      terminal +2)
    * occluded flag (vision lost while green overlaps the bird column)
    * the sf-teacher's own feature readings (by_feat, gc_feat)
    * full-res frame kept ONLY for occluded steps (capped per life)

Output: scratch/r55/life_kXXX.npz + r55a_meta.json (local, gitignored).
Purpose: offline lab for the v7 observer + training data with
overlap-regime labels (r54 left the latch diagnosed but unsolved).
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

from ps1play.learn.games import FlappyEnv, _small_rgb        # noqa: E402
from ps1play.learn.teacher import FlappyTeacherAgent         # noqa: E402
from ps1play.learn.perception import (flappy_bird_y,         # noqa: E402
                                      flappy_green_mask,
                                      flappy_gap_target_r15)

OUT = os.path.join(REPO, "scratch", "r55")
os.makedirs(OUT, exist_ok=True)

SEEDS = [(6, 6000), (30, 4500), (60, 4500), (90, 4000), (210, 4000)]
FULL_CAP = 400                     # occluded full-res frames kept / life

# source-verified dynamics (r15 note + r54k data fit — same constants
# the deployed FlappyObserver carries)
IMPULSE, GRAVITY, TERMINAL = -8.0, 1.0, 2.0


def overlap_now(small):
    """green pixels inside the bird's small column band (32..50)."""
    r = small[:, :, 0].astype(int)
    g = small[:, :, 1].astype(int)
    b = small[:, :, 2].astype(int)
    green = (g > 110) & (g > r + 10) & (b < 175) & (r < g)
    return bool(green[5:46, 32:50].any())


def silver_step(state, action, vision_y, vision_n):
    """Advance the silver (physics+vision) bird state one control step.

    state: dict(y, vy, run, anchored, since_trust, occluded_streak)
    Trust rule: vision accepted when anchored False (first fix) or
    |vision - predicted| <= 30 px (the r54 latch junk sat >= 40 px away
    from the true falling bird, measured 77->139 vs frozen 95-105).
    """
    st = state
    st["run"] = min(st["run"] + 1, 9) if action == "FLAP" else 0
    if st["anchored"]:
        if st["run"] == 2:
            st["vy"] = IMPULSE
        else:
            st["vy"] = min(st["vy"] + GRAVITY, TERMINAL)
        st["y"] += st["vy"]
    trusted = False
    if vision_y is not None and 6 <= vision_n <= 900:
        if not st["anchored"]:
            trusted = True
        else:
            trusted = abs(vision_y - st["y"]) <= 30.0
    if trusted:
        if st["anchored"] and abs(vision_y - st["y"]) > 2.0:
            st["y"] = float(vision_y)          # hard fix (vision exact)
        elif not st["anchored"]:
            st["y"] = float(vision_y)
        st["anchored"] = True
        st["since_trust"] = 0
        st["occluded_streak"] = 0
    else:
        st["since_trust"] += 1
        st["occluded_streak"] += 1
    return st, trusted


def run_life(env, agent, k, budget, tag, meta):
    env.start_episode(k)
    if hasattr(agent, "reset_history"):
        agent.reset_history()
    frames, actions, v_ys, v_ns, sil_ys, occ, bys, gcs = [], [], [], [], [], [], [], []
    full_cap = []
    st = {"y": None, "vy": 0.0, "run": 0, "anchored": False,
          "since_trust": 99, "occluded_streak": 0}
    prev_vy_vision = None
    prev_vision_y = None
    pipes = 0
    last_band_x = None
    t0 = time.time()
    step = 0
    for step in range(budget):
        fr = env.frame()
        small = _small_rgb(fr)
        action = agent.act(small)
        by_feat, gc_feat, _dx = _sf_features(small)
        v_y, v_n = flappy_bird_y(fr)
        st, trusted = silver_step(st, action, v_y, v_n)
        # pipe bookkeeping (evaluation-only, r53 convention)
        green = flappy_green_mask(fr)
        _gc, bx = flappy_gap_target_r15(green, v_y if v_y is not None else -1)
        if bx is not None:
            if last_band_x is not None and bx > last_band_x + 60:
                pipes += 1
            last_band_x = bx
        frames.append(small)
        actions.append(action)
        v_ys.append(-1.0 if v_y is None else float(v_y))
        v_ns.append(int(v_n))
        sil_ys.append(float(st["y"]) if st["anchored"] else -1.0)
        occ.append(0 if trusted else (1 if st["anchored"] else -1))
        bys.append(float(by_feat))
        gcs.append(float(gc_feat))
        if occ[-1] == 1 and len(full_cap) < FULL_CAP:
            full_cap.append(fr)
        buttons = {"B"} if action == "FLAP" else set()
        env.run(1, buttons)
        if env.game_over(env.frame()):
            break
    res = {"tag": tag, "k": k, "steps": step + 1,
           "result": "death" if step < budget - 1 else "budget",
           "pipes": pipes,
           "occluded_steps": int(sum(1 for o in occ if o == 1)),
           "wall_s": round(time.time() - t0, 1)}
    meta["lives"].append(res)
    np.savez_compressed(
        os.path.join(OUT, f"life_k{k:03d}.npz"),
        frames=np.asarray(frames, dtype=np.uint8),
        actions=np.asarray(actions),
        vision_y=np.asarray(v_ys, dtype=np.float32),
        vision_n=np.asarray(v_ns, dtype=np.int32),
        silver_y=np.asarray(sil_ys, dtype=np.float32),
        occl=np.asarray(occ, dtype=np.int8),
        by_feat=np.asarray(bys, dtype=np.float32),
        gc_feat=np.asarray(gcs, dtype=np.float32),
        fullres=np.asarray(full_cap, dtype=np.uint8) if full_cap
        else np.zeros((0,), dtype=np.uint8))
    print(json.dumps(res), flush=True)
    return res


def _sf_features(small):
    """The sf teacher's small-frame feature readings (for latch stats)."""
    from ps1play.learn import visual_only as VO
    f = VO.features_flappy(small, None)
    return float(f[0]), float(f[2]), float(f[3])


def main():
    meta = {"seeds": [k for k, _ in SEEDS], "lives": [],
            "impulse": IMPULSE, "gravity": GRAVITY, "terminal": TERMINAL}
    env = FlappyEnv()
    env.reach_ready()
    for k, budget in SEEDS:
        run_life(env, FlappyTeacherAgent(), k, budget,
                 f"sf_teacher_k{k}", meta)
    env.close()
    with open(os.path.join(OUT, "r55a_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print("== saved", os.path.join(OUT, "r55a_meta.json"), flush=True)


if __name__ == "__main__":
    main()
