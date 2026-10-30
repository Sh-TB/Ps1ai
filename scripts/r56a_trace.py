#!/usr/bin/env python3
"""r56a_trace.py — R56 Boot 1 (of max 3): the trace sweep.

The r55 scratch corpus was lost with the sandbox recycle; this boot
re-records the law-on-v7 teacher lives AND widens the BC coverage with
three NEW train-family seeds (the r55 honest limitation: "the BC labels
never cover those states"). One boot, eight lives, restore-based resets:

  protocol seeds (the identical 5-seed protocol, budgets verbatim):
    k=6 (6000), k=30 (4500), k=60 (4500), k=90 (4000), k=210 (4000)
  new TRAIN-family seeds (never in the heldout set {90, 210}):
    k=12 (4500), k=45 (4500), k=120 (4000)

Split discipline (unchanged from r55): k210 is recorded for the
schedule/sim-evaluation corpus ONLY — its frames/actions NEVER enter
training (the train script excludes it; the val split is the k90 trace;
the closed-loop eval is the real test).

Per control step recorded (the r55g/r55a field set):
  small frame 60x80x3, action, obs_y/obs_vy/since_trust (BirdObserverV7),
  beak_y (full-res vision truth), gap_gc (raw finder v3), gap_bx,
  trk_gc (GapTrackerV7 output).

Output: scratch/r56/tv8_kXXX.npz + r56a_trace.json (local, gitignored).

FOREGROUND-ONLY protocol (the r53/r56 silent-background-launch deaths):
one process = one boot; the --lives arg splits the sweep across
foreground chunks when the wall budget requires it (each chunk = its
own boot, disclosed in the ledger).
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

from ps1play.learn.games import FlappyEnv, _small_rgb          # noqa: E402
from ps1play.learn.perception import (flappy_bird_y,           # noqa: E402
                                      flappy_gap_target_r15,
                                      flappy_green_mask)
from r55g_m1 import LawOnV7Agent                               # noqa: E402

OUT = os.path.join(REPO, "scratch", "r56")
os.makedirs(OUT, exist_ok=True)

LIVES = [
    (6, 6000), (30, 4500), (60, 4500), (90, 4000), (210, 4000),
    (12, 4500), (45, 4500), (120, 4000),
]


def run_life(env, agent, k, budget, tag):
    env.start_episode(k)
    agent.reset_history()
    rec = []
    pipes = 0
    last_band_x = None
    flaps = 0
    t0 = time.time()
    step = 0
    for step in range(budget):
        fr = env.frame()
        small = _small_rgb(fr)
        action = agent.act(small)
        if action == "FLAP":
            flaps += 1

        by, _n = flappy_bird_y(fr)
        green = flappy_green_mask(fr)
        gc15, bx = flappy_gap_target_r15(green,
                                         by if by is not None else -1)
        if bx is not None:
            if last_band_x is not None and bx > last_band_x + 60:
                pipes += 1
            last_band_x = bx
        rec.append((
            small, action,
            float(agent.obs.y) if agent.obs.y is not None else -1.0,
            float(agent.obs.vy),
            int(agent.obs.since_trust),
            -1.0 if by is None else float(by),
            -1.0 if gc15 is None else float(gc15),
            -1.0 if bx is None else float(bx),
            float(agent.gtr.gc) if agent.gtr.gc is not None else -1.0))
        env.run(1, {"B"} if action == "FLAP" else set())
        if env.game_over(env.frame()):
            break
    res = {"tag": tag, "k": k, "result": "death" if step < budget - 1
           else "budget", "pipes": pipes, "steps": step + 1,
           "flaps": flaps, "wall_s": round(time.time() - t0, 1)}
    print(json.dumps(res), flush=True)
    sys.stdout.flush()
    np.savez_compressed(
        os.path.join(OUT, f"{tag}.npz"),
        frames=np.asarray([r[0] for r in rec], dtype=np.uint8),
        action=np.asarray([r[1] for r in rec]),
        obs_y=np.asarray([r[2] for r in rec], dtype=np.float32),
        obs_vy=np.asarray([r[3] for r in rec], dtype=np.float32),
        since_trust=np.asarray([r[4] for r in rec], dtype=np.int32),
        beak_y=np.asarray([r[5] for r in rec], dtype=np.float32),
        gap_gc=np.asarray([r[6] for r in rec], dtype=np.float32),
        gap_bx=np.asarray([r[7] for r in rec], dtype=np.float32),
        trk_gc=np.asarray([r[8] for r in rec], dtype=np.float32))
    return res


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lives", default="",
                    help="comma list of seeds to run (default: all 8)")
    ap.add_argument("--boot-id", default="1")
    a = ap.parse_args()
    want = ({int(x) for x in a.lives.split(",") if x}
            or {k for k, _b in LIVES})
    lives = [(k, b) for k, b in LIVES if k in want]
    env = FlappyEnv()
    env.reach_ready()
    agent = LawOnV7Agent()
    rows = []
    for k, b in lives:
        rows.append(run_life(env, agent, k, b, f"tv8_k{k:03d}"))
        # incremental summary (a timeout loses at most the live life)
        with open(os.path.join(OUT, f"r56a_trace_boot{a.boot_id}.json"),
                  "w") as f:
            json.dump({"boot": a.boot_id, "rows": rows}, f, indent=2)
    env.close()
    tot = [r["pipes"] for r in rows]
    print(f"== boot{a.boot_id} teacher pipes: {tot} "
          f"(sum {sum(tot)})", flush=True)


if __name__ == "__main__":
    main()
