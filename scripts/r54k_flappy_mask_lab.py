#!/usr/bin/env python3
"""r54k_flappy_mask_lab.py — offline mask lab: compare bird-y
estimators on the student's BLIND-regime frames (the recorded dagger
episodes where the small-frame centroid latched onto pipe blends).

Masks (on the 60x80 small RGB):
  v1 (current): (r > b+25) & (g > b+5) & (r > 120), rows 5..45, cols 32..49
  strict  : (b < 120) & (r > 130) & (g > 130)
  hybrid  : strict, fallback to v1 when strict is empty
Ground truth: the full-res bird_y recorded per step in the dagger
labels (flappy_bird_y on the live frame).
Metric: mean |est - truth|, and the WORST-16-step window error.
"""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    sys.path.insert(0, _p)

OUT = os.path.join(REPO, "scratch", "r54")
SY = 240.0 / 60.0


def masks(cur):
    r = cur[:, :, 0].astype(int)
    g = cur[:, :, 1].astype(int)
    b = cur[:, :, 2].astype(int)
    v1 = (r > b + 25) & (g > b + 5) & (r > 120)
    strict = (b < 120) & (r > 130) & (g > 130)
    return v1, strict


def bird_y(mask, lo=5, hi=45, c0=32, c1=50):
    m = mask.copy()
    m[:lo, :] = False
    m[hi:, :] = False
    m[:, :c0] = False
    m[:, c1:] = False
    ys, _ = np.nonzero(m)
    return ys.mean() * SY if len(ys) >= 2 else -1.0


def main():
    root = os.path.join(OUT, "ds_flappy_dagger_p4")
    eids = sorted(f[3:-5] for f in os.listdir(root)
                  if f.startswith("ep_") and f.endswith(".json"))
    from ps1play.learn.dataset import EpisodeRecord
    errs = {"v1": [], "strict": [], "hybrid": [], "v1_worst": [],
            "strict_worst": [], "hybrid_worst": []}
    for eid in eids:
        meta, npz = EpisodeRecord.load(root, eid)
        frames = npz["frames"]
        labels = json.loads(str(npz["labels_json"]))
        for i in range(meta["n_steps"]):
            truth = labels[i].get("bird_y", -1.0)
            if truth < 0:
                continue
            cur = frames[i]
            v1m, sm = masks(cur)
            e_v1 = bird_y(v1m)
            e_st = bird_y(sm)
            e_hy = e_st if e_st > 0 else e_v1
            for name, e in (("v1", e_v1), ("strict", e_st),
                            ("hybrid", e_hy)):
                if e > 0:
                    errs[name].append(abs(e - truth))
                else:
                    errs[name].append(40.0)   # dropout penalty
    for name in ("v1", "strict", "hybrid"):
        a = np.asarray(errs[name])
        worst = np.sort(a)[-max(1, len(a) // 16):].mean()
        print(f"{name:8s} mean={a.mean():6.2f}px  p90="
              f"{np.percentile(a, 90):6.2f}  worst16%={worst:6.2f}  "
              f"n={len(a)}")


if __name__ == "__main__":
    main()
