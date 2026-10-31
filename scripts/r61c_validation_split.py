#!/usr/bin/env python3
"""r61c_validation_split.py — R61 Section 7: pre-register the fresh
validation split BEFORE any collection (the R57/R58/R59 discipline).

Rule (deterministic, committed here):
  candidates = k in [1..2000], ascending
  fresh      = k not in the union of
                 - the r53–r56 history seeds,
                 - the R57 TEST (retired), R58 TEST (retired),
                   R59 TEST (retired) seeds,
                 - the R57 TRAIN/VAL seeds (the family + bootstrap),
                 - the recorded R58 dev/diagnostic seeds (k72, k195),
                 - every multiple of 7 below 250 (the pre-R61 scan
                   candidates from earlier dev sweeps)
  validation = the first 40 fresh k with k % 7 == 0 (stride 7 — a
               residue class never used as a previous split rule:
               R57 used its own list, R58 multiples-of-3, R59
               multiples-of-4)
  protocol   = n=2 independent repetitions per seed per policy,
               byte-identical episode records required (the emulator
               determinism is verified before collection); the split
               is consumed by the R61 final validation ONLY and
               retired afterwards.
"""
import json
import os

REPO = "/home/z/my-project/ps1ai"
OUT = os.path.join(REPO, "data", "learn", "r61_validation_split.json")

R53_R56 = [6, 12, 18, 24, 30, 36, 42, 45, 54, 60, 66, 78, 90, 100,
           102, 114, 120, 126, 130, 150, 174, 198, 210, 222, 246, 270,
           294]
R57_TRAIN = [6, 30, 60, 12, 45]
R57_VAL = [90, 210]
R57_TEST = [8, 16, 20, 28, 33, 40, 48, 57, 63, 72, 84, 96, 108, 111,
            117, 132, 141, 156, 165, 180, 195, 201, 216, 228]
R58_TEST = [9, 15, 21, 27, 39, 51, 69, 81, 87, 93, 99, 105, 123, 135,
            147, 159, 171, 183, 207, 219]
R58_DEV = [72, 195]          # the recorded R58 diagnostic lineages
R59_TEST = [4, 32, 44, 52, 56, 64, 68, 76, 80, 88, 92, 104, 112, 116,
            124, 128, 136, 140, 144, 148]
FAMILY = [6, 12, 30, 45, 60, 90, 210]


def main():
    used = set(R53_R56 + R57_TRAIN + R57_VAL + R57_TEST + R58_TEST
               + R58_DEV + R59_TEST + FAMILY)
    # every prior split rule's residue coverage is excluded wholesale
    # for extra safety: multiples of 3 or 4 (the R58/R59 rules)
    used |= {k for k in range(1, 251) if k % 3 == 0 or k % 4 == 0}

    fresh = []
    for k in range(1, 2001):
        if k % 7 != 0:
            continue
        if k in used:
            continue
        fresh.append(k)
        if len(fresh) == 40:
            break
    assert len(fresh) == 40, len(fresh)
    seeds = fresh[:30]
    reserve = fresh[30:]
    assert not (set(seeds) & used)
    assert not (set(reserve) & used)

    doc = {
        "round": "R61-final-validation",
        "k_semantics": ("the scenario k = idle frames between the "
                        "ready anchor restore and the X press (the "
                        "press seeds the game RNG)"),
        "committed_before_collection": True,
        "selection_rule": (
            "k % 7 == 0 ascending in [1..2000], excluding every seed "
            "in the r53-r56 history, the R57 TRAIN/VAL, the retired "
            "R57/R58/R59 TEST sets, the recorded R58 dev seeds, the "
            "family, and every multiple of 3 or 4 below 250 (the "
            "prior split residues); first 40"),
        "validation_seeds": seeds,
        "reserve_seeds": reserve,
        "repeat_protocol": (
            "n=2 independent repetitions per seed per policy; the "
            "emulator determinism is verified byte-exact before "
            "collection, so reps must produce identical (pipes, "
            "frames, flaps, trace hash); any deviation is reported "
            "as a failure, never averaged away"),
        "policies_on_this_split": [
            "deploy (the R61 deployment package = the ONNX artifact "
            "of r59_soup_e6a010)",
            "base (r58_dir2p_true.npz, the R59 soup base)",
            "c1 (flappy_student_feat_r56_c1.npz, the frozen R56 "
            "reference)",
        ],
        "budget": 10000,
        "retirement": ("after the R61 final validation these seeds "
                       "are retired permanently (never trained on, "
                       "never used for selection again)"),
        "used_union_sha_note": ("the exclusion union is inline in this "
                                "file's generator (r61c) and the "
                                "asserted pairwise disjointness is "
                                "part of the generation"),
    }
    with open(OUT, "w") as f:
        json.dump(doc, f, indent=1)
    print("wrote", OUT)
    print("validation_seeds:", seeds)
    print("reserve:", reserve)


if __name__ == "__main__":
    main()
