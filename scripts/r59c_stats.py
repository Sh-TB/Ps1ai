#!/usr/bin/env python3
"""r59c_stats.py — R59 fresh-TEST statistics (paired, per-seed).

Reads scratch/r57/r59_test_rows.jsonl (the r59b_test.py output) and
produces:
  * per-model TEST table (per-seed mean over reps, then mean/median/
    min/floor + depth tails),
  * the paired per-seed contrast soup vs base (W/T/L, mean delta),
  * the same vs C1,
  * the per-seed table with reps.
No emulator.
"""
import json
import os
from collections import defaultdict

import numpy as np

REPO = "/home/z/my-project/ps1ai"
ROWS = os.path.join(REPO, "scratch", "r57", "r59_test_rows.jsonl")

rows = [json.loads(l) for l in open(ROWS) if l.strip()]
by_mk = defaultdict(list)
for r in rows:
    by_mk[(r["model"], r["k"])].append(r["pipes"])

per_seed = defaultdict(dict)
for (m, k), v in by_mk.items():
    per_seed[m][k] = float(np.mean(v))

models = ["r59_soup_e6a010.npz", "r58_dir2p_true.npz",
          "flappy_student_feat_r56_c1.npz"]
LABEL = {"r59_soup_e6a010.npz": "soup",
         "r58_dir2p_true.npz": "base(r58champ)",
         "flappy_student_feat_r56_c1.npz": "C1"}

seeds = sorted(per_seed[models[0]].keys())
print(f"seeds n={len(seeds)}: {seeds}")
for m in models:
    assert len(per_seed[m]) == len(seeds), (m, len(per_seed[m]))

table = {}
for m in models:
    v = np.array([per_seed[m][k] for k in seeds])
    reps = {k: len(by_mk[(m, k)]) for k in seeds}
    table[m] = {
        "mean": round(float(v.mean()), 2),
        "median": round(float(np.median(v)), 1),
        "min": float(v.min()), "max": float(v.max()),
        "ge40": int((v >= 40).sum()), "ge50": int((v >= 50).sum()),
        "ge60": int((v >= 60).sum()), "alive": int(
            (v >= 85).sum()),
    }
    print(f"{LABEL[m]:>14}: mean {table[m]['mean']:6.2f}  "
          f"median {table[m]['median']:5.1f}  min {table[m]['min']:5.1f}"
          f"  max {table[m]['max']:5.1f}  >=40 {table[m]['ge40']:2d}/20"
          f"  >=50 {table[m]['ge50']:2d}/20  >=85(alive-ish) "
          f"{table[m]['alive']:2d}/20")

for ref in models[1:]:
    d = np.array([per_seed[models[0]][k] - per_seed[ref][k]
                  for k in seeds])
    w = int((d > 0).sum()); t = int((d == 0).sum()); l = int((d < 0).sum())
    print(f"\npaired soup - {LABEL[ref]}: mean {d.mean():+.2f}  "
          f"W/T/L {w}/{t}/{l}  max_gain +{d.max():.0f}  "
          f"max_loss {d.min():.0f}")
    for k in seeds:
        dv = per_seed[models[0]][k] - per_seed[ref][k]
        if abs(dv) > 0.5:
            print(f"   k{k:>3}: soup {per_seed[models[0]][k]:5.1f}  "
                  f"{LABEL[ref]} {per_seed[ref][k]:5.1f}  "
                  f"delta {dv:+6.1f}")

reps_check = {}
for m in models:
    for k in seeds:
        vals = by_mk[(m, k)]
        if len(set(vals)) > 1:
            reps_check[f"{LABEL[m]}_k{k}"] = vals
print("\nrep-consistency (should be empty = byte-identical reps):",
      reps_check or "ALL IDENTICAL")

out = {
    "round": "R59-continue",
    "split": "data/learn/r59_seed_splits.json (committed "
             "21f3e0d3c8d1 BEFORE collection)",
    "seeds": seeds,
    "episodes": len(rows),
    "table": {LABEL[m]: table[m] for m in models},
    "per_seed": {LABEL[m]: {k: per_seed[m][k] for k in seeds}
                 for m in models},
    "reps_identical": not reps_check,
    "reps_diff": reps_check,
}
p = os.path.join(REPO, "scratch", "r59", "r59_test_stats.json")
os.makedirs(os.path.dirname(p), exist_ok=True)
json.dump(out, open(p, "w"), indent=1)
print("wrote", p)
