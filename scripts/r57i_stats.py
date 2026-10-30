#!/usr/bin/env python3
"""r57i_stats.py — R57 P5: the TEST statistics + the final evidence JSON.

Inputs: the TEST eval summaries in scratch/r57 (TEST_champ_*, TEST_c1_*,
TEST_boot_*). One evidence file per the mission's deliverables list:
  data/learn/r57_flappy_evidence.json
"""
import glob
import json
import os

import numpy as np

REPO = "/home/z/my-project/ps1ai"
SCR = os.path.join(REPO, "scratch", "r57")
LEARN = os.path.join(REPO, "data", "learn")
TEST_SEEDS = [8, 16, 20, 28, 33, 40, 48, 57, 63, 72, 84, 96, 108, 111,
              117, 132, 141, 156, 165, 180, 195, 201, 216, 228]


def collect(pattern):
    per_seed = {}
    model = None
    sha = None
    for f in sorted(glob.glob(os.path.join(SCR, pattern))):
        with open(f) as fh:
            d = json.load(fh)
        model = model or d["model"]
        sha = sha or d["model_sha256"]
        for r in d["rows"]:
            per_seed.setdefault(r["k"], []).append(r["pipes"])
    return {"model": model, "sha256": sha,
            "per_seed": {k: sorted(v) for k, v in sorted(per_seed.items())}}


def stats(per_seed):
    med = np.asarray([np.median(v) for k, v in sorted(per_seed.items())])
    allv = np.concatenate([np.asarray(v, float)
                           for v in per_seed.values()])
    return {
        "n_seeds": len(per_seed),
        "per_seed_median_of_reps": {k: float(np.median(v))
                                    for k, v in sorted(per_seed.items())},
        "mean": round(float(allv.mean()), 2),
        "median_of_seed_medians": round(float(np.median(med)), 2),
        "p25": round(float(np.percentile(allv, 25)), 2),
        "p75": round(float(np.percentile(allv, 75)), 2),
        "min": round(float(allv.min()), 2),
        "max": round(float(allv.max()), 2),
        "std": round(float(allv.std(ddof=1)), 2),
        "n10": int((med >= 10).sum()), "n20": int((med >= 20).sum()),
        "n30": int((med >= 30).sum()), "n40": int((med >= 40).sum()),
        "n50": int((med >= 50).sum()),
        "n_alive_at_budget": sum(
            1 for v in per_seed.values() if max(v) >= 87),
    }


def main():
    champ = collect("eval_TEST_champ_*.json")
    c1 = collect("eval_TEST_c1_*.json")
    boot = collect("eval_TEST_boot_*.json")
    ev = {
        "/round": "R57-learn",
        "/date": "2026-10-31",
        "/mission": ("the student must learn beyond the teacher: "
                     "20-pipe capped bootstrap -> teacher-off "
                     "self-improvement (SI + ARS) -> 24 unseen TEST seeds"),
        "base_commit": "2d2c41e217cf",
        "protocol": {
            "budget": 10000,
            "test_seeds": TEST_SEEDS,
            "seed_provenance": "never booted in r53-r56 (the committed "
                               "split file data/learn/r57_seed_splits.json)",
            "reps": "champion n=3 (identical values within seed — the "
                    "determinism finding); references n=1 (disclosed)",
            "passage_metric": "the single-source-of-truth visual "
                              "PassageCounter (r53 band-jump convention; "
                              "validated by reproducing C1=173 exactly)",
            "no_ram": "student runs read NO RAM (visual death + visual "
                      "passages only; AST-scanned, teacher-import "
                      "blocked, hashed traces per run)",
        },
        "c1_reproduction": json.load(
            open(os.path.join(SCR, "r57c_repro.json")))["agg"],
        "champion": {"name": "r57_es2_dir2p.npz",
                     "lineage": "teacher(20-pipe capped) -> "
                                "r57_bootstrap_bc -> self-imitation v1 "
                                "(own lives only) -> ARS iter-0 dir-2-plus "
                                "selection (sigma 0.03)",
                     **stats(champ["per_seed"]),
                     "per_seed": champ["per_seed"],
                     "sha256": champ["sha256"]},
        "reference_c1": {"name": "flappy_student_feat_r56_c1.npz",
                         "note": "the frozen R56 champion (NEVER "
                                 "rewritten); historical-only under the "
                                 "20-pipe rule (its BC data reached the "
                                 "teacher's 51-pipe life)",
                         **stats(c1["per_seed"]),
                         "per_seed": c1["per_seed"],
                         "sha256": c1["sha256"]},
        "reference_bootstrap": {"name": "r57_bootstrap_bc.npz",
                                "lineage": "BC on the capped teacher "
                                           "demonstrations only",
                                **stats(boot["per_seed"]),
                                "per_seed": boot["per_seed"],
                                "sha256": boot["sha256"]},
        "gates": {
            "si_v2_rejected": "k60 29->20 (regression > 5)",
            "es2_iter1_mean_rejected": "k90 68->43, k60 29->20",
            "dir2p_promoted": "VAL k90 68 (=champ), k210 13 (-3, within "
                              "the gate); adds k60 87, k12 87",
        },
        "determinism_finding": ("within-boot restores AND cross-boot "
                                "episodes are byte-identical for fixed "
                                "(anchor, k, inputs): the teacher npz "
                                "shas repeat across 3 boots; n=3 reps "
                                "return identical values"),
    }
    with open(os.path.join(LEARN, "r57_flappy_evidence.json"), "w") as f:
        json.dump(ev, f, indent=2)
    for name in ("champion", "reference_c1", "reference_bootstrap"):
        s = ev[name]
        print(name, s["model"] if "model" in s else s.get("name"),
              "| mean", s["mean"], "| med-of-med", s["median_of_seed_medians"],
              "| n20/30/40/50", s["n20"], s["n30"], s["n40"], s["n50"])


if __name__ == "__main__":
    main()
