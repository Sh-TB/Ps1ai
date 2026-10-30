#!/usr/bin/env python3
"""r56e_eval.py — R56 the same-boot head-to-head (the P4 bar).

One boot:
  * the law-on-v7 teacher — the identical 5-seed protocol
    (k=6/30/60/90/210, budgets 6000/4500/4500/4000/4000);
  * the candidate student(s) — the deployed BrainClient SUBPROCESS
    (frames in / actions out), the same seeds/budgets/counting;
  * the student's TRAIN-seed lives (k6/30/60) are RECORDED (frames +
    the student's OWN actions) — the round-2 mining source (the real
    drift states the r55 BC never covered).

Protocol identical to r55_eval (the pipe-count proxy = the full-res
band-acquisition jump; the beige death test; 1-frame decision cadence).
The single change is mechanical: ONE frame grab per step (the post-run
frame feeds the next decision) — the decision/perception semantics are
unchanged, the wall time halves.

THE BAR (declared before the run, the r55 convention + the cap
arithmetic: the schedule caps the protocol at 195):
  PRIMARY: same-boot student total >= teacher total with the student
  >= teacher on EVERY seed; EXCEED = the student survives a window
  that kills the teacher (expected: the k30 death @~4398) — OR, when
  the teacher is budget-alive everywhere, the student matches the
  pipes with FEWER total flaps (efficiency-superior flight).
  The final honest verdict uses ONLY the same-boot numbers.
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
from ps1play.learn.runner import BrainClient                   # noqa: E402
from ps1play.learn.perception import (flappy_bird_y,           # noqa: E402
                                      flappy_gap_target_r15,
                                      flappy_green_mask)
from r55g_m1 import LawOnV7Agent                               # noqa: E402

OUT = os.path.join(REPO, "scratch", "r56")
LEARN = os.path.join(REPO, "data", "learn")
SEEDS = [(6, 6000), (30, 4500), (60, 4500), (90, 4000), (210, 4000)]
TRAIN_K = {6, 30, 60}


def run_life(env, agent, k, budget, tag, save_npz=False):
    env.start_episode(k)
    if hasattr(agent, "reset_history"):
        agent.reset_history()
    frames, acts = [], []
    pipes = 0
    last_band_x = None
    flaps = 0
    t0 = time.time()
    step = 0
    fr = env.frame()
    for step in range(budget):
        small = _small_rgb(fr)
        action = agent.act(small)
        if action == "FLAP":
            flaps += 1
        if save_npz:
            frames.append(small)
            acts.append(action)
        by, _n = flappy_bird_y(fr)
        green = flappy_green_mask(fr)
        _gc, bx = flappy_gap_target_r15(green,
                                        by if by is not None else -1)
        if bx is not None:
            if last_band_x is not None and bx > last_band_x + 60:
                pipes += 1
            last_band_x = bx
        env.run(1, {"B"} if action == "FLAP" else set())
        fr = env.frame()
        if env.game_over(fr):
            step += 1
            break
    res = {"tag": tag, "k": k, "result": "death" if step < budget
           else "budget", "pipes": pipes, "steps": step,
           "flaps": flaps, "wall_s": round(time.time() - t0, 1)}
    print(json.dumps(res), flush=True)
    sys.stdout.flush()
    if save_npz and len(frames):
        np.savez_compressed(
            os.path.join(OUT, f"{tag}.npz"),
            frames=np.asarray(frames, dtype=np.uint8),
            actions=np.asarray(acts))
    return res


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--students", default="p7v7h192w3",
                    help="comma list of artifact tag names")
    ap.add_argument("--boot-id", default="3")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    env = FlappyEnv()
    env.reach_ready()
    rows = {"teacher": [], "students": {}}

    agent = LawOnV7Agent()
    for k, b in SEEDS:
        rows["teacher"].append(run_life(env, agent, k, b,
                                        f"teacher_k{k:03d}"))
        _dump(a.boot_id, rows)

    for tag in a.students.split(","):
        art = os.path.join(LEARN, f"flappy_student_feat_{tag}.npz")
        client = BrainClient(art)
        srows = []
        for k, b in SEEDS:
            r = run_life(env, client, k, b, f"stu_{tag}_k{k:03d}",
                         save_npz=(k in TRAIN_K))
            srows.append(r)
            _dump(a.boot_id, rows | {tag: srows})
        client.close()
        rows["students"][tag] = srows

    env.close()
    _dump(a.boot_id, rows)
    t_tot = sum(r["pipes"] for r in rows["teacher"])
    print(f"== teacher total: {t_tot} "
          f"({[r['pipes'] for r in rows['teacher']]})", flush=True)
    for tag, srows in rows["students"].items():
        s_tot = sum(r["pipes"] for r in srows)
        s_fl = sum(r["flaps"] for r in srows)
        t_fl = sum(r["flaps"] for r in rows["teacher"])
        per = ["+" if s["pipes"] > t["pipes"]
               else ("=" if s["pipes"] == t["pipes"] else "-")
               for s, t in zip(srows, rows["teacher"])]
        print(f"== {tag}: total {s_tot} vs {t_tot} | per-seed "
              f"{[r['pipes'] for r in srows]} {per} | flaps "
              f"{s_fl} vs {t_fl}", flush=True)


def _dump(boot_id, rows):
    with open(os.path.join(OUT, f"r56e_eval_boot{boot_id}.json"),
              "w") as f:
        json.dump(rows, f, indent=2)


if __name__ == "__main__":
    main()
