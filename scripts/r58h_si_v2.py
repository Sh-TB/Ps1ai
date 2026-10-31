#!/usr/bin/env python3
"""r58h_si_v2.py — self-imitation round 2 (learner D) on the
PROVENANCE-CORRECTED base's own lives, offline, zero boots.

Why SI now (the r58 evidence): ARS round 2 is exhausted — the base sits
on a collapse plateau (r58g: 6/12 sibling directions INVARIANT on the
(k90,k210) pair, 6/12 collapse to attractors, ZERO positive signal;
r58_ars iter-0 candidate REJECTED: k60 87->29). SI moves in weight
space through the BC loss on the policy's OWN successful lives — the
lever that produced si_v1's verified gains (k90 43->68) in r57.

Recipe = the r57 arm-D recipe verbatim (r57_si_v1_train_report.json):
fine-tune FROM the base, own-lives only, no teacher rows, flap tile x4
+ sqrt-balanced class weights, batch 128, lr 1e-3; the base's norm
contract kept verbatim (the lineage norm == bootstrap == si_v1 ==
dir2p_true, verified). Epochs: 8 / 15 / 25 variants saved for the VAL
closed-loop selection (the bootstrap-protocol epoch rule).

Outputs: data/learn/r58_si_v2_e{8,15,25}.npz (+ sidecars) +
scratch/r57/r58h_si_v2_report.json. Every input life sha256 is
recorded. NO teacher data anywhere (the lives are the base's own
deployed-path rollouts, hashes in the report).
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

from ps1play.learn import visual_only as VO                 # noqa: E402
from ps1play.learn.policy import TinyMLP                    # noqa: E402
from r57e_train_bootstrap import mirror_life, CLASSES       # noqa: E402

SCR = os.path.join(REPO, "scratch", "r57")
LEARN = os.path.join(REPO, "data", "learn")
BASE = os.path.join(LEARN, "r58_dir2p_true.npz")
LIVES = [
    ("k6_87a", os.path.join(SCR, "life_r58_base_lives_k6_r0.npz")),
    ("k60_87a", os.path.join(SCR, "life_r58_base_lives_k60_r0.npz")),
    ("k12_76", os.path.join(SCR, "life_r58_base_lives_k12_r0.npz")),
]
EPOCH_SETS = [8, 15, 25]


def main():
    Xs, Ys, life_meta = [], [], []
    for name, path in LIVES:
        z = np.load(path)
        frames = z["frames"]
        acts = [str(a) for a in z["actions"]]
        X = mirror_life(frames, acts)
        Y = np.asarray([CLASSES.index(a) for a in acts], dtype=np.int64)
        Xs.append(X)
        Ys.append(Y)
        life_meta.append({"life": name, "npz": os.path.basename(path),
                          "rows": int(len(Y)),
                          "sha256": SO_sha(path)})
        print(f"{name}: {len(Y)} rows", flush=True)
    X = np.concatenate(Xs)
    Y = np.concatenate(Ys)

    # flap tile x4 + sqrt-balanced class weights (the C1/si mechanics)
    idx = np.nonzero(Y == 1)[0]
    extra = np.tile(idx, 4)
    Xb = np.concatenate([X, X[extra]])
    Yb = np.concatenate([Y, Y[extra]])
    counts = np.bincount(Yb, minlength=2)
    cw = np.clip((counts.sum() / (2.0 * np.maximum(counts, 1)))
                 ** 0.5, 0.5, 3.0).astype(np.float32)

    # the base's norm contract, kept verbatim
    net0, meta = TinyMLP.load_artifact(BASE)
    mu = np.asarray(meta["norm"]["mean"], dtype=np.float32)
    sd = np.asarray(meta["norm"]["std"], dtype=np.float32)

    report = {"round": "R58 arm D (si_v2)",
              "base": os.path.basename(BASE),
              "base_sha256": SO_sha(BASE),
              "lives": life_meta,
              "n_rows": int(len(Y)),
              "flap_fraction": round(float((Y == 1).mean()), 4),
              "norm_source": "r58_dir2p_true.npz (== lineage norm)",
              "recipe": "fine-tune FROM r58_dir2p_true, own lives only "
                        "(k6 87a + k60 87a + k12 76), flap tile x4, "
                        "sqrt-balanced class weights, batch 128, "
                        "lr 1e-3, seed 11; epochs {8,15,25} for the "
                        "VAL selection"}
    variants = {}
    for ep in EPOCH_SETS:
        net, _m = TinyMLP.load_artifact(BASE)   # fresh base weights
        t0 = time.time()
        net.fit((Xb - mu) / sd, np.eye(2, dtype=np.float32)[Yb],
                epochs=ep, batch=128, lr=1e-3, classification=True,
                seed=11, class_weights=cw)
        train_s = round(time.time() - t0, 1)
        pred = net.predict((X - mu) / sd).argmax(1)
        agree = float((pred == Y).mean())
        flap_rec = float((pred[Y == 1] == 1).mean())
        art = os.path.join(LEARN, f"r58_si_v2_e{ep}.npz")
        net.save_artifact(art, meta={
            "game": "flappy", "control_mode": "cv+mlp",
            "feature_version": 7, "classes": CLASSES,
            "norm": {"mean": mu.tolist(), "std": sd.tolist()},
            "teacher": "SELF (r58 arm D): fine-tune from "
                       "r58_dir2p_true on its OWN deployed-path lives "
                       "(k6@10000 87a, k60@10000 87a, k12@8798 76)",
            "teacher_provenance":
                "self-imitation, student-only; teacher import blocked "
                "during collection (hashed no-teacher traces); the "
                "base itself is the provenance-corrected "
                "si_v1+0.03*delta_2 reconstruction (r58f)",
            "init_checkpoint": "r58_dir2p_true.npz",
            "lives": life_meta,
            "epochs": ep, "lr": 1e-3, "batch": 128, "seed": 11,
            "n_steps": int(len(Y)), "trained_at": time.time()})
        variants[f"e{ep}"] = {
            "artifact": os.path.basename(art),
            "sha256": SO_sha(art), "epochs": ep,
            "self_agreement": round(agree, 4),
            "flap_recall": round(flap_rec, 4),
            "train_s": train_s}
        print(f"e{ep}: agree={agree:.4f} flap_rec={flap_rec:.4f} "
              f"({train_s}s)", flush=True)
    report["variants"] = variants
    with open(os.path.join(SCR, "r58h_si_v2_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=1))


def SO_sha(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    main()
