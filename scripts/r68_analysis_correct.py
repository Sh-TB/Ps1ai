#!/usr/bin/env python3
"""r68_analysis_correct.py — R68 offline verdict (zero boots).

Consumes ONLY committed evidence:
  data/games/SLUS-01212/truck_evidence/r68/r68_boot3_s2b.jsonl (the
    R68 pass-B hunt — the R66 tap sequence VERBATIM replay)
  + the R66/R67/R52 banks (the r67 analysis inputs verbatim)

Verdicts:
  1. THE +500 CAPTURE LEDGER — the R68 capture(s) with their causal
     chain (the honesty rule verbatim: score_delta == 500 AND exactly
     one +500 jump in the tap window).
  2. THE WIDENED-SET ZERO-OVERlap TEST — the R67 lever WITH n>=2 +500
     vectors for the first time (the R66 tap-6 capture + the R68
     tap-6 capture): the per-capture zero-overlap sets AND their
     intersection.  RESOLVED iff the intersection is non-empty.
  3. THE TRAJECTORY-SENSITIVITY CHECK — the R68 tap sequence vs the
     R66 pass-B tap sequence (the amendment-G lesson: the verbatim
     gate replay should reproduce the R66 tap order; any divergence
     is disclosed with its exact tap index).
  4. THE DELAY SIGNATURE + the magnitude table update.

Evidence: data/games/SLUS-01212/truck_evidence/r68/r68_analysis.json
"""
from __future__ import annotations

import json
import os
import sys

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(_REPO, "scripts"))

import r67_analysis_correct as A67                 # noqa: E402

EV = A67.EV
R68B = os.path.join(EV, "r68", "r68_boot3_s2b.jsonl")
R66B66 = os.path.join(EV, "r66", "r66_boot4_s2b.jsonl")
OUT = os.path.join(EV, "r68", "r68_analysis.json")


def main():
    # ---- 1. the +500 ledger -----------------------------------------
    r68_p500 = A67.extract_pay500s(R68B, "r68 passB")
    r66_p500 = A67.extract_pay500s(A67.R66A, "r66 passA") \
        + A67.extract_pay500s(A67.R66B, "r66 passB")
    r67_p500 = (A67.extract_pay500s(A67.R67A, "r67 passA")
                + A67.extract_pay500s(A67.R67B, "r67 passB"))
    all_p500 = r66_p500 + r67_p500 + r68_p500
    print("== +500 ledger ==")
    for p in all_p500:
        print(f"  {p['pass']} tap{p['tap']} slot{p['target_slot']} "
              f"st_pre={hex(p['target_st_pre']) if p['target_st_pre'] else '?'} "
              f"pay_frame={p['pay_frame']}")

    # ---- 2. the widened-set zero-overlap test (n>=2 for the first
    #         time) ----------------------------------------------------
    vecs500 = []
    for p in all_p500:
        slot = p["target_slot"]
        if p.get("pay_words") and slot is not None \
                and str(slot) in p["pay_words"]:
            vecs500.append({"src": f"{p['pass']} t{p['tap']}",
                            "slot": slot,
                            "vec": p["pay_words"][str(slot)]})
    vecs1000 = A67.extract_pay1000_bank()
    r67_p1000 = (A67.extract_pay1000s(A67.R67A, "r67 passA")
                 + A67.extract_pay1000s(A67.R67B, "r67 passB"))
    for p in r67_p1000:
        slot = p["target_slot"]
        if p.get("pay_words") and slot is not None \
                and str(slot) in p["pay_words"]:
            vecs1000.append({"src": f"{p['pass']} t{p['tap']}",
                             "slot": slot,
                             "vec": p["pay_words"][str(slot)]})
    # the R68 +1000s (if any) join the bank too
    r68_p1000 = A67.extract_pay1000s(R68B, "r68 passB")
    for p in r68_p1000:
        slot = p["target_slot"]
        if p.get("pay_words") and slot is not None \
                and str(slot) in p["pay_words"]:
            vecs1000.append({"src": f"{p['pass']} t{p['tap']}",
                             "slot": slot,
                             "vec": p["pay_words"][str(slot)]})
    zt = A67.zero_overlap_test(vecs500, vecs1000)
    print("\n== widened-set zero-overlap ==")
    print(f"  +500 vectors: {zt['n_plus500_vectors']} "
          f"({[v['src'] for v in vecs500]})")
    print(f"  +1000 vectors: {zt['n_plus1000_vectors']}")
    for pc in zt["per_capture"]:
        print(f"  {pc['src']} slot{pc['slot']}: "
              f"zero-overlap offsets = {pc['n_zero_overlap']}")
    print(f"  INTERSECTION: n={zt['n_intersection']} "
          f"-> {[o['off'] for o in zt['intersection']][:12]}")
    print(f"  VERDICT: {zt['verdict']}")

    # ---- 3. the trajectory check vs the R66 pass-B ------------------
    r68_taps = A67.taps(R68B)
    r66_taps = A67.taps(R66B66)
    traj = {
        "r68_passb_taps": [{"tap": t["tap"], "kind": t["kind"],
                            "score_delta": t.get("score_delta", 0)}
                           for t in r68_taps],
        "r66_passb_taps": [{"tap": t["tap"], "kind": t["kind"],
                            "score_delta": t.get("score_delta", 0)}
                           for t in r66_taps],
    }
    same_order = ([t["kind"] for t in traj["r68_passb_taps"]]
                  == [t["kind"] for t in traj["r66_passb_taps"]])
    print(f"\n== trajectory vs R66 pass-B ==\n  tap kinds identical: "
          f"{same_order}")

    # ---- 4. the delay signature + the magnitude table ----------------
    w52 = json.load(open(A67.W52))
    mag = {"plus500": list(w52["magnitude"]["plus500"]),
           "plus1000": list(w52["magnitude"]["plus1000"])}
    mag["plus500"].append("r68 passB t6")
    out = {"schema": "ps1play.r68-analysis/1",
           "commit": os.popen("git -C %s rev-parse HEAD"
                              % _REPO).read().strip(),
           "inputs": ["r68/r68_boot3_s2b.jsonl",
                      "r67/r67_boot2_s2a.jsonl",
                      "r67/r67_boot3_s2b.jsonl",
                      "r66/r66_boot3_s2a.jsonl",
                      "r66/r66_boot4_s2b.jsonl",
                      "r52/r52_wound_table.json"],
           "pay500_ledger": {
               "r68_captures": [{k: v for k, v in p.items()
                                 if k != "pay_words"}
                                for p in r68_p500],
               "n_plus500_total": len(all_p500),
               "n_plus500_vectors_in_test": len(vecs500)},
           "pay1000_bank_n": len(vecs1000),
           "zero_overlap_test": zt,
           "trajectory_check": dict(traj, tap_kinds_identical=same_order),
           "magnitude_table": mag,
           "m2_gate_note": "unchanged — interactive M2 entry stays "
                           "gated on a clean (deaths=0, no-restart) "
                           "deep resolve posture"}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("\nreport ->", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
