#!/usr/bin/env python3
"""msx_m2_candidates.py — offline ranker for the ATTRACT-FLAG RAM HUNT
(task 17-a).  No emulator: mines the FlipTracker npz that rg1 recorded
across the M1-end teardown -> NOW LOADING -> attract-hijack ladder
(rg1_045648, 26627 frames, 1,027,796 changed bytes) plus rg4's
gatestart npz as a game-stabilized reference.

Ranking idea (session-9 recorded lever): the attract flag = a byte that
  (a) is STABLE during the pure-loading stretch,
  (b) flips EXACTLY at the attract-hijack onset and STAYS flipped,
  (c) looks like a flag (0/1-ish values), not a counter.
rg1 timeline anchors (from its PNGs/ladder): teardown ~f0 (relative to
the tracker start), dark/loading f2000-4000, first attract world
f5435 (px 236).  Hijack onset (logo cinematic) ~= f4300-5500.

Outputs: scratch/issue6_round7_msx/candidates.json with ranked tables
+ a shortlist for the force test.
"""
import json
import os
import sys

import numpy as np

EVID = "/home/z/my-project/ps1ai/scratch/issue6_round7_msx"
NPZ = os.path.join(EVID, "rg1_045648_tracker.npz")

# rg1 relative-frame anchors (post-teardown ladder)
LOAD_END = 4200       # loading/dark stretch ends around here
HIJACK_LO, HIJACK_HI = 4200, 5600   # logo cinematic + world spawn
WORLD_AT = 5435


def main():
    d = np.load(NPZ, allow_pickle=False)
    meta = json.loads(str(d["meta"]))
    val0, final = d["val0"], d["final"]
    first_f, last_f, count = d["first_f"], d["last_f"], d["count"]
    print("meta:", json.dumps(meta)[:400])
    print("bytes:", len(val0), "changed:", int((count > 0).sum()))

    changed = count > 0
    rows = []
    idx = np.flatnonzero(changed)
    for j in idx:
        f0, f1, c = int(first_f[j]), int(last_f[j]), int(count[j])
        v0, vf = int(val0[j]), int(final[j])
        # (b) flips at the hijack window and stays (last change in window)
        if not (HIJACK_LO <= f0 <= HIJACK_HI and f1 >= WORLD_AT - 400):
            continue
        # (a) NOT churning during loading: first change not early-loading
        #     (f0 already constrained), count small (1-4)
        if c > 4:
            continue
        # (c) flag-like: small magnitudes and a small delta
        if max(v0, vf) > 0x1000 or abs(vf - v0) > 0x1000:
            continue
        rows.append({"addr": int(j), "val0": v0, "final": vf,
                     "first_f": f0, "last_f": f1, "count": c})

    # rank: flip closest to the observed onset, single-change first
    def rank(r):
        return (r["count"], abs(r["first_f"] - WORLD_AT))

    rows.sort(key=rank)
    out = {"meta": meta, "n_changed": int(changed.sum()),
           "hijack_window": [HIJACK_LO, HIJACK_HI],
           "world_at": WORLD_AT, "candidates": rows[:80]}
    with open(os.path.join(EVID, "candidates.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(f"candidates: {len(rows)} (top {min(40, len(rows))})")
    for r in rows[:40]:
        print(f"  0x{r['addr']:06X}  {r['val0']:>3} -> {r['final']:>3}"
              f"  first_f={r['first_f']} last_f={r['last_f']}"
              f" n={r['count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
