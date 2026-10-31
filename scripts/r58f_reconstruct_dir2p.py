#!/usr/bin/env python3
"""r58f_reconstruct_dir2p.py — reconstruct the TRUE iter-0 dir-2-plus ARS
candidate from the committed si_v1 artifact + the committed r57f ARS
procedure (seeded rng), and analyze the champion-vs-candidate residual.

Background (r58 forensic finding): the champion npz is NOT the recorded
dir-2-plus sample (r58e: cos 0.56, norm 2.08 vs expected 1.21). The
candidate itself is offline-reconstructable because the r57f delta
stream is seeded (57 + it*1_000_003). This script:
  1. rebuilds theta_true = si_v1 + 0.03*delta_2(iter-0),
  2. saves it as a proper TinyMLP artifact r58_dir2p_true.npz (si_v1's
     meta/norm verbatim — ARS perturbs weights only),
  3. projects the residual (champ - theta_true) on the iter-1 delta
     stream to test whether the rejected iter-1 mean update leaked into
     the saved champion.
No emulator, no frames.
"""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(REPO, "scripts"))
from r57f_es_ars import SIGMA, N_DIRS, ALPHA, TOP_B         # noqa: E402

DATA = os.path.join(REPO, "data", "learn")
SI = os.path.join(DATA, "r57_si_v1.npz")
CHAMP = os.path.join(DATA, "r57_es2_dir2p.npz")
OUT_ART = os.path.join(DATA, "r58_dir2p_true.npz")


def parts(art):
    z = np.load(art)
    names = ["W1", "b1", "W2", "b2"]
    return names, [z[n].astype(np.float32) for n in names]


def flat(art):
    z = np.load(art)
    return np.concatenate([z[n].ravel().astype(np.float64)
                           for n in ["W1", "b1", "W2", "b2"]])


def main():
    th_si = flat(SI)
    th_ch = flat(CHAMP)
    n = len(th_si)

    rng0 = np.random.default_rng(57 + 0 * 1_000_003)
    d0 = np.asarray([rng0.standard_normal(n) for _ in range(N_DIRS)])
    theta_true = th_si + SIGMA * d0[2]

    # --- save the true candidate as a real artifact ---
    names, arrs = parts(SI)
    off, rebuilt = 0, {}
    for nm, a in zip(names, arrs):
        sz = a.size
        rebuilt[nm] = theta_true[off:off + sz].astype(np.float32) \
            .reshape(a.shape)
        off += sz
    np.savez_compressed(OUT_ART, **rebuilt)
    # copy si_v1's meta verbatim (the norm/feature contract is the
    # INIT's; ARS never touches it)
    import shutil
    shutil.copyfile(SI + ".json", OUT_ART + ".json")

    # --- residual analysis: champ - theta_true vs the iter-1 stream ---
    resid = th_ch - theta_true
    rng1 = np.random.default_rng(57 + 1 * 1_000_003)
    d1 = np.asarray([rng1.standard_normal(n) for _ in range(N_DIRS)])
    cos1 = [float(np.dot(resid, d1[i])
                  / (np.linalg.norm(resid) * np.linalg.norm(d1[i])
                     + 1e-30)) for i in range(N_DIRS)]
    cos0 = [float(np.dot(resid, d0[i])
                  / (np.linalg.norm(resid) * np.linalg.norm(d0[i])
                     + 1e-30)) for i in range(N_DIRS)]

    out = {
        "theta_true_saved": os.path.basename(OUT_ART),
        "theta_true_sha256": __import__("hashlib").sha256(
            open(OUT_ART, "rb").read()).hexdigest(),
        "resid_norm": float(np.linalg.norm(resid)),
        "resid_norm_over_expected_step": float(
            np.linalg.norm(resid) / (SIGMA * np.linalg.norm(d0[2]))),
        "resid_cosine_iter0_dirs": [round(c, 6) for c in cos0],
        "resid_cosine_iter1_dirs": [round(c, 6) for c in cos1],
        "note": "resid = champion - true_dir2p; if the rejected iter-1 "
                "mean leaked into the save, the iter-1 cosines should "
                "show structure (top dirs aligned); if the champion is "
                "an unrelated perturbation, cosines ~ N(0, 1/sqrt(n)).",
        "noise_level_1sigma": round(1.0 / np.sqrt(n), 6),
    }
    with open(os.path.join(REPO, "scratch", "r57",
                           "r58f_reconstruct.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
