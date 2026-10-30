#!/usr/bin/env python3
"""r54h_flappy_dagger.py — flappy DAgger round: roll the CURRENT brain
on TRAIN-family seeds, relabel every state with the full-res teacher,
freeze into ds_flappy_dagger_p4. Deaths are the dataset — the relabels
at the student's own drift/failure states are what close the closed-
loop gap (the r53 P2 lesson, applied with the fixed target column).
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    sys.path.insert(0, _p)

from ps1play.learn.games import FlappyEnv, _small_rgb      # noqa: E402
from ps1play.learn.teacher import FlappyTeacher            # noqa: E402
from ps1play.learn.runner import BrainClient               # noqa: E402
from ps1play.learn.dataset import EpisodeRecord            # noqa: E402
from hellopong_r12_lib import make_jrn                     # noqa: E402

OUT = os.path.join(REPO, "scratch", "r54")
DS_DAG = os.path.join(OUT, "ds_flappy_dagger_p4")

FIELDS = [
    {"name": "frame_small_rgb", "role": "visual_input",
     "source": "frame_rgb -> area downsample 60x80x3"},
    {"name": "bird_y", "role": "visual_input", "source": "yellow centroid"},
    {"name": "vy", "role": "visual_input", "source": "bird_y diff"},
    {"name": "gap_center", "role": "visual_input",
     "source": "flappy_gap_target_r15"},
    {"name": "pipes", "role": "evaluation_only",
     "source": "vision band-crossing count"},
]


def dagger_life(env, client, k, max_steps, eid, jr):
    env.start_episode(k)
    client.reset_history()
    dag = EpisodeRecord(
        game="flappy", mode="evaluate_visual_only", episode_id=eid,
        scenario=f"seed_k{k}", field_table=FIELDS,
        frame_shape=(60, 80, 3),
        note="student state, full-res FlappyTeacher relabel (dagger)")
    teacher = FlappyTeacher()
    prev_by = None
    pipes = 0
    last_band_x = None
    t0 = time.time()
    from ps1play.learn.perception import (flappy_bird_y,     # noqa: E402
                                          flappy_gap_target_r15,
                                          flappy_green_mask)
    for step in range(max_steps):
        fr = env.frame()
        small = _small_rgb(fr)
        action = client.act(small)
        tby, tvy, tgc = teacher.observe(fr, prev_by)
        t_act = teacher.act(tby, tvy if tvy is not None else 0.0, tgc)
        dag.add_frame(small)
        dag.add_step(action, teacher_action=t_act, labels={
            "bird_y": -1.0 if tby is None else float(tby),
            "vy": -99.0 if tvy is None else float(tvy),
            "gap_center": -1.0 if tgc is None else float(tgc),
            "pipes": pipes})
        prev_by = tby
        green = flappy_green_mask(fr)
        _g, bx = flappy_gap_target_r15(green, tby)
        if bx is not None:
            if last_band_x is not None and bx > last_band_x + 60:
                pipes += 1
            last_band_x = bx
        env.run(1, {"B"} if action == "FLAP" else set())
        if env.game_over(env.frame()):
            break
    outcome = {"result": "death" if step < max_steps - 1 else "budget",
               "pipes": pipes, "steps": step + 1,
               "wall_s": round(time.time() - t0, 1)}
    dag.set_outcome(**outcome)
    dag.freeze(DS_DAG)
    jr({"ev": "dagger_life", "id": eid, **outcome})
    print(f"{eid} k={k} pipes={pipes} steps={step+1}", flush=True)
    return outcome


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--art", required=True)
    ap.add_argument("--prefix", default="p4fdag_r2")
    ap.add_argument("--lives-per-seed", type=int, default=2)
    a = ap.parse_args()

    jr = make_jrn(OUT, f"[flapP4DAG:{a.prefix}]")
    env = FlappyEnv()
    env.reach_ready()
    client = BrainClient(a.art)
    seeds = [6, 30, 60, 100, 130]
    total_steps = 0
    for k in seeds:
        for i in range(a.lives_per_seed):
            eid = f"{a.prefix}_k{k:03d}_{i}"
            o = dagger_life(env, client, k, 4500, eid, jr)
            total_steps += o["steps"]
    client.close()
    env.close()
    print(json.dumps({"prefix": a.prefix, "total_steps": total_steps}))


if __name__ == "__main__":
    main()
