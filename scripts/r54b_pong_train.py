#!/usr/bin/env python3
"""r54b_pong_train.py — P4 Stage C: train the visual students on the
PREDICTIVE teacher's labels (v2 features + policy-history inputs).

  S-feat-v2 "cv+mlp": features_pong_v2 (6 v1 dims + pred_y intercept +
                      prev UP/DOWN) -> TinyMLP(32) -> UP/DOWN/NONE
  S-raw-v2 "raw+mlp": stacked 2-frame gray pixels -> TinyMLP(64)
Targets = PongTeacherV2's recorded actions (behavior cloning); the
artifact meta records feature_version=2 so the deployed Brain uses the
same vector (tests assert the equality of the two readers).
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    sys.path.insert(0, _p)

from ps1play.learn.dataset import EpisodeRecord           # noqa: E402
from ps1play.learn.policy import TinyMLP                  # noqa: E402
from ps1play.learn import visual_only as VO               # noqa: E402

OUT = os.path.join(REPO, "scratch", "r54")
CLASSES = ["DOWN", "NONE", "UP"]


def load_episodes(root, ids, kind="feat", w_scale=1.0):
    """kind=feat: v2 features (prev_action from the RECORDED actions —
    the teacher's own previous action, matching the deployed Brain's
    self-history at deployment)."""
    X, Y, W = [], [], []
    for eid in ids:
        meta, npz = EpisodeRecord.load(root, eid)
        frames = npz["frames"]              # (T,60,80) uint8 gray
        acts = [str(a) for a in npz["actions"]]
        # DAgger records: the TARGET is the teacher's relabel, not the
        # student's own (broken) action — r54d1/d2 trained on the wrong
        # column and degraded; caught by the r54 eval table.
        t_acts = [str(t) for t in npz["teacher_actions"]] \
            if "teacher_actions" in npz else [""] * len(acts)
        labels = json.loads(str(npz["labels_json"]))
        for i in range(meta["n_steps"]):
            cur = frames[i]
            prev = frames[i - 1] if i > 0 else np.zeros_like(cur)
            prev_act = acts[i - 1] if i > 0 else None
            target = t_acts[i] if t_acts[i] else acts[i]
            if not target:
                continue
            if kind == "feat":
                X.append(VO.features_pong_v2(cur, prev,
                                             prev_action=prev_act))
            else:
                X.append(np.concatenate(
                    [prev.ravel(), cur.ravel()]).astype(np.float32)
                    / 255.0)
            Y.append(CLASSES.index(target))
            # near-paddle steps carry the interception signal
            try:
                W.append(w_scale * (3.0 if float(labels[i]["ball_x"])
                                    < 110 else 1.0))
            except (KeyError, TypeError, ValueError):
                W.append(w_scale)
    return (np.asarray(X, np.float32), np.asarray(Y, np.int64),
            np.asarray(W, np.float32))


def train(which, hidden, epochs, lr, roots, suffix="p4"):
    X_all, Y_all, W_all = [], [], []
    for root, ids, wsc in roots:
        X, Y, W = load_episodes(root, ids, kind=which, w_scale=wsc)
        X_all.append(X)
        Y_all.append(Y)
        W_all.append(W)
    X, Y, W = (np.concatenate(a) for a in (X_all, Y_all, W_all))
    counts = np.bincount(Y, minlength=3)
    cw = np.clip((counts.sum() / (3.0 * np.maximum(counts, 1))) ** 0.5,
                 0.5, 6.0).astype(np.float32)
    mu, sd = X.mean(0), X.std(0) + 1e-6
    net = TinyMLP(X.shape[1], hidden, 3, seed=7)
    net.fit((X - mu) / sd, np.eye(3, dtype=np.float32)[Y], epochs=epochs,
            batch=128, lr=lr, classification=True, seed=7,
            class_weights=cw, sample_weights=W)
    accs = {}
    pred = net.predict((X - mu) / sd).argmax(1)
    accs["train_all"] = round(float((pred == Y).mean()), 4)
    art = os.path.join(OUT, f"pong_student_{which}_{suffix}.npz")
    info = net.save_artifact(art, meta={
        "game": "pong",
        "control_mode": "cv+mlp" if which == "feat" else "raw+mlp",
        "feature_version": 2, "classes": CLASSES,
        "norm": {"mean": mu.tolist(), "std": sd.tolist()},
        "teacher": "pong_teacher_v2_predictive_edge",
        "dataset": {"roots": [{"root": r, "episodes": list(ids),
                               "weight": wsc} for r, ids, wsc in roots]},
        "n_steps": int(len(Y)), "class_weights": cw.tolist(),
        "trained_at": time.time(),
        "train_acc": accs["train_all"]})
    return info, accs


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", nargs="*", default=[],
                    help="extra dataset roots:root1,eid1,eid2;...")
    ap.add_argument("--suffix", default="p4")
    ap.add_argument("--models", default="feat,raw")
    ap.add_argument("--extra-weight", type=float, default=1.0)
    ap.add_argument("--epochs", type=int, default=60)
    a = ap.parse_args()

    man = json.load(open(os.path.join(OUT, "ds_pong_v2",
                                      "manifest.json")))
    eps = {e["episode_id"]: e for e in man["episodes"]}
    splits = {"train": [], "val": [], "test": []}
    for eid, e in eps.items():
        splits[e["split"]].append(eid)

    roots = [(os.path.join(OUT, "ds_pong_v2"), splits["train"], 1.0)]
    for spec in a.extra:
        root, _, eids = spec.partition(":")
        roots.append((root, [e for e in eids.split(",") if e],
                      a.extra_weight))
        # val on the base val split only

    report = {"splits": {k: len(v) for k, v in splits.items()},
              "extra_roots": len(roots) - 1}
    specs = (("feat", 32, a.epochs, 3e-3), ("raw", 64, 14, 1e-3))
    specs = [s for s in specs if s[0] in set(a.models.split(","))]
    for which, hidden, epochs, lr in specs:
        info, accs = train(which, hidden, epochs, lr, roots,
                           suffix=a.suffix)
        report[f"s_{which}"] = {"acc": accs, "hidden": hidden,
                                "artifact": info}
        print(which, accs, f"{info['npz_bytes']}B", flush=True)
    with open(os.path.join(OUT, f"pong_train_{a.suffix}.json"), "w") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    main()
