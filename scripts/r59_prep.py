#!/usr/bin/env python3
"""r59_prep.py — R59 pre-collection preparation (run ONCE, then push).

1. Computes the R59 fresh-TEST seed list (multiples-of-4 rule in
   [1..250], ascending, excluding EVERY seed used in r53-r56 history,
   the R57 TEST set, the R58 TEST set, and all dev/diagnostic seeds of
   R58/R59) -> data/learn/r59_seed_splits.json
2. Saves the R59 soup candidate as a proper artifact
   data/learn/r59_soup_e6a010.npz (+ .json meta) — byte-identical
   weights to the measured scratch candidate
   (sha256 72c79f3091ed14e8...), meta norm/arch verbatim from the base.
3. Writes scripts/r59b_test.py runner constants sanity check.

No emulator, no frames. The split is committed BEFORE any TEST
collection (the fd1c1422 discipline).
"""
import hashlib
import json
import os

import numpy as np

REPO = "/home/z/my-project/ps1ai"
DATA = os.path.join(REPO, "data", "learn")
SCR = os.path.join(REPO, "scratch", "r59")

R57_TEST = [8, 16, 20, 28, 33, 40, 48, 57, 63, 72, 84, 96, 108, 111,
            117, 132, 141, 156, 165, 180, 195, 201, 216, 228]
R58_TEST = [9, 15, 21, 27, 39, 51, 69, 81, 87, 93,
            99, 105, 123, 135, 147, 159, 171, 183, 207, 219]
R53_56_HISTORY = [6, 12, 18, 24, 30, 36, 42, 45, 54, 60, 66, 78, 90,
                  100, 102, 114, 120, 126, 130, 150, 174, 198, 210,
                  222, 246, 270, 294]
R58_DEV = [6, 12, 30, 45, 60, 72, 90, 195, 210]
R59_DEV = [6, 12, 30, 45, 60, 90, 210]   # this round's probe seeds

USED = set(R57_TEST) | set(R58_TEST) | set(R53_56_HISTORY) \
    | set(R58_DEV) | set(R59_DEV)

seeds = []
for k in range(4, 251, 4):
    if k in USED:
        continue
    seeds.append(k)
    if len(seeds) == 20:
        break
assert len(seeds) == 20, seeds
assert not (set(seeds) & USED)

splits = {
    "round": "R59-continue",
    "parent_round": "R58-continue (issue #13, the R57 workstream)",
    "k_semantics": ("the scenario k = idle frames between the ready "
                    "anchor restore and the X press (the press seeds "
                    "the game RNG)"),
    "committed_before_collection": True,
    "candidate": "r59_soup_e6a010.npz",
    "candidate_provenance": (
        "linear-path soup point: theta = r58_dir2p_true + 0.10 * "
        "(r58_si_v2_e6 - r58_dir2p_true); weights sha256 "
        "72c79f3091ed14e8dd497ddc52570bb4660bfc6367e6b50eb8a8aa1eff8a28f4; "
        "family (deployed path, n=3 on VAL): k6 87 alive, k12 76@8798, "
        "k30 37@4401, k45 40@4753 (+7 vs base), k60 87 alive, "
        "k90 68@7895, k210 42@4966 — strictly dominates the base, "
        "regression gate PASS (VAL median delta 0, max drop 0)"),
    "test_selection_rule": ("multiples of 4 in [1..250], ascending, "
                            "excluding every seed used in r53-r56 "
                            "history, the R57 TEST set, the R58 TEST "
                            "set, and all R58/R59 dev seeds; first 20"),
    "test_never_used_before_this_round": seeds,
    "test_repeat_protocol": ("final candidate n=3 boots per seed; "
                             "references n=1: r58_dir2p_true.npz (the "
                             "R58 champion / the soup base) and "
                             "flappy_student_feat_r56_c1.npz (frozen "
                             "R56 reference); byte-determinism of the "
                             "deployed path verified repeatedly"),
    "test_retirement": ("after the R59 final evaluation these TEST "
                        "seeds are retired permanently (never trained "
                        "on, never used for selection)"),
    "excluded_used_seeds": {
        "r53_r56_history": R53_56_HISTORY,
        "r57_test_retired": R57_TEST,
        "r58_test_retired": R58_TEST,
        "r58_dev": R58_DEV,
        "r59_dev": R59_DEV,
    },
    "references_on_same_seeds": [
        "r58_dir2p_true.npz (the R58 champion, the soup base)",
        "flappy_student_feat_r56_c1.npz (the frozen R56 reference)",
    ],
}
path = os.path.join(DATA, "r59_seed_splits.json")
json.dump(splits, open(path, "w"), indent=1)
print("wrote", path, "seeds:", seeds)

# --- the artifact ---
src = np.load(os.path.join(SCR, "lin_r58_si_v2_e6_a0.1.npz"))
out = {n: src[n] for n in ("W1", "b1", "W2", "b2")}
art = os.path.join(DATA, "r59_soup_e6a010.npz")
np.savez_compressed(art, **out)
sha = hashlib.sha256(open(art, "rb").read()).hexdigest()
assert sha == ("72c79f3091ed14e8dd497ddc52570bb4660bfc6367e6b50eb"
               "8a8aa1eff8a28f4"), sha
print("artifact bytes-identical to the measured candidate:", sha[:16])

meta = json.load(open(os.path.join(DATA, "r58_dir2p_true.npz.json")))
meta["teacher"] = ("R59 soup: r58_dir2p_true + 0.10 * "
                   "(r58_si_v2_e6 - r58_dir2p_true); no new training, "
                   "a convex combination of two working self-imitation "
                   "checkpoints")
meta["init_checkpoint"] = "r58_dir2p_true.npz"
meta["soup"] = {
    "base": "r58_dir2p_true.npz",
    "donor": "r58_si_v2_e6.npz",
    "alpha": 0.1,
    "direction_norm": 1.0254,
    "family": {"k6": "87 alive", "k12": "76@8798", "k30": "37@4401",
               "k45": "40@4753", "k60": "87 alive", "k90": "68@7895",
               "k210": "42@4966"},
    "regression_gate": "PASS (VAL median delta 0, max drop 0)",
}
json.dump(meta, open(art + ".json", "w"), indent=1)
print("meta written")
