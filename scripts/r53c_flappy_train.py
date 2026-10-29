#!/usr/bin/env python3
"""r53c_flappy_train.py — Stage C: train the flappy visual students.

  S-feat "cv+mlp": the DEPLOYED feature function features_flappy
                   (by, vy, gap_center, gap_dx from the small RGB) ->
                   TinyMLP -> {HOVER, FLAP}
  S-raw  "raw+mlp": stacked 2-frame gray pixels -> TinyMLP -> action
Targets = the teacher's recorded actions (behavior cloning) with
inverse-frequency class weights (FLAP is the minority class).
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    sys.path.insert(0, _p)

from ps1play.learn.dataset import EpisodeRecord          # noqa: E402
from ps1play.learn.policy import TinyMLP                 # noqa: E402
from ps1play.learn import visual_only as VO              # noqa: E402

OUT = os.path.join(REPO, "scratch", "r53learn")
DS = os.path.join(OUT, "ds_flappy")
CLASSES = ["HOVER", "FLAP"]


def main():
    ds_manifest = json.load(open(os.path.join(DS, "manifest.json")))
    eps = {e["episode_id"]: e for e in ds_manifest["episodes"]}
    train = [k for k, v in eps.items() if v["split"] == "train"]
    val = [k for k, v in eps.items() if v["split"] == "val"]
    test = [k for k, v in eps.items() if v["split"] == "test"]
    print(f"splits train={len(train)} val={len(val)} test={len(test)}",
          flush=True)

    def load(ids):
        Xf, Xr, Y = [], [], []
        for eid in ids:
            meta, npz = EpisodeRecord.load(DS, eid)
            frames = npz["frames"]              # (T, 60, 80, 3) uint8
            acts = [str(a) for a in npz["actions"]]
            grays = frames.mean(axis=3).astype(np.uint8)
            for i in range(meta["n_steps"]):
                cur = frames[i]
                prev = frames[i - 1] if i > 0 else np.zeros_like(cur)
                Xf.append(VO.features_flappy(cur, prev))
                Xr.append(np.concatenate(
                    [grays[i - 1].ravel() if i > 0
                     else np.zeros(4800, np.uint8),
                     grays[i].ravel()]).astype(np.float32) / 255.0)
                Y.append(CLASSES.index(acts[i]))
        return (np.asarray(Xf, np.float32), np.asarray(Xr, np.float32),
                np.asarray(Y))

    t0 = time.time()
    Xf_tr, Xr_tr, Y_tr = load(train)
    Xf_va, Xr_va, Y_va = load(val)
    Xf_te, Xr_te, Y_te = load(test)
    print(f"loaded feat={Xf_tr.shape} raw={Xr_tr.shape} "
          f"({time.time()-t0:.1f}s)", flush=True)
    # oversample the minority FLAP steps x4 (duplicate rows) — the
    # 6% FLAP rate otherwise collapses the classifier to all-HOVER;
    # the weight below is then the mild sqrt-inverse on the BALANCED
    # set (the earlier ^1.5-on-oversampled double-counting collapsed
    # the model the other way — measured, kept honest here)
    idx_flap = np.nonzero(Y_tr == 1)[0]
    extra = np.tile(idx_flap, 4)
    Xf_tr = np.concatenate([Xf_tr, Xf_tr[extra]])
    Xr_tr = np.concatenate([Xr_tr, Xr_tr[extra]])
    Y_tr = np.concatenate([Y_tr, Y_tr[extra]])
    counts = np.bincount(Y_tr, minlength=2)
    cw = np.clip((counts.sum() / (2.0 * np.maximum(counts, 1))) ** 0.5,
                 0.5, 3.0).astype(np.float32)
    report = {"splits": {"train": len(train), "val": len(val),
                         "test": len(test)},
              "n_train_steps": int(len(Y_tr)),
              "class_counts": counts.tolist(),
              "classes": CLASSES}

    for which, X_tr, X_va, X_te, hidden, epochs, lr in (
            ("feat", Xf_tr, Xf_va, Xf_te, 24, 40, 3e-3),
            ("raw", Xr_tr, Xr_va, Xr_te, 48, 12, 1e-3)):
        mu, sd = X_tr.mean(0), X_tr.std(0) + 1e-6
        net = TinyMLP(X_tr.shape[1], hidden, 2, seed=11)
        net.fit((X_tr - mu) / sd, np.eye(2, dtype=np.float32)[Y_tr],
                epochs=epochs, batch=128, lr=lr, classification=True,
                seed=11, class_weights=cw)
        acc = {}
        for nm, X, Y in (("train", X_tr, Y_tr), ("val", X_va, Y_va),
                         ("test", X_te, Y_te)):
            pred = net.predict((X - mu) / sd).argmax(1)
            acc[nm] = round(float((pred == Y).mean()), 4)
        # per-class recall on test (the FLAP recall matters)
        pred = net.predict((X_te - mu) / sd).argmax(1)
        recall = {}
        for c, cname in enumerate(CLASSES):
            m = Y_te == c
            recall[cname] = round(float((pred[m] == c).mean()), 4) \
                if m.sum() else None
        art = os.path.join(OUT, f"flappy_student_{which}.npz")
        info = net.save_artifact(art, meta={
            "game": "flappy",
            "control_mode": "cv+mlp" if which == "feat" else "raw+mlp",
            "classes": CLASSES,
            "norm": {"mean": mu.tolist(), "std": sd.tolist()},
            "dataset": {"root": DS, "train": train, "val": val,
                        "test": test},
            "trained_at": time.time()})
        report[f"s_{which}"] = {"acc": acc, "recall_test": recall,
                                "n_in": int(X_tr.shape[1]),
                                "hidden": hidden, "artifact": info}
        print(which, acc, recall, flush=True)
    with open(os.path.join(OUT, "flappy_train_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps({k: v for k, v in report.items()
                      if k.startswith("s_")}, indent=2))


if __name__ == "__main__":
    main()
