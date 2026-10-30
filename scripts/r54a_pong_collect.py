#!/usr/bin/env python3
"""r54a_pong_collect.py — P4 Stage A: the PREDICTIVE teacher dataset.

The P3 round proved pure behavior cloning of the v1 (tracking) teacher
can only TIE it. This round labels with PongTeacherV2 — the RAM-truth
PREDICTIVE + edge-aim teacher (see teacher.py; RAM is legal in
collect_teacher_data mode and the provenance is recorded per field).

10 episodes: 5 vs the game AI (pad2 disconnected), 5 vs the TRAIN-FAMILY
scenario opponent (aim_err 14 / delay 10 — the HELD-OUT family 22/16 is
NEVER played in collection). Episode-level split AFTER collection.
Every control step records:
  frames: small gray (60x80)               role visual_input
  actions: teacher-v2 action               role teacher_label (input)
  labels: ball_x/y, pad_l/r (RAM truth)    role teacher_label
          score_l/r (RAM)                  role evaluation_only
          teacher_pred_y (diagnostic)      role evaluation_only
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    sys.path.insert(0, _p)

from ps1play.learn.games import PongEnv                     # noqa: E402
from ps1play.learn.perception import to_gray                # noqa: E402
from ps1play.learn.teacher import PongTeacherV2, ScenarioOpponent  # noqa
from ps1play.learn.dataset import EpisodeRecord, LearningDataset  # noqa
from hellopong_r12_lib import make_jrn                      # noqa: E402

OUT = os.path.join(REPO, "scratch", "r54")
DS = os.path.join(OUT, "ds_pong_v2")
BALL_X, BALL_Y = 0x1FFEA0, 0x1FFEA4
PAD_L, SCORE_L = 0x1FFEB0, 0x1FFEB4
PAD_R, SCORE_R = 0x1FFEB8, 0x1FFEBC

FIELDS = [
    {"name": "frame_small_gray", "role": "visual_input",
     "source": "frame_rgb -> to_gray 60x80"},
    {"name": "ball_x", "role": "teacher_label",
     "source": "ram:0x1FFEA0 i32"},
    {"name": "ball_y", "role": "teacher_label",
     "source": "ram:0x1FFEA4 i32"},
    {"name": "pad_l", "role": "teacher_label",
     "source": "ram:0x1FFEB0 i32"},
    {"name": "pad_r", "role": "teacher_label",
     "source": "ram:0x1FFEB8 i32"},
    {"name": "score_l", "role": "evaluation_only",
     "source": "ram:0x1FFEB4 i32"},
    {"name": "score_r", "role": "evaluation_only",
     "source": "ram:0x1FFEBC i32"},
    {"name": "teacher_pred_y", "role": "evaluation_only",
     "source": "PongTeacherV2 RAM-velocity prediction (diagnostic)"},
]


def i32(ram, a):
    return int(np.frombuffer(ram[a:a + 4].tobytes(), "<i4")[0])


ACTIONS = {"UP": {"UP"}, "DOWN": {"DOWN"}, "NONE": set()}


def run_episode(env, teacher, rec, opponent, max_steps):
    """One teacher-v2-controlled episode; opponent None = game AI."""
    env.p.core.set_port_device(0, port=1)
    env.load_anchor("pong_anchor")
    env.p.core.set_port_device(0 if opponent is None else 1, port=1)
    teacher.reset_history()
    steps = 0
    sl = sr = 0
    t0 = time.time()
    for step in range(max_steps):
        _, ram = env.frame(), env.p.core.ram.copy()
        teacher.observe_ram(i32(ram, BALL_X), i32(ram, BALL_Y))
        act = teacher.act(i32(ram, PAD_L))
        opp_buttons = set()
        if opponent is not None:
            opponent.observe(i32(ram, BALL_Y), i32(ram, PAD_R))
            opp_buttons = opponent.buttons()
        rec.add_frame(to_gray(env.frame()))
        rec.add_step(act, labels={
            "ball_x": i32(ram, BALL_X), "ball_y": i32(ram, BALL_Y),
            "pad_l": i32(ram, PAD_L), "pad_r": i32(ram, PAD_R),
            "score_l": i32(ram, SCORE_L), "score_r": i32(ram, SCORE_R),
            "teacher_pred_y": (-1.0 if teacher.last_pred is None
                               else float(teacher.last_pred))})
        env.run(2, ACTIONS.get(act, set()), opp_buttons)
        steps += 1
        sl, sr = i32(ram, SCORE_L), i32(ram, SCORE_R)
        if sl and (sl != rec.outcome.get("player_score", 0)
                   or sr != rec.outcome.get("opponent_score", 0)):
            rec.add_event(ev="point", score_l=sl, score_r=sr, step=step)
            rec.set_outcome(player_score=sl, opponent_score=sr)
        if sl >= 5 or sr >= 5:
            break
    rec.set_outcome(
        result="win" if sl >= 5 else "loss" if sr >= 5 else "budget",
        player_score=sl, opponent_score=sr, steps=steps,
        wall_s=round(time.time() - t0, 1))
    return sl, sr, steps


def main():
    os.makedirs(OUT, exist_ok=True)
    jr = make_jrn(OUT, "[pongP4A]")
    ds = LearningDataset(DS)
    env = PongEnv()
    env.settle()
    teacher = PongTeacherV2(deadband=8.0, aim_offset=18.0)
    train_fam = {"aim_err": 14.0, "delay": 10, "deadband": 8.0}

    plan = ([("game_ai", None, 2600)] * 5 +
            [("train_fam", train_fam, 2400)] * 5)
    summary = []
    for i, (kind, params, budget) in enumerate(plan):
        eid = f"p4t{i:03d}"
        rec = EpisodeRecord(
            game="pong", mode="collect_teacher_data", episode_id=eid,
            scenario=kind, field_table=FIELDS, frame_shape=(60, 80),
            note="PongTeacherV2 (predictive edge-aim, RAM-truth labels);"
                 " STEP=2")
        opp = (ScenarioOpponent(params, seed=100 + i)
               if params is not None else None)
        sl, sr, steps = run_episode(env, teacher, rec, opp, budget)
        rec.freeze(DS)
        ds.register(rec.episode_id, json.load(
            open(os.path.join(DS, f"ep_{eid}.json"))))
        jr({"ev": "episode", "id": eid, "kind": kind, "l": sl, "r": sr,
            "steps": steps})
        summary.append({"id": eid, "kind": kind, "l": sl, "r": sr,
                        "steps": steps})
        print(f"{eid} {kind:10s} L={sl} R={sr} steps={steps}", flush=True)

    ids = [s["id"] for s in summary]
    test_ids = set(ids[-2:])
    val_ids = {ids[-3]}
    train_ids = [i for i in ids if i not in test_ids | val_ids]
    ds.assign_splits(train_ids, sorted(val_ids), sorted(test_ids))
    ds.save()
    report = {"episodes": summary, "splits": {"train": train_ids,
                                              "val": sorted(val_ids),
                                              "test": sorted(test_ids)},
              "teacher": teacher.name}
    with open(os.path.join(OUT, "pong_collect_p4.json"), "w") as f:
        json.dump(report, f, indent=2)
    env.close()
    jr({"ev": "done", "n": len(summary)})
    print("splits:", report["splits"])


if __name__ == "__main__":
    main()
