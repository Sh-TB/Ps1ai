#!/usr/bin/env python3
"""r57e_train_bootstrap.py — R57 P1: the QUALIFIED bootstrap student.

Offline, zero boots. Inputs: scratch/r57/tb_life_e*.npz (capped teacher
demonstrations) + tb_manifest.json.

Pipeline:
  1. rebuild the EXACT Brain._vector decision vectors per step (the
     r56b mirror: BirdObserverV7 + GapTrackerV7 + features_flappy_v7 +
     the policy's own history), class order [HOVER, FLAP];
  2. the row-level provenance manifest (episode_id, k, frame_index,
     passed_pipe_count, action, split) — the mission PART 1 manifest;
  3. train the C1 recipe VERBATIM (TinyMLP 10-128-2, seed 11, CE,
     FLAP tile x4, sqrt-balanced class weights, epochs 60, batch 128,
     lr 3e-3) on the CAPPED dataset only;
  4. save data/learn/r57_bootstrap_bc.npz + sidecar with the dataset
     digest + the cutoff proof (test-enforced elsewhere).

Outputs:
  data/learn/r57_bootstrap_dataset.npz (+ .json provenance manifest)
  data/learn/r57_bootstrap_bc.npz (+ .json sidecar)
  data/learn/r57_bootstrap_train_report.json
"""
import hashlib
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

SCR = os.path.join(REPO, "scratch", "r57")
LEARN = os.path.join(REPO, "data", "learn")
CLASSES = ["HOVER", "FLAP"]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def mirror_life(frames, acts):
    """EXACT Brain._vector/act mirror (r56b_miner.mirror_vectors)."""
    obs = VO.BirdObserverV7()
    gtr = VO.GapTrackerV7()
    X = []
    since_flap, flap_run = 99, 0
    last_gc, since_gap = -1.0, 40
    prev_action = None
    for i in range(len(acts)):
        cur = frames[i]
        by_obs, vy_obs = obs.step(cur, prev_action)
        gc_raw, dx, g0, g1, _b = VO._flappy_gap_raw2(cur, by_hint=by_obs)
        gc_obs = gtr.step((gc_raw, g0, g1, dx + 160.0))
        X.append(VO.features_flappy_v7(
            cur, by_obs, vy_obs, since_flap=since_flap,
            last_gc=last_gc, since_gap=since_gap, flap_run=flap_run,
            gc_obs=gc_obs))
        a = acts[i]
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
    return np.asarray(X, dtype=np.float32)


