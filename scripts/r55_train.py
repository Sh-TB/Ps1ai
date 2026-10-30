#!/usr/bin/env python3
"""r55_train.py — the v7 flappy student (behavior cloning, offline,
zero boots).

Teacher = flappy_law_on_v7 (the r15 play law driven by BirdObserverV7
+ GapTrackerV7 — the SAME small-frame pathway the deployed Brain runs,
same-sensor discipline). The labels = the teacher's own actions on its
own recorded flight (the tv7n traces, one boot, saved by r55g_m1):
a deterministic function of the student's sensory stream + the policy's
own action history — mission-legal, disclosed in the meta.

Feature pipeline mirrors Brain._vector/act EXACTLY (the v7 observer +
gap tracker + the policy-owned history state), so the offline vectors
are bit-identical to the deployed brain's inputs.
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
from ps1play.learn import visual_only as VO                # noqa: E402

SCR = os.path.join(REPO, "scratch", "r55")
OUT = os.path.join(REPO, "data", "learn")
CLASSES = ["HOVER", "FLAP"]

# episode-level split: the train family (6/60 — the only seeds the
# m1 boot traced; k30 joins via the DAgger rounds) vs the held-out
# seeds (90/210, never trained — the val trace is an OFFLINE metric
# only, the closed-loop test is the boot eval)
SPLITS = {"train": ["tv7p_k6", "tv7p_k60"],
          "val": ["tv7p_k90"],
          "test": []}


def episode_vectors(frames, acts):
    """(X, Y) for one law-on-v7 life — mirrors Brain._vector/act."""
    obs = VO.BirdObserverV7()
    gtr = VO.GapTrackerV7()
    X, Y = [], []
    since_flap, flap_run = 99, 0
    last_gc, since_gap = -1.0, 40
    prev_action = None
    for i in range(len(frames)):
        cur = frames[i]
        by_obs, vy_obs = obs.step(cur, prev_action)
        gc_raw, dx, g0, g1, _b = VO._flappy_gap_raw2(cur,
                                                     by_hint=by_obs)
        gc_obs = gtr.step((gc_raw, g0, g1, dx + 160.0))
        x = VO.features_flappy_v7(cur, by_obs, vy_obs,
                                  since_flap=since_flap,
                                  last_gc=last_gc,
                                  since_gap=since_gap,
                                  flap_run=flap_run,
                                  gc_obs=gc_obs)
        X.append(x)
        Y.append(CLASSES.index(str(acts[i])))
        # the Brain's post-decision state machine (the trajectory's
        # OWN action = the teacher's action here)
        a = str(acts[i])
        prev_action = a
        if a == "FLAP":
            since_flap = 0
            flap_run = min(flap_run + 1, 9)
        else:
            since_flap = min(since_flap + 1, 99)
            flap_run = 0
        if gc_obs is not None:
            last_gc = float(gc_obs)
            since_gap = 0
        else:
            since_gap = min(since_gap + 1, 40)
    return X, Y


def load_split(names):
    X, Y, meta = [], [], {}
    for nm in names:
        z = np.load(os.path.join(SCR, f"{nm}.npz"))
        ex, ey = episode_vectors(z["frames"], z["action"])
        X.extend(ex)
        Y.extend(ey)
        meta[nm] = len(ey)
    return np.asarray(X, np.float32), np.asarray(Y, np.int64), meta


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--suffix", default="p5v7")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--hidden", type=int, default=48)
    ap.add_argument("--dagger-eps", default="",
                    help="comma list of extra DAgger episode npz "
                         "stems in scratch/r55 (student states, "
                         "law-on-v7 relabels)")
    ap.add_argument("--dagger-weight", type=float, default=1.0)
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    data = {}
    for split, names in SPLITS.items():
        X, Y, meta = load_split(names)
        data[split] = (X, Y)
        print(f"{split}: {meta} -> {len(Y)} steps", flush=True)

    Xtr, Ytr = data["train"]
    if a.dagger_eps:
        xd, yd = [], []
        for stem in [s for s in a.dagger_eps.split(",") if s]:
            z = np.load(os.path.join(SCR, f"{stem}.npz"))
            ex, ey = episode_vectors(z["frames"], z["teacher_actions"])
            xd.extend(ex)
            yd.extend(ey)
            print(f"dagger {stem}: {len(ey)} steps", flush=True)
        Xtr = np.concatenate([Xtr, np.asarray(xd, np.float32)])
        Ytr = np.concatenate([Ytr, np.asarray(yd, np.int64)])
        wd = np.concatenate([np.ones(len(Ytr) - len(yd)),
                             np.full(len(yd), a.dagger_weight)])
    else:
        wd = np.ones(len(Ytr))

    # FLAP oversampling x4 + sqrt-inverse class weights (the r54f
    # BC-collapse guards)
    idx = np.nonzero(Ytr == 1)[0]
    extra = np.tile(idx, 4)
    X = np.concatenate([Xtr, Xtr[extra]])
    Y = np.concatenate([Ytr, Ytr[extra]])
    W = np.concatenate([wd, wd[extra]])
    counts = np.bincount(Y, minlength=2)
    cw = np.clip((counts.sum() / (2.0 * np.maximum(counts, 1)))
                 ** 0.5, 0.5, 3.0).astype(np.float32)
    mu, sd = X.mean(0), X.std(0) + 1e-6
    net = TinyMLP(X.shape[1], a.hidden, 2, seed=11)
    net.fit((X - mu) / sd, np.eye(2, dtype=np.float32)[Y],
            epochs=a.epochs, batch=128, lr=3e-3, classification=True,
            seed=11, class_weights=cw, sample_weights=W)

    report = {"splits": {k: len(v[1]) for k, v in data.items()},
              "dagger_eps": a.dagger_eps, "hidden": a.hidden,
              "n_train_steps": int(len(Y))}
    for nm in ("train", "val", "test"):
        Xv, Yv = data[nm]
        if len(Yv) == 0:
            continue
        pred = net.predict((Xv - mu) / sd).argmax(1)
        acc = float((pred == Yv).mean())
        flap_rec = float((pred[Yv == 1] == 1).mean()) \
            if (Yv == 1).any() else -1.0
        report[f"acc_{nm}"] = round(acc, 4)
        report[f"flap_recall_{nm}"] = round(flap_rec, 4)
        print(f"{nm}: acc={acc:.4f} flap_recall={flap_rec:.4f}",
              flush=True)

    art = os.path.join(OUT, f"flappy_student_feat_{a.suffix}.npz")
    info = net.save_artifact(art, meta={
        "game": "flappy",
        "control_mode": "cv+mlp",
        "feature_version": 7,
        "classes": CLASSES,
        "norm": {"mean": mu.tolist(), "std": sd.tolist()},
        "teacher": "flappy_law_on_v7 (r15 law + BirdObserverV7 + "
                   "GapTrackerV7, same-sensor small-frame pathway)",
        "teacher_provenance": "behavior cloning on the teacher's own "
                              "recorded flight (tv7n traces) + "
                              "DAgger relabels"
                              if a.dagger_eps else
                              "behavior cloning on the teacher's own "
                              "recorded flight (tv7n traces)",
        "n_steps": int(len(Y)), "class_weights": cw.tolist(),
        "trained_at": time.time()})
    report["artifact"] = info
    with open(os.path.join(OUT, f"flappy_train_{a.suffix}.json"),
              "w") as f:
        json.dump(report, f, indent=2)
    print(f"artifact: {info['npz_bytes']}B", flush=True)


if __name__ == "__main__":
    main()
