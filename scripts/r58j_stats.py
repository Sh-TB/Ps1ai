#!/usr/bin/env python3
"""r58j_stats.py — the R58 fresh-TEST statistics (20 unseen seeds).

Reads scratch/r57/r58_test_rows.jsonl, verifies the champion's n=3
determinism per seed, and emits the summary tables + paired contrasts
to scratch/r57/r58_test_stats.json.
"""
import json
import os
from collections import defaultdict

import numpy as np

REPO = "/home/z/my-project/ps1ai"
SCR = os.path.join(REPO, "scratch", "r57")
ROWS = os.path.join(SCR, "r58_test_rows.jsonl")

NAMES = {"r58_dir2p_true.npz": "champion_r58_dir2p_true",
         "r57_es2_dir2p.npz": "ref_r57_es2_dir2p",
         "flappy_student_feat_r56_c1.npz": "ref_c1_r56"}


def main():
    per = defaultdict(lambda: defaultdict(list))
    with open(ROWS) as f:
        for line in f:
            r = json.loads(line)
            per[NAMES[r["model"]]][r["k"]].append(r["pipes"])

    out = {"n_seeds": 0, "models": {}, "determinism": {}}
    for model, seeds in per.items():
        med = {k: float(np.median(v)) for k, v in sorted(seeds.items())}
        allv = [x for v in seeds.values() for x in v]
        mos = list(med.values())
        out["models"][model] = {
            "per_seed_reps": {str(k): v for k, v in sorted(seeds.items())},
            "per_seed_median": med,
            "mean": round(float(np.mean(allv)), 2),
            "median_of_seed_medians": round(float(np.median(mos)), 1),
            "p25": round(float(np.percentile(mos, 25)), 2),
            "p75": round(float(np.percentile(mos, 75)), 2),
            "min": float(np.min(mos)), "max": float(np.max(mos)),
            "std": round(float(np.std(mos)), 2),
            "n_ge20": int(sum(m >= 20 for m in mos)),
            "n_ge30": int(sum(m >= 30 for m in mos)),
            "n_ge40": int(sum(m >= 40 for m in mos)),
            "n_ge50": int(sum(m >= 50 for m in mos)),
            "n_alive_at_budget": int(sum(
                max(v) >= 87 and all(x >= 80 for x in v)
                for v in seeds.values())),
            "n_episodes": len(allv),
        }
    ch = per["champion_r58_dir2p_true"]
    out["determinism"] = {
        str(k): {"reps": v,
                 "identical": bool(len(set(v)) == 1)}
        for k, v in sorted(ch.items())}
    out["n_seeds"] = len(ch)

    for ref in ("ref_r57_es2_dir2p", "ref_c1_r56"):
        d = []
        for k in sorted(ch):
            d.append(float(np.median(ch[k]))
                     - float(np.median(per[ref][k])))
        out[f"paired_delta_vs_{ref}"] = {
            "mean": round(float(np.mean(d)), 2),
            "median": round(float(np.median(d)), 2),
            "wins": int(sum(x > 0 for x in d)),
            "ties": int(sum(x == 0 for x in d)),
            "losses": int(sum(x < 0 for x in d)),
            "per_seed": {str(k): round(v, 1) for k, v in
                         zip(sorted(ch), d)}}

    with open(os.path.join(SCR, "r58_test_stats.json"), "w") as f:
        json.dump(out, f, indent=1)
    for m in out["models"]:
        s = out["models"][m]
        print(f"{m}: mean={s['mean']} med={s['median_of_seed_medians']} "
              f"min={s['min']} max={s['max']} n20={s['n_ge20']} "
              f"n30={s['n_ge30']} n40={s['n_ge40']} n50={s['n_ge50']}")
    print("champion determinism:",
          all(v["identical"] for v in out["determinism"].values()))
    for ref in ("ref_r57_es2_dir2p", "ref_c1_r56"):
        p = out[f"paired_delta_vs_{ref}"]
        print(f"vs {ref}: mean_delta={p['mean']} "
              f"W/T/L={p['wins']}/{p['ties']}/{p['losses']}")


if __name__ == "__main__":
    main()
