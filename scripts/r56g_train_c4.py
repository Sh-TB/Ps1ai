#!/usr/bin/env python3
"""r56g_train_c4.py — R56 C4: the CHAMPION recipe (the r55 one: BC on
the teacher's own k6+k60 lives, hidden 128) + ALL the surgical
corrections (the r1 teacher-death walkbacks k30/k45 + the r2 real-basin
flips mined from the recorded student lives), jitter-regioned, weight
tiled x2. One lever on top of the proven recipe.
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

from ps1play.learn.policy import TinyMLP                   # noqa: E402
from r56b_miner import (load_life, mirror_vectors,          # noqa: E402
                        VAL_K, SCR, LEARN, CLASSES)
from r56c2_train import build_xy                            # noqa: E402


def main():
    Xb = []
    for name in ("mined_r1", "mined_r2"):
        z = np.load(os.path.join(SCR, f"{name}.npz"))
        if len(z["y"]):
            Xb.append(z["X"])
            print(f"{name}: {len(z['y'])} labels", flush=True)
    Xm = np.concatenate(Xb)
    Ym = np.concatenate(
        [np.load(os.path.join(SCR, f"{n}.npz"))["y"]
         for n in ("mined_r1", "mined_r2") if len(
             np.load(os.path.join(SCR, f"{n}.npz"))["y"])])
    JIT_SIGMA, JIT_COPIES = 1.2, 8
    SPATIAL = [0, 1, 2, 3, 4, 5, 8]
    rng = np.random.default_rng(7)
    blocks = [Xm]
    for _c in range(JIT_COPIES):
        Xj = Xm.copy()
        for d in SPATIAL:
            Xj[:, d] += rng.normal(0.0, JIT_SIGMA, len(Xj))
        blocks.append(Xj)
    Xm_aug = np.concatenate(blocks)
    Ym_aug = np.concatenate([Ym] * (JIT_COPIES + 1))
    print(f"mined total: {len(Ym)} -> {len(Ym_aug)} with jitter",
          flush=True)

    Xtr, Ytr, per = build_xy([6, 60])          # the CHAMPION recipe
    idx = np.nonzero(Ytr == 1)[0]
    extra = np.tile(idx, 4)
    X = np.concatenate([Xtr, Xtr[extra]])
    Y = np.concatenate([Ytr, Ytr[extra]])
    rep2 = 2                                    # the mined block x2
    X = np.concatenate([X] + [Xm_aug] * rep2)
    Y = np.concatenate([Y] + [Ym_aug] * rep2)
    counts = np.bincount(Y, minlength=2)
    cw = np.clip((counts.sum() / (2.0 * np.maximum(counts, 1)))
                 ** 0.5, 0.5, 3.0).astype(np.float32)
    mu, sd = X.mean(0), X.std(0) + 1e-6
    net = TinyMLP(X.shape[1], 128, 2, seed=11)
    net.fit((X - mu) / sd, np.eye(2, dtype=np.float32)[Y],
            epochs=60, batch=128, lr=3e-3, classification=True,
            seed=11, class_weights=cw)

    # the offline metrics
    Xval, Yval = [], []
    for k in VAL_K:
        life = load_life(k)
        Xs, _st = mirror_vectors(life)
        Xval.extend(Xs)
        Yval.extend(CLASSES.index(a) for a in life["acts"])
    Xval = np.asarray(Xval, np.float32)
    Yval = np.asarray(Yval, np.int64)
    pred = net.predict((Xval - mu) / sd).argmax(1)
    rep = {"tag": "r56_c4", "train": [6, 60],
           "mined": int(len(Ym)), "per_seed_steps": per,
           "acc_val": round(float((pred == Yval).mean()), 4),
           "flap_recall_val": round(
               float((pred[Yval == 1] == 1).mean()), 4)}
    agr = {}
    for k in (6, 30, 60):
        life = load_life(k)
        Xs, _st = mirror_vectors(life)
        pr = net.predict((np.asarray(Xs, np.float32) - mu) / sd).argmax(1)
        truth = np.asarray([CLASSES.index(a) for a in life["acts"]])
        agr[f"k{k}"] = round(float((pr == truth).mean()), 4)
    rep["teacher_agreement"] = agr
    art = os.path.join(LEARN, "flappy_student_feat_r56_c4.npz")
    info = net.save_artifact(art, meta={
        "game": "flappy", "control_mode": "cv+mlp",
        "feature_version": 7, "classes": CLASSES,
        "norm": {"mean": mu.tolist(), "std": sd.tolist()},
        "teacher": "flappy_law_on_v7 (r15 law + BirdObserverV7"
                   " + GapTrackerV7, same-sensor pathway)",
        "teacher_provenance":
            "BC on the tv8 teacher lives k6+k60 (the r55 champion"
            " recipe) + the r56 surgical corrections (2 teacher-death"
            " walkbacks k30/k45 + 4 real-basin flips from the recorded"
            f" student lives), jitter x{JIT_COPIES} sigma "
            f"{JIT_SIGMA}px, tiled x{rep2}",
        "n_steps": int(len(Y)), "trained_at": time.time()})
    rep["artifact"] = info
    with open(os.path.join(LEARN, "flappy_train_r56_c4.json"),
              "w") as f:
        json.dump(rep, f, indent=2)
    print(f"c4: acc_val={rep['acc_val']:.4f} agreement={agr} "
          f"({info['npz_bytes']}B)", flush=True)


if __name__ == "__main__":
    main()
