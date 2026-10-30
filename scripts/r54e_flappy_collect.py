#!/usr/bin/env python3
"""r54e_flappy_collect.py — P4 Stage B (flappy): teacher lives on the
TRAIN-FAMILY seeds ONLY.

Split hygiene fix vs r53b: that round collected lives at k=90 and k=210
— the SAME values later used as the held-out evaluation seeds. This
round collects on k in {6..42, 60, 100, 130}; k=90/210 stay untouched
for evaluation.

10 lives; each = restore ready anchor -> k idle -> the r15 start
sequence -> 1-frame servo (FlappyTeacher, full-res vision — the same
sensors that produced the r15/r53 evidence) until death or 4500 steps.
Per step records: small RGB frame (visual_input), the teacher action
(FLAP/HOVER target), and the vision-derived bird/gap readings
(visual_input role, evaluation-side bookkeeping).
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
from ps1play.learn.dataset import EpisodeRecord, LearningDataset  # noqa
from ps1play.learn.perception import (flappy_bird_y,       # noqa: E402
                                      flappy_gap_target_r15,
                                      flappy_green_mask)
from hellopong_r12_lib import make_jrn                     # noqa: E402

OUT = os.path.join(REPO, "scratch", "r54")
DS = os.path.join(OUT, "ds_flappy_v2")

FIELDS = [
    {"name": "frame_small_rgb", "role": "visual_input",
     "source": "frame_rgb -> area downsample 60x80x3"},
    {"name": "bird_y", "role": "visual_input",
     "source": "yellow centroid (perception.flappy_bird_y)"},
    {"name": "vy", "role": "visual_input", "source": "bird_y[t]-bird_y[t-1]"},
    {"name": "gap_center", "role": "visual_input",
     "source": "flappy_gap_target_r15"},
    {"name": "pipes", "role": "evaluation_only",
     "source": "vision band-crossing count"},
]

SEEDS = [6, 12, 18, 24, 30, 36, 42, 60, 100, 130]
MAX_STEPS = 4500


def main():
    os.makedirs(OUT, exist_ok=True)
    jr = make_jrn(OUT, "[flapP4B]")
    ds = LearningDataset(DS)
    env = FlappyEnv()
    env.reach_ready()
    teacher = FlappyTeacher()
    summary = []
    for li, k in enumerate(SEEDS):
        eid = f"f4l{li:02d}_k{k:03d}"
        env.start_episode(k)
        rec = EpisodeRecord(
            game="flappy", mode="collect_teacher_data", episode_id=eid,
            scenario=f"seed_k{k}", field_table=FIELDS,
            frame_shape=(60, 80, 3),
            note="full-res FlappyTeacher life; 1-frame servo; deaths kept")
        teacher.reset_history()
        prev_by = None
        last_band_x = None
        pipes = 0
        flaps = 0
        t0 = time.time()
        for step in range(MAX_STEPS):
            fr = env.frame()
            small = _small_rgb(fr)
            by, vy, gc = teacher.observe(fr, prev_by)
            prev_by = by
            act = teacher.act(by, vy if vy is not None else 0.0, gc)
            if act == "FLAP":
                flaps += 1
            green = flappy_green_mask(fr)
            _g, bx = flappy_gap_target_r15(green, by)
            if bx is not None:
                if last_band_x is not None and bx > last_band_x + 60:
                    pipes += 1
                    rec.add_event(ev="pipe", n=pipes, step=step)
                last_band_x = bx
            rec.add_frame(small)
            rec.add_step(act, labels={
                "bird_y": -1.0 if by is None else float(by),
                "vy": -99.0 if vy is None else float(vy),
                "gap_center": -1.0 if gc is None else float(gc),
                "pipes": pipes})
            env.run(1, {"B"} if act == "FLAP" else set())
            if env.game_over(env.frame()):
                break
        rec.set_outcome(result="death" if step < MAX_STEPS - 1
                        else "budget", pipes=pipes, steps=step + 1,
                        flaps=flaps, wall_s=round(time.time() - t0, 1))
        rec.freeze(DS)
        ds.register(rec.episode_id, json.load(
            open(os.path.join(DS, f"ep_{eid}.json"))))
        jr({"ev": "life", "id": eid, "k": k, "pipes": pipes,
            "steps": step + 1, "flaps": flaps})
        summary.append({"id": eid, "k": k, "pipes": pipes,
                        "steps": step + 1, "flaps": flaps})
        print(f"{eid} k={k:3d} pipes={pipes:3d} steps={step+1} "
              f"flaps={flaps}", flush=True)

    ids = [s["id"] for s in summary]
    test_ids = set(ids[-2:])
    val_ids = {ids[-3]}
    train_ids = [i for i in ids if i not in test_ids | val_ids]
    ds.assign_splits(train_ids, sorted(val_ids), sorted(test_ids))
    ds.save()
    report = {"lives": summary, "heldout_seeds": [90, 210],
              "splits": {"train": train_ids, "val": sorted(val_ids),
                         "test": sorted(test_ids)}}
    with open(os.path.join(OUT, "flappy_collect_p4.json"), "w") as f:
        json.dump(report, f, indent=2)
    env.close()
    print("splits:", report["splits"])


if __name__ == "__main__":
    main()
