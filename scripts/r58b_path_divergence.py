#!/usr/bin/env python3
"""r58b_path_divergence.py — WHERE do the two decision paths diverge?

Path A (deployed): BrainClient subprocess -> visual_only.Brain.act.
Path B (training): r57f_es_ars.FlatPolicy.act (in-process).

The champion's k6 life was recorded through path A (63 pipes, death
@7345); the r57 ARS fitness for the SAME theta claimed 87 @10000 through
path B. Replay the RECORDED path-A frames through path B step by step
and find the first action mismatch — then dump both decision vectors.

Diagnostic only: no training, no labels, no teacher.
"""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.learn import visual_only as VO                 # noqa: E402
from r57f_es_ars import FlatPolicy                          # noqa: E402

ART = os.path.join(REPO, "data", "learn", "r57_es2_dir2p.npz")
LIFE = os.path.join(REPO, "scratch", "r57",
                    "life_r58_champ_k6_k6_r0.npz")
OUT = os.path.join(REPO, "scratch", "r57", "r58b_path_divergence.json")


def main():
    z = np.load(LIFE)
    frames = z["frames"]
    acts_a = z["actions"]
    n = len(frames)

    pol = FlatPolicy(ART)

    # -- replay through path B --
    acts_b = []
    pol.reset_obs()
    for i in range(n):
        acts_b.append(pol.act(frames[i]))

    mism = [i for i in range(n) if acts_b[i] != acts_a[i]]
    first = mism[0] if mism else None

    out = {"n_steps": int(n),
           "n_mismatch": len(mism),
           "first_mismatch_step": first,
           "a_actions_first10": [str(x) for x in acts_a[:10]],
           "b_actions_first10": [str(x) for x in acts_b[:10]],
           "a_pipes_area": None}
    if first is not None:
        lo = max(0, first - 5)
        out["context"] = {
            "steps": list(range(lo, min(n, first + 5))),
            "actions_a": [str(x) for x in acts_a[lo:first + 5]],
            "actions_b": [str(x) for x in acts_b[lo:first + 5]]}
        # both decision vectors at the mismatch step (fresh, parallel)
        fa = VO.Brain(ART)          # deployed path vector recompute
        fb = FlatPolicy(ART)
        xa = xb = None
        for i in range(first + 1):
            fr = frames[i]
            xa = fa._vector(fr)
            xb = fb.vector(fr)
            fa.act(fr)
            fb.observe_history(
                "FLAP" if int(np.argmax(fb.net.forward(
                    xb.reshape(1, -1))[0])) == 1 else "HOVER")
        out["vector_diff"] = {
            "max_abs": float(np.max(np.abs(xa - xb))),
            "argmax_abs": int(np.argmax(np.abs(xa - xb))),
            "xa": [round(float(v), 6) for v in xa.ravel()],
            "xb": [round(float(v), 6) for v in xb.ravel()]}
    with open(OUT, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps({k: v for k, v in out.items()
                      if k not in ("vector_diff",)}, indent=1))
    if "vector_diff" in out:
        vd = out["vector_diff"]
        print("vector max|diff|:", vd["max_abs"], "at", vd["argmax_abs"])
        print("xa:", vd["xa"])
        print("xb:", vd["xb"])


if __name__ == "__main__":
    main()
