#!/usr/bin/env python3
"""msx_m2_candidates8.py — round 8 (task 8-a) OFFLINE ranker for the
M1-end vs M2-side loading diff.

Inputs: the per-window FlipTracker npz files written by
msx_m1end_m2side_diff.py (val0, first_f, last_f, count, final per RAM
byte; window A = m2_train M2-live, B = m1_end quiet/attract path,
C = m1_end START-tap detour, D = M1-live, E = m1_end ride-along).

Families (the surgical diff-of-diffs):
  M2PATH   bytes that TRANSITION in an M2-reaching loading window and
           END at the M2-live value (A.final), never churning in A
           (mission-state flags must be stable in live M2 play).
  ATTRACTONLY  bytes that transition in the M1-end quiet path (B) but
           never in the M2-reaching ride window (E) — the reverse arm.
Ranking: window agreement, M1-contrast (D.final != A.final), small-u32
0x0 -> {1,2,3} transition shape at the containing aligned u32,
proximity to the known scene globals, ENEMY.BIN overlay membership,
early flip frame inside the loading phase.

Outputs (scratch/issue6_round8_msx/): candidates8.csv (full M2PATH
table), candidates8_top.json (ranked top-N with decoded fields),
pages8.json (4KB-page aggregation).
"""
import argparse
import csv
import json
import os
import sys

import numpy as np

SCRATCH = "/home/z/my-project/ps1ai/scratch/issue6_round8_msx"
KNOWN = (("flags32", 0x0EE518), ("score", 0x0EE318), ("gren", 0x0EDCF4),
         ("px", 0x0CA2E0), ("php", 0x0CA2F6), ("sec_st", 0x0EB5F4),
         ("sec_fl", 0x0EB5D0), ("prog", 0x0EB5D4),
         ("move_acc16", 0x0EB858), ("entity_root", 0x0C9A98))
OVERLAY_ENEMY = (0x9C0E8, 0x9C0E8 + 115400)


def load_trk(tag, key):
    path = os.path.join(SCRATCH, f"{tag}_trk{key}.npz")
    if not os.path.exists(path):
        return None
    z = np.load(path)
    return {k: z[k] for k in ("val0", "first_f", "last_f", "count",
                              "final")}


