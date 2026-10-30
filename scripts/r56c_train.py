#!/usr/bin/env python3
"""r56c_train.py — R56 the flappy student training (offline, zero
boots): the WIDENED BC + the surgical corrections.

Base data (this round's boots 1-2, the tv8 traces):
  train = the TRAIN-family lives k=6/30/60/12/45/120 (the r55 BC never
          had the new seeds — the honest limitation "the BC labels
          never cover those states");
  val   = the k90 trace (an OFFLINE metric only — the r55 split
          discipline);
  test  = k210 NEVER touched (the closed-loop boot is the only test).

+ the r56b surgical corrections (mined_r1.npz): the step-level
  recovery flips (incl. the teacher-death windows k30/k45) at weights
  w in {1,2,3} — the r55 whole-tail mining taught a second flight
  style and DEGRADED the loop; these are single-step labels at the
  exact drift/death states only.

Candidates: (base, w1, w2, w3) x (hidden 128, 192) = 8 artifacts, all
 TinyMLP npz <= 4 MiB, feature_version 7, the same-norm discipline.
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
                        TRAIN_K, VAL_K, SCR, LEARN, CLASSES)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--round-tag", default="r1")
    a = ap.parse_args()

    data = {}
    for split, ks in (("train", TRAIN_K), ("val", VAL_K)):
        X, Y = [], []
        meta = {}
        for k in ks:
            life = load_life(k)
            Xv, Yv = [], []
            # the mirror's X + the recorded actions as the labels
            Xs, _states = mirror_vectors(life)
            acts = life["acts"]
            for i in range(life["n"]):
                Xv.append(Xs[i])
                Yv.append(CLASSES.index(acts[i]))
            X.extend(Xv)
            Y.extend(Yv)
            meta[f"k{k}"] = len(Yv)
        data[split] = (np.asarray(X, np.float32),
                       np.asarray(Y, np.int64), meta)
        print(f"{split}: {meta} -> {len(Y)} steps", flush=True)

    Xtr, Ytr, _m = data["train"]
    z = np.load(os.path.join(SCR, f"mined_{a.round_tag}.npz"))
    Xm, Ym = z["X"], z["y"]
    # JITTER AUGMENTATION: a single-step corrective label is smoothed
    # away by the MLP's locality (the mined-acceptance measured ~0 at
    # weight 3); teaching a small REGION around each critical state
    # (the perception-noise scale, the spatial dims only) makes the
    # correction stick without a whole-tail restyle.
    JIT_SIGMA, JIT_COPIES = 1.5, 16
    SPATIAL = [0, 1, 2, 3, 4, 5, 8]     # by vy gc dx g0 g1 last_gc
    rng = np.random.default_rng(7)
    Xa = [Xm]
    for _c in range(JIT_COPIES):
        Xj = Xm.copy()
        for d in SPATIAL:
            Xj[:, d] += rng.normal(0.0, JIT_SIGMA, len(Xj))
        Xa.append(Xj)
    Xm_aug = np.concatenate(Xa)
    Ym_aug = np.concatenate([Ym] * (JIT_COPIES + 1))
    print(f"mined: {len(Ym)} labels -> {len(Ym_aug)} with jitter x"
          f"{JIT_COPIES} (sigma {JIT_SIGMA}px, spatial dims only)",
          flush=True)

    idx = np.nonzero(Ytr == 1)[0]
    extra = np.tile(idx, 4)          # the r54f FLAP-oversample guard
    Xb = np.concatenate([Xtr, Xtr[extra]])
    Yb = np.concatenate([Ytr, Ytr[extra]])
    Wb = np.ones(len(Yb), dtype=np.float32)

    for hidden in (128, 192):
        for w in (0, 1, 2, 3):
            tag = f"p7v7h{hidden}" if w == 0 else f"p7v7h{hidden}w{w}"
            if w == 0:
                X = Xb
                Y = Yb
                W = Wb
            else:
                rep = w               # the mined block tiled w times
                Xc = np.tile(Xm_aug, (rep, 1))
                Yc = np.tile(Ym_aug, rep)
                X = np.concatenate([Xb, Xc])
                Y = np.concatenate([Yb, Yc])
                W = np.concatenate([Wb, np.full(len(Yc), 1.0)])
            counts = np.bincount(Y, minlength=2)
            cw = np.clip(
                (counts.sum() / (2.0 * np.maximum(counts, 1)))
                ** 0.5, 0.5, 3.0).astype(np.float32)
            mu, sd = X.mean(0), X.std(0) + 1e-6
            net = TinyMLP(X.shape[1], hidden, 2, seed=11)
            net.fit((X - mu) / sd, np.eye(2, dtype=np.float32)[Y],
                    epochs=60, batch=128, lr=3e-3, classification=True,
                    seed=11, class_weights=cw)
            report = {"tag": tag, "hidden": hidden, "mined_weight": w,
                      "n_train_steps": int(len(Y)),
                      "mined_labels": int(len(Ym)),
                      "splits": {k: v for k, v in
                                 data["train"][2].items()}}
            for nm in ("train", "val"):
                Xv, Yv, _ = data[nm]
                pred = net.predict((Xv - mu) / sd).argmax(1)
                acc = float((pred == Yv).mean())
                flap_rec = float((pred[Yv == 1] == 1).mean()) \
                    if (Yv == 1).any() else -1.0
                report[f"acc_{nm}"] = round(acc, 4)
                report[f"flap_recall_{nm}"] = round(flap_rec, 4)
            art = os.path.join(LEARN, f"flappy_student_feat_{tag}.npz")
            info = net.save_artifact(art, meta={
                "game": "flappy", "control_mode": "cv+mlp",
                "feature_version": 7, "classes": CLASSES,
                "norm": {"mean": mu.tolist(), "std": sd.tolist()},
                "teacher": "flappy_law_on_v7 (r15 law + BirdObserverV7"
                           " + GapTrackerV7, same-sensor pathway)",
                "teacher_provenance":
                    f"BC on the tv8 teacher lives (8 seeds incl. "
                    f"k12/45/120) + {len(Ym)} r56b surgical "
                    f"corrections @weight {w}"
                    if w else
                    "BC on the tv8 teacher lives (8 seeds incl. "
                    "k12/45/120)",
                "n_steps": int(len(Y)), "trained_at": time.time()})
            report["artifact"] = info
            with open(os.path.join(
                    LEARN, f"flappy_train_{tag}.json"), "w") as f:
                json.dump(report, f, indent=2)
            print(f"{tag}: acc_val={report['acc_val']:.4f} "
                  f"flap_recall_val={report['flap_recall_val']:.4f} "
                  f"({info['npz_bytes']}B)", flush=True)


if __name__ == "__main__":
    main()
