#!/usr/bin/env python3
"""r53c_pong_train.py — Stage C: train the pong visual students.

Two disclosed architectures, BOTH trained on the SAME frozen split:
  S-feat "cv+mlp": frame-derived CV features (visual_input, the SAME
                   code path as the deployed brain) -> TinyMLP -> action
  S-raw  "raw+mlp": stacked 2-frame gray pixels -> TinyMLP -> action
Targets = the teacher's recorded actions (behavior cloning). Reports
train/val/test accuracy per class, saves artifacts + norm + digest.
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    sys.path.insert(0, _p)

from ps1play.learn.dataset import EpisodeRecord, LearningDataset  # noqa
from ps1play.learn.policy import TinyMLP                # noqa: E402
from ps1play.learn import visual_only as VO             # noqa: E402

OUT = os.path.join(REPO, "scratch", "r53learn")
DS = os.path.join(OUT, "ds_pong")
CLASSES = ["DOWN", "NONE", "UP"]


def main():
    ds = LearningDataset(DS)
    eps = {e["episode_id"]: e for e in ds.manifest["episodes"]}
    train = [k for k, v in eps.items() if v["split"] == "train"]
    val = [k for k, v in eps.items() if v["split"] == "val"]
    test = [k for k, v in eps.items() if v["split"] == "test"]
    print(f"splits: train={len(train)} val={len(val)} test={len(test)}",
          flush=True)

    def load_split(ids):
        Xf, Xr, Y = [], [], []
        for eid in ids:
            meta, npz = EpisodeRecord.load(DS, eid)
            frames = npz["frames"]
            acts = [str(a) for a in npz["actions"]]
            for i in range(meta["n_steps"]):
                cur = frames[i]
                prev = frames[i - 1] if i > 0 else np.zeros_like(cur)
                Xf.append(VO.features_pong(cur, prev))
                Xr.append(np.concatenate([prev.ravel(),
                                          cur.ravel()]).astype(
                                              np.float32) / 255.0)
                Y.append(CLASSES.index(acts[i]))
        return (np.asarray(Xf, np.float32), np.asarray(Xr, np.float32),
                np.asarray(Y, np.int64))

    t0 = time.time()
    Xf_tr, Xr_tr, Y_tr = load_split(train)
    Xf_va, Xr_va, Y_va = load_split(val)
    Xf_te, Xr_te, Y_te = load_split(test)
    print(f"loaded: feat={Xf_tr.shape} raw={Xr_tr.shape} "
          f"({time.time()-t0:.1f}s)", flush=True)

    report = {"splits": {"train": len(train), "val": len(val),
                         "test": len(test)},
              "n_train_steps": int(len(Y_tr)),
              "classes": CLASSES}

    # ---- S-feat ----
    mu, sd = Xf_tr.mean(0), Xf_tr.std(0) + 1e-6
    net_f = TinyMLP(Xf_tr.shape[1], 24, 3, seed=1)
    net_f.fit((Xf_tr - mu) / sd, np.eye(3, dtype=np.float32)[Y_tr],
              epochs=40, batch=128, lr=3e-3, classification=True, seed=1)
    acc = {}
    for name, X, Y in (("train", Xf_tr, Y_tr), ("val", Xf_va, Y_va),
                       ("test", Xf_te, Y_te)):
        pred = net_f.predict((X - mu) / sd).argmax(1)
        acc[name] = round(float((pred == Y).mean()), 4)
    report["s_feat"] = {"acc": acc,
                        "n_in": int(Xf_tr.shape[1]), "hidden": 24}
    art = os.path.join(OUT, "pong_student_feat.npz")
    info = net_f.save_artifact(art, meta={
        "game": "pong", "control_mode": "cv+mlp", "classes": CLASSES,
        "norm": {"mean": mu.tolist(), "std": sd.tolist()},
        "dataset": {"root": DS,
                    "train": train, "val": val, "test": test},
        "trained_at": time.time()})
    report["s_feat"]["artifact"] = info

    # ---- S-raw ----
    net_r = TinyMLP(Xr_tr.shape[1], 48, 3, seed=2)
    net_r.fit(Xr_tr, np.eye(3, dtype=np.float32)[Y_tr],
              epochs=12, batch=128, lr=1e-3, classification=True,
              seed=2, verbose=True)
    acc = {}
    for name, X, Y in (("train", Xr_tr, Y_tr), ("val", Xr_va, Y_va),
                       ("test", Xr_te, Y_te)):
        pred = net_r.predict(X).argmax(1)
        acc[name] = round(float((pred == Y).mean()), 4)
    report["s_raw"] = {"acc": acc,
                       "n_in": int(Xr_tr.shape[1]), "hidden": 48}
    art = os.path.join(OUT, "pong_student_raw.npz")
    info = net_r.save_artifact(art, meta={
        "game": "pong", "control_mode": "raw+mlp", "classes": CLASSES,
        "norm": {},
        "dataset": {"root": DS,
                    "train": train, "val": val, "test": test},
        "trained_at": time.time()})
    report["s_raw"]["artifact"] = info

    with open(os.path.join(OUT, "pong_train_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
