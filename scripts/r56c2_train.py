#!/usr/bin/env python3
"""r56c2_train.py — R56 the DISCIPLINED ladder (one lever per rung).

The boot-3 lesson (honest): changing several variables at once (3 new
seeds + jittered corrections @w3) REGRESSED the previously-won seeds
(k6 51->19, k210 13->1 vs the r55 champion 155). The r55
incremental protocol exists for exactly this failure class.

The ladder, each rung = ONE lever on top of the proven recipe
(r55_train's: BC on the teacher's own lives, FLAP oversample x4 +
sqrt-inverse class weights, seed 11, epochs 60):

  C1 (sanity anchor): the r55 recipe VERBATIM on this round's traces
     (train = tv8 k6+k60, val = tv8 k90, hidden 128). Boot-4 must
     reproduce ~155 before anything else counts.
  C2 (+coverage): C1 + the two BUDGET-ALIVE new seeds (k12, k120)
     — the widened BC coverage, no corrections.
  C3 (+recovery): C2 + the 2 walkback corrections (the k30/k45
     teacher-death flips) at weight 1 with the jitter region
     (sigma 1.2px, 8 copies, spatial dims only).

Offline metrics per rung: the val acc/flap-recall (k90) + the
per-seed DECISION AGREEMENT with the recorded teacher actions (the
clone-fidelity proxy; the r55 champion's k6 agreement was exact).
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

LADDER = {
    "c1": {"train": [6, 60], "mined": 0},
    "c2": {"train": [6, 60, 12, 120], "mined": 0},
    "c3": {"train": [6, 60, 12, 120], "mined": 1},
}


def build_xy(ks):
    X, Y, per = [], [], {}
    for k in ks:
        life = load_life(k)
        Xs, _st = mirror_vectors(life)
        for i in range(life["n"]):
            X.append(Xs[i])
            Y.append(CLASSES.index(life["acts"][i]))
        per[f"k{k}"] = life["n"]
    return np.asarray(X, np.float32), np.asarray(Y, np.int64), per


def main():
    # the mined corrections (with the jitter region)
    z = np.load(os.path.join(SCR, "mined_r1.npz"))
    Xm, Ym = z["X"], z["y"]
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

    # the offline val split + the agreement table's source lives
    val_lives = {k: load_life(k) for k in VAL_K}
    Xval, Yval = [], []
    for k, life in val_lives.items():
        Xs, _st = mirror_vectors(life)
        Xval.extend(Xs)
        Yval.extend(CLASSES.index(a) for a in life["acts"])
    Xval = np.asarray(Xval, np.float32)
    Yval = np.asarray(Yval, np.int64)

    agreement_lives = {}
    for tag_cfg in LADDER.values():
        for k in tag_cfg["train"]:
            if k not in agreement_lives:
                agreement_lives[k] = load_life(k)

    report_all = {}
    for tag, cfg in LADDER.items():
        Xtr, Ytr, per = build_xy(cfg["train"])
        idx = np.nonzero(Ytr == 1)[0]
        extra = np.tile(idx, 4)
        X = np.concatenate([Xtr, Xtr[extra]])
        Y = np.concatenate([Ytr, Ytr[extra]])
        if cfg["mined"]:
            X = np.concatenate([X, Xm_aug])
            Y = np.concatenate([Y, Ym_aug])
        counts = np.bincount(Y, minlength=2)
        cw = np.clip(
            (counts.sum() / (2.0 * np.maximum(counts, 1)))
            ** 0.5, 0.5, 3.0).astype(np.float32)
        mu, sd = X.mean(0), X.std(0) + 1e-6
        net = TinyMLP(X.shape[1], 128, 2, seed=11)
        net.fit((X - mu) / sd, np.eye(2, dtype=np.float32)[Y],
                epochs=60, batch=128, lr=3e-3, classification=True,
                seed=11, class_weights=cw)
        rep = {"tag": f"r56_{tag}", "train": cfg["train"],
               "mined": cfg["mined"], "per_seed_steps": per,
               "n_train": int(len(Y))}
        pred = net.predict((Xval - mu) / sd).argmax(1)
        rep["acc_val"] = round(float((pred == Yval).mean()), 4)
        rep["flap_recall_val"] = round(
            float((pred[Yval == 1] == 1).mean()), 4)
        # the per-seed decision agreement with the recorded teacher
        agr = {}
        for k, life in agreement_lives.items():
            Xs, _st = mirror_vectors(life)
            Xs = np.asarray(Xs, np.float32)
            pr = net.predict((Xs - mu) / sd).argmax(1)
            truth = np.asarray(
                [CLASSES.index(a) for a in life["acts"]])
            agr[f"k{k}"] = round(float((pr == truth).mean()), 4)
        rep["teacher_agreement"] = agr
        art = os.path.join(LEARN, f"flappy_student_feat_r56_{tag}.npz")
        info = net.save_artifact(art, meta={
            "game": "flappy", "control_mode": "cv+mlp",
            "feature_version": 7, "classes": CLASSES,
            "norm": {"mean": mu.tolist(), "std": sd.tolist()},
            "teacher": "flappy_law_on_v7 (r15 law + BirdObserverV7"
                       " + GapTrackerV7, same-sensor pathway)",
            "teacher_provenance":
                f"BC on the tv8 teacher lives {cfg['train']}"
                + (f" + the r56b walkback corrections (jitter "
                   f"x{JIT_COPIES}, sigma {JIT_SIGMA}px)"
                   if cfg["mined"] else ""),
            "n_steps": int(len(Y)), "trained_at": time.time()})
        rep["artifact"] = info
        with open(os.path.join(LEARN, f"flappy_train_r56_{tag}.json"),
                  "w") as f:
            json.dump(rep, f, indent=2)
        report_all[tag] = rep
        print(f"{tag}: acc_val={rep['acc_val']:.4f} "
              f"flap_recall={rep['flap_recall_val']:.4f} "
              f"agreement={agr} ({info['npz_bytes']}B)", flush=True)

    with open(os.path.join(SCR, "r56c2_ladder.json"), "w") as f:
        json.dump(report_all, f, indent=2)


if __name__ == "__main__":
    main()
