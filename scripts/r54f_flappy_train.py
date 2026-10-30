#!/usr/bin/env python3
"""r54f_flappy_train.py — P4 Stage C (flappy): train the visual student
on features_flappy_v2 (v1 4 dims + gap edges + OWN policy history).

The policy-history dims (prev FLAP / steps-since-FLAP, both maintained
by the deployed Brain itself) are the mechanism that lets the LEARNED
policy reproduce the flap-edge pulse discipline that r53's hand
state-machine carried. Targets = the recorded teacher actions
(behavior cloning) with FLAP oversampling x4 + sqrt-inverse weights.
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
CLASSES = ["HOVER", "FLAP"]


def episode_vectors(meta, npz, kind="feat", feature_version=2):
    """Per-episode (X, Y) with the causal since-flap history (v2) and
    the policy-owned stale-gap memory (v3)."""
    frames = npz["frames"]                  # (T,60,80,3) uint8
    acts = [str(a) for a in npz["actions"]]
    # DAgger records: the TARGET is the teacher relabel (the student's
    # own actions are the distribution, never the target).
    t_acts = [str(t) for t in npz["teacher_actions"]] \
        if "teacher_actions" in npz else [""] * len(acts)
    X, Y = [], []
    since = 99
    last_gc = -1.0
    since_gap = 40
    flap_run = 0
    for i in range(meta["n_steps"]):
        cur = frames[i]
        prev = frames[i - 1] if i > 0 else np.zeros_like(cur)
        prev_act = acts[i - 1] if i > 0 else None
        target = t_acts[i] if t_acts[i] else acts[i]
        if not target:
            continue
        if kind == "feat":
            if feature_version >= 4:
                X.append(VO.features_flappy_v4(
                    cur, prev, since_flap=since, last_gc=last_gc,
                    since_gap=since_gap, flap_run=flap_run))
            elif feature_version == 3:
                X.append(VO.features_flappy_v3(
                    cur, prev, prev_action=prev_act, since_flap=since,
                    last_gc=last_gc, since_gap=since_gap))
            else:
                X.append(VO.features_flappy_v2(cur, prev,
                                               prev_action=prev_act,
                                               since_flap=since))
        else:
            grays = frames.mean(axis=3).astype(np.uint8)
            g_prev = (grays[i - 1] if i > 0
                      else np.zeros(4800, np.uint8))
            X.append(np.concatenate([g_prev.ravel(), grays[i].ravel()])
                     .astype(np.float32) / 255.0)
        Y.append(CLASSES.index(target))
        if acts[i] == "FLAP":
            since = 0
            flap_run = min(flap_run + 1, 9)
        else:
            since = min(since + 1, 99)
            flap_run = 0
        if feature_version >= 3:
            gc = float(VO.features_flappy(cur, None)[2])
            if gc >= 0:
                last_gc = gc
                since_gap = 0
            else:
                since_gap = min(since_gap + 1, 40)
    return X, Y


def load(root, ids, kind="feat", w_scale=1.0, feature_version=2):
    X, Y = [], []
    for eid in ids:
        meta, npz = EpisodeRecord.load(root, eid)
        ex, ey = episode_vectors(meta, npz, kind,
                                 feature_version=feature_version)
        X.extend(ex)
        Y.extend(ey)
    return (np.asarray(X, np.float32), np.asarray(Y, np.int64),
            np.full(len(Y), w_scale, dtype=np.float32))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", nargs="*", default=[])
    ap.add_argument("--suffix", default="p4")
    ap.add_argument("--models", default="feat,raw")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--extra-weight", type=float, default=1.0)
    ap.add_argument("--feature-version", type=int, default=2)
    ap.add_argument("--feat-arch", type=int, default=48)
    ap.add_argument("--base-root", default=None,
                    help="override the base dataset root (e.g. the "
                         "sf-relabeled copy)")
    a = ap.parse_args()

    man = json.load(open(os.path.join(OUT, "ds_flappy_v2",
                                      "manifest.json")))
    eps = {e["episode_id"]: e for e in man["episodes"]}
    splits = {"train": [], "val": [], "test": []}
    for eid, e in eps.items():
        splits[e["split"]].append(eid)
    print("splits:", {k: len(v) for k, v in splits.items()}, flush=True)

    base_root = a.base_root or os.path.join(OUT, "ds_flappy_v2")
    roots = [(base_root, splits["train"], 1.0)]
    for spec in a.extra:
        root, _, eids = spec.partition(":")
        roots.append((root, [e for e in eids.split(",") if e],
                      a.extra_weight))

    def gather(kind):
        Xs, Ys, Ws = [], [], []
        for root, ids, wsc in roots:
            X, Y, W = load(root, ids, kind, w_scale=wsc,
                           feature_version=a.feature_version)
            Xs.append(X)
            Ys.append(Y)
            Ws.append(W)
        return (np.concatenate(Xs), np.concatenate(Ys),
                np.concatenate(Ws))

    report = {"splits": {k: len(v) for k, v in splits.items()},
              "extra_roots": len(roots) - 1}
    specs = [("feat", a.feat_arch, a.epochs, 3e-3), ("raw", 64, 12, 1e-3)]
    specs = [s for s in specs if s[0] in set(a.models.split(","))]
    for which, hidden, epochs, lr in specs:
        X, Y, W = gather(which)
        # oversample the minority FLAP class x4 (BC collapse guard)
        idx = np.nonzero(Y == 1)[0]
        extra = np.tile(idx, 4)
        X = np.concatenate([X, X[extra]])
        Y = np.concatenate([Y, Y[extra]])
        W = np.concatenate([W, W[extra]])
        counts = np.bincount(Y, minlength=2)
        cw = np.clip((counts.sum() / (2.0 * np.maximum(counts, 1)))
                     ** 0.5, 0.5, 3.0).astype(np.float32)
        mu, sd = X.mean(0), X.std(0) + 1e-6
        net = TinyMLP(X.shape[1], hidden, 2, seed=11)
        net.fit((X - mu) / sd, np.eye(2, dtype=np.float32)[Y],
                epochs=epochs, batch=128, lr=lr, classification=True,
                seed=11, class_weights=cw, sample_weights=W)
        accs = {}
        for nm, ids in (("train", splits["train"]),
                        ("val", splits["val"]), ("test", splits["test"])):
            Xv, Yv, _Wv = load(roots[0][0], ids, which,
                               feature_version=a.feature_version)
            pred = net.predict((Xv - mu) / sd).argmax(1)
            accs[nm] = round(float((pred == Yv).mean()), 4)
            flap_recall = float((pred[Yv == 1] == 1).mean()) \
                if (Yv == 1).any() else -1.0
            accs[f"{nm}_flap_recall"] = round(flap_recall, 4)
        art = os.path.join(OUT, f"flappy_student_{which}_{a.suffix}.npz")
        info = net.save_artifact(art, meta={
            "game": "flappy",
            "control_mode": "cv+mlp" if which == "feat" else "raw+mlp",
            "feature_version": a.feature_version, "classes": CLASSES,
            "norm": {"mean": mu.tolist(), "std": sd.tolist()},
            "teacher": "flappy_teacher_v2_r15play (full-res)",
            "n_steps": int(len(Y)), "class_weights": cw.tolist(),
            "trained_at": time.time()})
        report[f"s_{which}"] = {"acc": accs, "hidden": hidden,
                                "artifact": info}
        print(which, accs, f"{info['npz_bytes']}B", flush=True)
    with open(os.path.join(OUT, f"flappy_train_{a.suffix}.json"),
              "w") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    main()