def u32_at(arr, off):
    b = arr[off:off + 4].astype(np.uint32)
    return int(b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atag", default="diff2_074813",
                    help="tag of the run that produced trkA/B/C/D")
    ap.add_argument("--etag", default="diff3",
                    help="tag prefix of the run that produced trkE")
    ap.add_argument("--top", type=int, default=64)
    args = ap.parse_args()

    W = {}
    for key in "ABCDE":
        tag = args.etag if key == "E" else args.atag
        z = load_trk(tag, key)
        if z is not None:
            W[key] = z
            print(f"window {key}: {int((z['count'] > 0).sum())} bytes "
                  f"changed ({tag})")
    A = W.get("A")
    if A is None:
        print("FATAL: window A (M2-live) missing")
        return 1
    A_final = A["final"]
    A_stable = A["count"] == 0          # never churned in live M2

    # which windows represent the M2-REACHING loading path?
    m2_path = [k for k in ("E", "C", "B") if k in W]
    report_meta = {"m2_path_windows": m2_path}

    rows = []
    n = len(A_final)
    for key in m2_path:
        w = W[key]
        ch = w["count"] > 0
        m2val = ch & (w["final"] == A_final) & A_stable
        idx = np.flatnonzero(m2val)
        print(f"M2PATH[{key}]: {idx.size} bytes")
        rows.append((key, idx))

    if not rows:
        print("FATAL: no M2PATH bytes at all")
        return 1

    # intersection across all M2-path windows = agreement
    agree = None
    for key, idx in rows:
        s = set(idx.tolist())
        agree = s if agree is None else (agree & s)
    agree_idx = np.fromiter(sorted(agree), dtype=np.int64) if agree else \
        np.array([], dtype=np.int64)
    print(f"AGREE across {len(rows)} M2-path windows: {agree_idx.size}")

    D = W.get("D")
    D_final = D["final"] if D is not None else None
    B = W.get("B")
    E = W.get("E")

    out = []
    for off in agree_idx.tolist():
        base = off & ~3

        def u32a(arr):
            b = arr[base:base + 4]
            return int(b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24))
        a_u32 = u32a(A_final)
        b_v0 = u32a(B["val0"]) if B is not None else None
        b_f = u32a(B["final"]) if B is not None else None
        e_v0 = u32a(E["val0"]) if E is not None else None
        e_f = u32a(E["final"]) if E is not None else None
        d_f = u32a(D_final) if D_final is not None else None
        # small-index transition shape at the CONTAINING u32
        small_shape = False
        for (v0, v1) in ((b_v0, b_f), (e_v0, e_f)):
            if v0 is not None and v1 is not None and v0 == 0 \
                    and v1 in (1, 2, 3):
                small_shape = True
        near = min(((abs(off - a), nm) for nm, a in KNOWN),
                   key=lambda t: t[0])
        in_overlay = OVERLAY_ENEMY[0] <= off < OVERLAY_ENEMY[1]
        first_e = int(E["first_f"][off]) if E is not None else -1
        first_b = int(B["first_f"][off]) if B is not None else -1
        score = 0
        score += 3 if E is not None else 0          # ride window present
        score += 2 if (D_final is not None
                       and int(D_final[off]) != int(A_final[off])) else 0
        score += 2 if small_shape else 0
        score += 2 if near[0] <= 0x100 else 0
        score += 1 if in_overlay else 0
        if 0 <= first_e <= 2700:                     # flip inside loading
            score += 1
        out.append({
            "addr": f"0x{off:06X}", "off": off,
            "A_final": int(A_final[off]),
            "B_val0": int(B["val0"][off]) if B is not None else None,
            "B_final": int(B["final"][off]) if B is not None else None,
            "B_first_f": first_b,
            "E_val0": int(E["val0"][off]) if E is not None else None,
            "E_final": int(E["final"][off]) if E is not None else None,
            "E_first_f": first_e,
            "D_final": int(D_final[off]) if D_final is not None else None,
            "u32_A": a_u32, "u32_B_v0": b_v0, "u32_B_f": b_f,
            "u32_E_v0": e_v0, "u32_E_f": e_f, "u32_D_f": d_f,
            "small_u32_shape": small_shape,
            "page": off >> 12,
            "near_known": near[1], "near_dist": near[0],
            "in_overlay": in_overlay, "score": score,
        })

    out.sort(key=lambda r: (-r["score"], r["off"]))
    with open(os.path.join(SCRATCH, "candidates8.csv"), "w", newline="") \
            as fh:
        wr = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        wr.writeheader()
        wr.writerows(out)

    # ---- 4KB page aggregation ----
    pages = {}
    for r in out:
        p = pages.setdefault(r["page"], {"n": 0, "top_score": 0})
        p["n"] += 1
        p["top_score"] = max(p["top_score"], r["score"])
    pages_sorted = sorted(pages.items(), key=lambda kv: (-kv[1]["n"],
                                                         kv[0]))
    with open(os.path.join(SCRATCH, "pages8.json"), "w") as fh:
        json.dump({"pages": [{"page": f"0x{p:05X}000", "addr": p << 12,
                              **v} for p, v in pages_sorted[:64]],
                   "total_candidate_bytes": len(out),
                   "meta": report_meta}, fh, indent=1)

    top = out[:args.top]
    with open(os.path.join(SCRATCH, "candidates8_top.json"), "w") as fh:
        json.dump({"m2_path_windows": m2_path,
                   "agree_bytes": int(agree_idx.size),
                   "top": top}, fh, indent=1)
    print(f"\ntop {min(args.top, len(out))} of {len(out)} "
          f"(agree={agree_idx.size}):")
    for r in top[:24]:
        print(f"  {r['addr']} score={r['score']} "
              f"A={r['A_final']} B {r['B_val0']}->{r['B_final']}@f"
              f"{r['B_first_f']} "
              + (f"E {r['E_val0']}->{r['E_final']}@f{r['E_first_f']} "
                 if E is not None else "")
              + f"D={r['D_final']} u32[{r['u32_B_v0']}->"
                f"{r['u32_B_f']}|E {r['u32_E_v0']}->{r['u32_E_f']}] "
                f"near={r['near_known']}+{r['near_dist']} "
                f"ovl={r['in_overlay']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
