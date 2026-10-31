#!/usr/bin/env python3
"""r58e_provenance_theta.py — OFFLINE provenance test: is the champion
npz EXACTLY si_v1 + SIGMA * delta_2 (the iter-0 dir-2-plus ARS sample)?

r57f_es_ars samples deltas as
    rng = np.random.default_rng(57 + it * 1_000_003)
    deltas = [rng.standard_normal(n_params) for _ in range(N_DIRS)]
and the dir-2-plus candidate is theta + SIGMA*deltas[2] with SIGMA=0.03.
No emulator, no frames — pure arithmetic on the committed artifacts.
"""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(REPO, "scripts"))
from r57f_es_ars import SIGMA, N_DIRS                      # noqa: E402

DATA = os.path.join(REPO, "data", "learn")
SI = os.path.join(DATA, "r57_si_v1.npz")
CHAMP = os.path.join(DATA, "r57_es2_dir2p.npz")


def flat(art):
    z = np.load(art)
    return np.concatenate([z["W1"].ravel().astype(np.float64),
                           z["b1"].ravel().astype(np.float64),
                           z["W2"].ravel().astype(np.float64),
                           z["b2"].ravel().astype(np.float64)])


def main():
    th_si = flat(SI)
    th_ch = flat(CHAMP)
    n = len(th_si)
    rng = np.random.default_rng(57 + 0 * 1_000_003)
    deltas = np.asarray([rng.standard_normal(n) for _ in range(N_DIRS)])

    d = th_ch - th_si
    out = {"n_params": int(n),
           "champ_minus_si_norm": float(np.linalg.norm(d)),
           "expected_step_norm": float(SIGMA * np.linalg.norm(deltas[2]))}
    cos = [float(np.dot(d, deltas[i])
                 / (np.linalg.norm(d) * np.linalg.norm(deltas[i]) + 1e-30))
           for i in range(N_DIRS)]
    out["cosine_vs_each_dir"] = [round(c, 9) for c in cos]
    # exactness: reconstruct and compare bit-level after f32 round-trip
    cand = th_si + SIGMA * deltas[2]
    out["exact_match_f32"] = bool(np.array_equal(
        cand.astype(np.float32).astype(np.float64), th_ch))
    out["max_abs_diff_vs_dir2plus_f32"] = float(np.max(np.abs(
        cand.astype(np.float32).astype(np.float64) - th_ch)))
    out["verdict"] = ("champion == si_v1 + 0.03*delta_2 (EXACT)"
                      if out["exact_match_f32"] else
                      "champion is NOT the iter-0 dir-2-plus sample")
    with open(os.path.join(REPO, "scratch", "r57",
                           "r58e_provenance_theta.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
