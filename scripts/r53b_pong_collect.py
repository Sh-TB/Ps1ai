#!/usr/bin/env python3
"""r53b_pong_collect.py — Stage A close + Stage B: edge-aim teacher
play (forces sharp angles -> the game AI eventually misses -> left
points verify score_l) WHILE collecting the teacher dataset.

Dataset: 8 episodes (restore pong_anchor each), opponent = the game's
own AI (pad2 disconnected). Every control step records:
  frames: small gray (60x80 uint8)          role visual_input
  actions: teacher action (UP/DOWN/NONE)    role teacher_label (input)
  labels: ball_x/y, pad_l/r (RAM truth)     role teacher_label
          score_l/r (RAM)                   role evaluation_only
Episode-level splits assigned AFTER collection (train/val/test).
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
from ps1play.learn.perception import (pong_ball_centroid,   # noqa: E402
                                      pong_paddle_rows, to_gray)
from ps1play.learn.teacher import PongTeacher               # noqa: E402
from ps1play.learn.dataset import (EpisodeRecord,           # noqa: E402
                                   LearningDataset)
from hellopong_r12_lib import make_jrn, save_png            # noqa: E402

OUT = os.path.join(REPO, "scratch", "r53learn")
DS = os.path.join(OUT, "ds_pong")
BALL_X, BALL_Y = 0x1FFEA0, 0x1FFEA4
PAD_L, SCORE_L = 0x1FFEB0, 0x1FFEB4
PAD_R, SCORE_R = 0x1FFEB8, 0x1FFEBC

FIELDS = [
    {"name": "frame_small_gray", "role": "visual_input",
     "source": "frame_rgb -> to_gray 60x80"},
    {"name": "ball_x", "role": "teacher_label", "source": "ram:0x1FFEA0 i32"},
    {"name": "ball_y", "role": "teacher_label", "source": "ram:0x1FFEA4 i32"},
    {"name": "pad_l", "role": "teacher_label", "source": "ram:0x1FFEB0 i32"},
    {"name": "pad_r", "role": "teacher_label", "source": "ram:0x1FFEB8 i32"},
    {"name": "score_l", "role": "evaluation_only",
     "source": "ram:0x1FFEB4 i32"},
    {"name": "score_r", "role": "evaluation_only",
     "source": "ram:0x1FFEBC i32"},
]


def i32(ram, a):
    return int(np.frombuffer(ram[a:a + 4].tobytes(), "<i4")[0])


def main():
    jr = make_jrn(OUT, "[pongB]")
    ds = LearningDataset(DS)
    env = PongEnv()
    env.p.core.set_port_device(0, port=1)
    env.settle()
    teacher_edge = PongTeacher(deadband=10.0)

    # EDGE-AIM variant: position the paddle so the ball clips an edge
    # (hit_pos ~ +/-26 -> vel_y bump) to force AI misses.
    def edge_action(cx, cy, lp, ram, aim):
        if cx is None or lp is None:
            return "NONE"
        if cx > 200:            # ball on the AI side: drift to center
            if lp > 130:
                return "UP"
            if lp < 110:
                return "DOWN"
            return "NONE"
        ty = (cy or 120) + (26 if aim else -26)
        if ty < lp - 10:
            return "UP"
        if ty > lp + 10:
            return "DOWN"
        return "NONE"

    score_l_seen = set()
    score_r_seen = set()
    t0 = time.time()
    for ep in range(8):
        env.load_anchor("pong_anchor")
        rec = EpisodeRecord(
            game="pong", mode="collect_teacher_data",
            episode_id=f"t{ep:03d}", scenario="ai_opponent_default",
            field_table=FIELDS, frame_shape=(60, 80),
            note="edge-aim teacher vs game AI; STEP=2")
        prev_scores = (0, 0)
        for step in range(2600):
            fr, ram = env.frame(), env.p.core.ram.copy()
            cx, cy, _n = pong_ball_centroid(fr)
            lp_v, _rp = pong_paddle_rows(fr)
            sl, sr = i32(ram, SCORE_L), i32(ram, SCORE_R)
            if (sl, sr) != prev_scores:
                rec.add_event(ev="point", score_l=sl, score_r=sr,
                              step=step)
                score_l_seen.add(sl)
                score_r_seen.add(sr)
                prev_scores = (sl, sr)
            aim = (step // 40) % 2 == 0
            act = edge_action(cx, cy, lp_v, ram, aim)
            labels = {"ball_x": i32(ram, BALL_X),
                      "ball_y": i32(ram, BALL_Y),
                      "pad_l": i32(ram, PAD_L),
                      "pad_r": i32(ram, PAD_R),
                      "score_l": sl, "score_r": sr}
            rec.add_frame(to_gray(fr))
            rec.add_step(act, labels=labels)
            env.run(2, {"UP": {"UP"}, "DOWN": {"DOWN"},
                        "NONE": set()}.get(act, set()))
            if sl >= 5 or sr >= 5:
                break
        rec.set_outcome(result="game" if (sl >= 5 or sr >= 5)
                        else "budget", player_score=sl,
                        opponent_score=sr, steps=len(rec.actions))
        meta_path = rec.freeze(DS)
        import hashlib
        with open(meta_path, "rb") as f:
            pass
        ds.register(rec.episode_id, json.load(open(meta_path)))
        jr({"ev": "episode", "id": rec.episode_id,
            "steps": len(rec.actions), "l": sl, "r": sr})
        score_l_seen.add(sl)
        score_r_seen.add(sr)
        if max(score_l_seen, default=0) >= 2 and max(score_r_seen,
                                                     default=0) >= 2:
            break
    # episode-level split: hold out every 4th episode
    ids = [e["episode_id"] for e in ds.manifest["episodes"]]
    test_ids = set(ids[::4])
    train_ids = [i for i in ids if i not in test_ids]
    val_ids = train_ids[-1:]
    train_ids = train_ids[:-1]
    ds.assign_splits(train_ids, val_ids, sorted(test_ids))
    digest = ds.save()
    report = {"episodes": len(ids), "score_l_values": sorted(score_l_seen),
              "score_r_values": sorted(score_r_seen),
              "wall_s": round(time.time() - t0, 1),
              "digest": json.dumps(ds.manifest["episodes"][:1])}
    with open(os.path.join(OUT, "pong_stage_b.json"), "w") as f:
        json.dump(report, f, indent=2)
    env.close()
    jr({"ev": "done", **report})
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
