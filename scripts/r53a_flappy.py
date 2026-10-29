#!/usr/bin/env python3
"""r53a_flappy.py — Stage A for FlappyBirdPSX:
  1. ready anchor + seed-variation probe: does the X-press timing (k)
     change the pipe sequence? (the anti-memorization lever)
  2. RAM hunts: bird world-y, pipe-x words (delta -45/f), score u16,
     gap-y words (constant per pipe).
Evidence -> scratch/r53learn/flappy_stage_a.json + flappy_ram_anchors.json
"""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    sys.path.insert(0, _p)

from ps1play.learn.games import FlappyEnv                # noqa: E402
from ps1play.learn.perception import flappy_bird_y       # noqa: E402
from ps1play.learn.teacher import FlappyTeacher          # noqa: E402
from hellopong_r12_lib import make_jrn, save_png         # noqa: E402

OUT = os.path.join(REPO, "scratch", "r53learn")


def gap_profile(env, k, frames=800):
    """Start with seed-timing k, play with the teacher, record the gap
    centers (vision) at fixed frame marks."""
    env.start_episode(k)
    teacher = FlappyTeacher()
    prev_by = None
    gaps = []
    last_flap = False
    for f in range(frames):
        fr = env.frame()
        by, vy, gc = teacher.observe(fr, prev_by)
        prev_by = by
        act = teacher.act(by, vy if vy is not None else 0.0, gc)
        buttons = {"B"} if act == "FLAP" else set()
        last_flap = act == "FLAP"
        env.run(1, buttons)      # r15 cadence: 1-frame decisions
        if f % 40 == 0:
            gaps.append(None if gc is None else round(float(gc), 1))
        if env.game_over(env.frame()):
            break
    return gaps


def main():
    jr = make_jrn(OUT, "[flapA]")
    env = FlappyEnv()
    jr({"ev": "boot", "core": env.boot_info})
    env.reach_ready()
    fr = env.frame()
    save_png(OUT, fr, "flappy_ready.png")
    jr({"ev": "ready_anchor_saved"})

    # ---- 1) seed variation probe (3 timings) ----
    profiles = {}
    for k in (6, 60, 130):
        profiles[k] = gap_profile(env, k)
        jr({"ev": "seed_probe", "k": k, "gaps_head": profiles[k][:12]})
    differ = (profiles[6][:12] != profiles[60][:12]
              or profiles[60][:12] != profiles[130][:12])
    report = {"seed_variation": {"differ": bool(differ),
                                 "profiles": profiles}}

    # ---- 2) RAM hunts (fresh episode, k=6) ----
    env.start_episode(6)
    teacher = FlappyTeacher()
    prev_by = None
    last_flap = False
    snaps = []
    for f in range(360):
        fr = env.frame()
        ram = env.p.core.ram.copy()
        by, _n = flappy_bird_y(fr)
        snaps.append((by, ram))
        byt, vy, gc = teacher.observe(fr, prev_by)
        prev_by = byt
        act = teacher.act(byt, vy if vy is not None else 0.0, gc)
        buttons = {"B"} if act == "FLAP" else set()
        last_flap = act == "FLAP"
        env.run(1, buttons)      # r15 cadence
        if env.game_over(env.frame()):
            jr({"ev": "hunt_episode_died", "frame": f})
            break
    bys = np.array([s[0] if s[0] is not None else np.nan
                    for s in snaps])
    # bird: words CORRELATED with the vision series (offset-agnostic)
    ok = ~np.isnan(bys)
    view = snaps[0][1].view("<i4").astype(np.int64)
    series32 = np.stack([s[1].view("<i4").astype(np.int64)
                         for s in snaps])         # T x N (i32 view)
    series = np.stack([s[1].view("<i2").astype(np.int64)
                       for s in snaps])           # T x N (i16 view: the
    # r15 sensors recorded the pipe pos.x as i16 — try BOTH views)
    bz = np.nan_to_num(bys, nan=0.0)
    bz = bz - bz.mean()
    denom = (bz.std() + 1e-9)
    corr = ((series - series.mean(axis=0)) * bz[:, None]).mean(axis=0) \
        / (series.std(axis=0) * denom + 1e-9)
    inrange = (series.max(axis=0) < 20000) & (series.min(axis=0) > -20000)
    bird_c = np.nonzero((corr > 0.9) & inrange)[0]
    report["bird_corr_cands"] = [hex(int(o) * 2) for o in bird_c[:10]]
    if len(bird_c):
        best = bird_c[np.argmax(corr[bird_c])]
        report["bird_best"] = {"addr": hex(int(best) * 2),
                               "corr": round(float(corr[best]), 3)}
    # pipe-x: delta exactly -90 per 2-frame snap (=-45/f world), both views
    pipes = []
    for nm, ser in (("i16", series), ("i32", series32)):
        d = np.diff(ser, axis=0)
        for delta in (-90, -45):
            hit = np.nonzero((d == delta).all(axis=0))[0]
            pipes += [f"{nm}:{hex(int(o) * ser.dtype.itemsize)}"
                      for o in hit[:8]]
    report["pipe_delta_words"] = pipes[:16]
    jr({"ev": "hunts", "bird": report.get("bird_best"),
        "pipes": report["pipe_delta_words"]})
    # score u16: increments during play (hunt on u16 view)
    s0 = snaps[0][1].view("<u2").astype(int)
    sN = snaps[-1][1].view("<u2").astype(int)
    inc = np.nonzero(sN - s0 >= 1)[0]
    report["u16_increased"] = len(inc)
    jr({"ev": "hunts", **{k: v for k, v in report.items()
                          if k != "seed_variation"}})
    with open(os.path.join(OUT, "flappy_stage_a.json"), "w") as f:
        json.dump(report, f, indent=2)
    env.close()
    print(json.dumps({k: v for k, v in report.items()
                      if k != "seed_variation"}, indent=2))
    print("seed differ:", differ)


if __name__ == "__main__":
    main()
