#!/usr/bin/env python3
"""r53b_flappy_collect.py — Stage B: teacher lives across varied seeds.

10 lives; each = restore ready anchor -> seed-timing k (varied) -> the
r15 start sequence -> 1-frame servo until death. Per step recorded:
  frame small RGB (60x80x3)        role visual_input
  action (FLAP/HOVER)              the teacher's own action (target)
  bird_y, vy, gap_center           vision-derived (visual_input role,
                                   the SAME sensors the teacher used)
  score (vision pipe passes)       evaluation_only
Deaths ARE the dataset (mistakes + recoveries across seeds). RAM hunts
failed within budget (flappy_stage_a.json) -> labels are vision-derived
and this is DISCLOSED in the issue's information-source table.
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    sys.path.insert(0, _p)

from ps1play.learn.games import FlappyEnv, _small_rgb     # noqa: E402
from ps1play.learn.teacher import FlappyTeacher           # noqa: E402
from ps1play.learn.dataset import EpisodeRecord, LearningDataset  # noqa
from hellopong_r12_lib import make_jrn                    # noqa: E402

OUT = os.path.join(REPO, "scratch", "r53learn")
DS = os.path.join(OUT, "ds_flappy")

FIELDS = [
    {"name": "frame_small_rgb", "role": "visual_input",
     "source": "frame_rgb -> area downsample 60x80x3"},
    {"name": "bird_y", "role": "visual_input",
     "source": "yellow centroid (perception.flappy_bird_y)"},
    {"name": "vy", "role": "visual_input",
     "source": "bird_y[t] - bird_y[t-1]"},
    {"name": "gap_center", "role": "visual_input",
     "source": "flappy_gap_target_r15"},
    {"name": "pipes", "role": "evaluation_only",
     "source": "vision band-crossing count"},
]


def main():
    jr = make_jrn(OUT, "[flapB]")
    ds = LearningDataset(DS)
    env = FlappyEnv()
    env.reach_ready()
    teacher = FlappyTeacher()
    seeds = [6, 30, 60, 90, 120, 150, 180, 210, 240, 270]
    summary = []
    for li, k in enumerate(seeds):
        env.start_episode(k)
        rec = EpisodeRecord(
            game="flappy", mode="collect_teacher_data",
            episode_id=f"l{li:02d}_k{k:03d}", scenario=f"seed_k{k}",
            field_table=FIELDS, frame_shape=(60, 80, 3),
            note="teacher life; 1-frame servo; deaths kept")
        prev_by = None
        last_band_x = None
        pipes = 0
        flaps = 0
        t0 = time.time()
        for step in range(6000):
            fr = env.frame()
            small = _small_rgb(fr)
            by, vy, gc = teacher.observe(fr, prev_by)
            prev_by = by
            act = teacher.act(by, vy if vy is not None else 0.0, gc)
            # pipe pass = a NEW band acquisition well right of the last
            # one (vision proxy for the r15 RAM crossing; disclosed)
            from ps1play.learn.perception import (flappy_green_mask,
                                                  flappy_gap_target_r15)
            green = flappy_green_mask(fr)
            _g, bx = flappy_gap_target_r15(green, by)
            if bx is not None:
                if last_band_x is not None and bx > last_band_x + 60:
                    pipes += 1
                last_band_x = bx
            labels = {"bird_y": -1.0 if by is None else round(by, 2),
                      "vy": round(vy, 2) if vy is not None else 0.0,
                      "gap_center": (-1.0 if gc is None
                                     else round(gc, 2)),
                      "pipes": pipes}
            rec.add_frame(small)
            rec.add_step(act, labels=labels)
            if act == "FLAP":
                flaps += 1
            env.run(1, {"B"} if act == "FLAP" else set())  # pulse 1:1
            if env.game_over(env.frame()):
                break
        rec.set_outcome(result="death", pipes=pipes, steps=step + 1,
                        flaps=flaps, seed_k=k,
                        wall_s=round(time.time() - t0, 1))
        meta_path = rec.freeze(DS)
        with open(meta_path) as f:
            meta = json.load(f)
        ds.register(rec.episode_id, meta)
        summary.append({"life": li, "k": k, "pipes": pipes,
                        "steps": step + 1, "flaps": flaps})
        jr({"ev": "life", **summary[-1]})
    ids = [e["episode_id"] for e in ds.manifest["episodes"]]
    test_ids = [ids[i] for i in (3, 7)]          # held-out lives
    train_ids = [i for i in ids if i not in test_ids]
    val_ids = train_ids[-1:]
    train_ids = train_ids[:-1]
    ds.assign_splits(train_ids, val_ids, test_ids)
    pipes_all = [s["pipes"] for s in summary]
    report = {"lives": summary,
              "pipes_mean": round(float(np.mean(pipes_all)), 2),
              "pipes_max": int(max(pipes_all)),
              "splits": {"train": len(train_ids), "val": len(val_ids),
                         "test": len(test_ids)}}
    with open(os.path.join(OUT, "flappy_stage_b.json"), "w") as f:
        json.dump(report, f, indent=2)
    env.close()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
