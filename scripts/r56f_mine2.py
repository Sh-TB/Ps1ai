#!/usr/bin/env python3
"""r56f_mine2.py — R56 round-2 mining: the REAL drift-basin flips.

Source: the student lives RECORDED in the eval boots (the real frames
+ the student's OWN actions — the on-policy states the r55 BC never
covered). Only the basins the r55 CHAMPION also suffers are mined:

  stu_r56_c3_k060  death @2487 — the champion's k60 basin (2488) ✓
  stu_p7v7h192w3_k060 death @2488 — the same basin, a 2nd sample ✓
  stu_r56_c3_k030  death @1701 — the early basin (the champion's k210
                   dies at 1699 — the generalization shot; the label
                   comes from the TRAIN seed k30, legal) ✓
  stu_p7v7h192w3_k030 death @4394 — the teacher's k30 window, 2nd
                   sample ✓

Skipped: the k6 lives (the champion's k6 is budget-alive — its flips
would fight the clone on a seed the champion already wins) and the
k210 lives (HELD-OUT — never labeled, the split discipline).

Method per life: the EXACT feature mirror (the real frames through
BirdObserverV7 + finder + tracker + the policy's own history) -> the
belief states -> the death walk-back (the LATEST single flip whose
LOCAL physics lookahead — schedule geometry + the law continuation,
<= 150 steps — survives with margin). The same surgical standard as
r56b; zero synthetic frames; zero boots.
"""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import r55k_sim_lab as SL                                    # noqa: E402
from r56b_miner import (load_student_life, mirror_vectors,   # noqa: E402
                        lookahead, SCR, CLASSES, MARGIN_MIN,
                        H_WALK)

SOURCES = [
    ("stu_r56_c3_k060", 60),
    ("stu_p7v7h192w3_k060", 60),
    ("stu_r56_c3_k030", 30),
    ("stu_p7v7h192w3_k030", 30),
]


def main():
    SL.TOP_PAD, SL.BOT_PAD = 10.0, 11.0
    SL.GROUND_Y = 204.0
    out = []
    for stem, k in SOURCES:
        path = os.path.join(SCR, f"{stem}.npz")
        if not os.path.exists(path):
            print(f"{stem}: MISSING (skipped)", flush=True)
            continue
        life = load_student_life(path, k)
        X, states = mirror_vectors(life)
        d_step = None
        # the recorded death = the last step of the life
        n = life["n"]
        beak = life["beak"]
        # find the death step from the frames' end (the eval loop
        # breaks right after game_over)
        d_step = n
        labels = []
        latest = None
        for t in range(d_step - 1, max(life["i0"], d_step - 220), -1):
            if beak[t] <= 0 and states[t][0] < 0:
                continue
            flip = "FLAP" if life["acts"][t] == "HOVER" else "HOVER"
            st = states[t]
            if st[0] < 0:
                continue
            run_t = 1 if (t > 0 and life["acts"][t - 1] == "FLAP") \
                else 0
            ok, mg, _d = lookahead(life, t, st[0], st[1], run_t,
                                   first_action=flip, horizon=H_WALK)
            if ok and mg >= MARGIN_MIN:
                latest = (t, flip, mg)
                break
        if latest:
            t, flip, mg = latest
            labels.append({"stem": stem, "k": k, "step": t,
                           "label": flip, "margin": round(float(mg), 1),
                           "kind": "real_basin_flip",
                           "x": X[t].tolist()})
            print(f"{stem}: flip at {t} ({flip}, margin {mg:.1f})",
                  flush=True)
        else:
            print(f"{stem}: NO surviving single flip (honest negative)",
                  flush=True)
        out.extend(labels)
    X = np.asarray([lb["x"] for lb in out], dtype=np.float32) \
        if out else np.zeros((0, 10), np.float32)
    y = np.asarray([CLASSES.index(lb["label"]) for lb in out],
                   dtype=np.int64) if out else np.zeros((0,), np.int64)
    np.savez_compressed(
        os.path.join(SCR, "mined_r2.npz"), X=X, y=y,
        stem=np.asarray([lb["stem"] for lb in out]),
        step=np.asarray([lb["step"] for lb in out]),
        kind=np.asarray([lb["kind"] for lb in out]),
        margin=np.asarray([lb["margin"] for lb in out]))
    print(f"== mined_r2: {len(out)} real-basin flips", flush=True)


if __name__ == "__main__":
    main()