def main():
    with open(os.path.join(SCR, "tb_manifest.json")) as f:
        manifest = json.load(f)
    assert manifest["cutoff_proof"], "cutoff proof failed"

    Xs, Ys, meta_rows = [], [], []
    ep_index = []
    frame_index = []
    passed_at_row = []
    for ep_i, ep in enumerate(manifest["episodes"]):
        z = np.load(os.path.join(SCR, ep["npz"]))
        frames = z["frames"]
        acts = [str(a) for a in z["actions"]]
        X = mirror_life(frames, acts)
        Y = np.asarray([CLASSES.index(a) for a in acts], dtype=np.int64)
        Xs.append(X)
        Ys.append(Y)
        ep_index.append(np.full(len(Y), ep_i, dtype=np.int32))
        frame_index.append(np.arange(len(Y), dtype=np.int32))
        # passed_pipe_count at each row: the passage events BEFORE the row
        events = []
        # rebuild per-row pipe counts from the manifest's cutoff info:
        # rows are [0, n_labels); the episode's passages completed at
        # the cutoff (20) or died earlier (passages < 20). The exact
        # per-row count: count band-jump events up to that row from the
        # recorded band_x series (the same detector, replayed offline).
        band = z["band_x"]
        last = None
        cnt = 0
        for i in range(len(Y)):
            bx = band[i]
            if bx is not None and bx >= 0:
                if last is not None and bx > last + 60:
                    cnt += 1
                last = float(bx)
            passed_at_row.append(cnt)
        meta_rows.append({
            "episode_index": ep_i, "episode_id": ep["episode_id"],
            "k": ep["k"], "n_rows": int(len(Y)),
            "source_type": "teacher",
            "source_checkpoint": ep["source_checkpoint"],
            "frame_index_range": [0, int(len(Y) - 1)],
            "max_passed_pipe_count_in_rows": int(cnt),
            "row_bound_note": ("rows [0, cutoff_step): the action at the "
                               "last row is the one whose execution "
                               "completes the 20th passage; the cutoff "
                               "step's own action is EXCLUDED; the "
                               "offline pre-run band recount lags the "
                               "live post-run counter by one event"),
            "cutoff_step": ep["cutoff_step"],
            "npz_sha256": ep["npz_sha256"],
            "npz": ep["npz"],
        })
        print(f"{ep['episode_id']} k={ep['k']} rows={len(Y)} "
              f"pipes={cnt}", flush=True)
    X = np.concatenate(Xs)
    Y = np.concatenate(Ys)
    ep_index = np.concatenate(ep_index)
    frame_index = np.concatenate(frame_index)
    passed_at_row = np.asarray(passed_at_row, dtype=np.int32)

    # THE QUALIFICATION INVARIANT (mission PART 1, test-enforced too):
    assert int(passed_at_row.max()) <= 20, (
        f"teacher label beyond pipe 20: {passed_at_row.max()}")
    ds_npz = os.path.join(LEARN, "r57_bootstrap_dataset.npz")
    np.savez_compressed(
        ds_npz, X=X, Y=Y, episode_index=ep_index,
        frame_index=frame_index, passed_pipe_count=passed_at_row)
    ds_meta = {
        "round": "R57 P1", "format": "r57-capped-bc-dataset-v1",
        "classes": CLASSES, "n_rows": int(len(Y)),
        "rows_sha_note": ("row identity = (episode_id, frame_index); "
                          "provenance_hash = sha256 of the episode npz "
                          "recorded per episode below"),
        "dataset_sha256": sha256_file(ds_npz),
        "cap_rule": ("no teacher action beyond the first 20 visually "
                     "confirmed pipes per episode; the cutoff step's "
                     "own label excluded"),
        "max_passed_pipe_count": int(passed_at_row.max()),
        "episodes": meta_rows,
        "teacher": manifest["teacher"],
        "teacher_params": manifest["teacher_params"],
        "boot_ids": manifest["boot_ids"],
        "cutoff_proof": manifest["cutoff_proof"],
    }
    with open(ds_npz + ".json", "w") as f:
        json.dump(ds_meta, f, indent=2)

    # ---- the C1 recipe verbatim on the capped dataset ----
    idx = np.nonzero(Y == 1)[0]
    extra = np.tile(idx, 4)
    Xb = np.concatenate([X, X[extra]])
    Yb = np.concatenate([Y, Y[extra]])
    counts = np.bincount(Yb, minlength=2)
    cw = np.clip((counts.sum() / (2.0 * np.maximum(counts, 1)))
                 ** 0.5, 0.5, 3.0).astype(np.float32)
    mu, sd = X.mean(0), X.std(0) + 1e-6
    net = TinyMLP(X.shape[1], 128, 2, seed=11)
    t0 = time.time()
    net.fit((Xb - mu) / sd, np.eye(2, dtype=np.float32)[Yb],
            epochs=60, batch=128, lr=3e-3, classification=True,
            seed=11, class_weights=cw)
    train_s = round(time.time() - t0, 1)

    art = os.path.join(LEARN, "r57_bootstrap_bc.npz")
    info = net.save_artifact(art, meta={
        "game": "flappy", "control_mode": "cv+mlp",
        "feature_version": 7, "classes": CLASSES,
        "norm": {"mean": mu.tolist(), "std": sd.tolist()},
        "teacher": "flappy_law_on_v7 (r15 law + BirdObserverV7 + "
                   "GapTrackerV7, same-sensor pathway)",
        "teacher_provenance":
            "QUALIFIED R57 bootstrap: BC on the capped teacher "
            "demonstrations r57_tb_e01..e10 (10 episodes, cap 20 "
            "visually confirmed passages, cutoff-step label excluded); "
            "dataset sha256 " + ds_meta["dataset_sha256"][:16],
        "dataset": "r57_bootstrap_dataset.npz",
        "dataset_sha256": ds_meta["dataset_sha256"],
        "recipe": "tinymlp 10-128-2, seed 11, CE, flap tile x4, "
                  "sqrt-balanced class weights, epochs 60, batch 128, "
                  "lr 3e-3 (the C1 recipe verbatim)",
        "n_steps": int(len(Y)), "trained_at": time.time()})

    # offline per-episode agreement (in-sample, honest label)
    pred = net.predict((X - mu) / sd).argmax(1)
    per_ep = {}
    for ep_i, ep in enumerate(meta_rows):
        m = ep_index == ep_i
        acc = float((pred[m] == Y[m]).mean())
        flap_rec = float((pred[m][Y[m] == 1] == 1).mean())
        per_ep[ep["episode_id"]] = {
            "acc": round(acc, 4),
            "flap_recall": round(flap_rec, 4) if (Y[m] == 1).any() else -1}
    report = {
        "round": "R57 P1", "artifact": info,
        "recipe": {"hidden": 128, "epochs": 60, "batch": 128,
                   "lr": 3e-3, "seed": 11, "flap_tile": 4,
                   "train_s": train_s},
        "dataset_rows": int(len(Y)),
        "max_teacher_pipe": int(passed_at_row.max()),
        "in_sample_agreement": per_ep,
        "mean_acc": round(float(np.mean([v["acc"]
                                         for v in per_ep.values()])), 4),
    }
    with open(os.path.join(LEARN, "r57_bootstrap_train_report.json"),
              "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps({k: v for k, v in report.items()
                      if k != "in_sample_agreement"}, indent=2))
    print("per-episode:", json.dumps(per_ep))


if __name__ == "__main__":
    main()
