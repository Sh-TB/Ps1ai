#!/usr/bin/env python3
"""r50b_capf2000.py — R50 (buzzybee, the 40% track, Issue #6).

The capsule lever (R49 close-out), executed verbatim: the dominance
recipe SCALES to CAP_F 2000 (the third extension).  R49 replicated
the FULL ORACLE (score >= 1550 AND hits 0 AND caused >= 2) at 1800f
(arm B bot_policy8 1701/0/7/caused 2; arm A = the 7th policy5
reproduction, exactly the R47 A1800 line).

HYPOTHESIS (verbatim, the capsule R50): arm B (bot_policy8 verbatim
@2000) holds hits 0 AND caused >= 2 (the THIRD caused-replication)
with score >= 1901 predicted by score = f - 99; the REAL RISK is
late-game wasp density vs the guarantee planner (the pass count
grows 7 -> ~8-9; a hit at GM8 files the margin floor per the R45-B
revert protocol); arm A = policy5 verbatim @2000 (the control line
and the 8th reproduction check).

Method (the capsule): offline checks BEFORE any boot (the R48/R49
precedent) -> boot 1 core+rom load -> restore the r47b gs1
checkpoint -> arm A2000 -> arm B2000 -> arm B2 (tier 12/12) only on
a B hit -> the oracle line evaluated on B + the score = f - 99
prediction check at 2000 + the pass-density vs commitment table
(the 8th/9th passes).

Protocol: restore-only arms from the r47b gs1 checkpoint (READ-ONLY,
survived on disk — verified pre-boot); boot 1 = the core+rom load
ONLY (cap 1 DISCLOSED PRE-RUN); restores are NOT boots (r35
precedent).  Environment re-verified internet-first sha-verified
0 boots (the R47/R48/R49 precedent).
"""
from __future__ import annotations

import json
import os
import sys
import time

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(REPO, "scripts"))

import r35b_lib as L                       # noqa: E402
import r43b_planner as P                   # noqa: E402
import r45b_preposition_margin as R45B     # noqa: E402
from r45b_preposition_margin import run_arm  # noqa: E402
import r48b_committed_seek as R48B         # noqa: E402
from r48b_committed_seek import (          # noqa: E402
    bot_policy8, offline_checks, verify_environment)

OUT = os.path.join(REPO, "scratch", "r50b")
L.OUT = OUT                                # re-point AFTER the import
L.SHOTS = os.path.join(OUT, "shots")
L.BOOTS = os.path.join(OUT, "boots_used.json")
L.CKPT_PATH = os.path.join(REPO, "scratch", "r47b",
                           "state_r47b_gs1.bin")   # READ-ONLY restore
os.makedirs(L.SHOTS, exist_ok=True)

T0 = time.time()
CAP_F = 2000               # the third extension (the R50 lever)
T_ENTER_MIN = 20           # the R45-B tier-switch threshold (verbatim)
TIER_PRE, TIER_IN = 8, 12  # the tiered margin (verbatim)
COMMIT_PROX = 8.0          # the flower-prox commit radius (verbatim)


def main():
    env = verify_environment()
    assert env["internet_first_verified"], \
        f"environment sha mismatch: {env}"
    print("[r50b] environment verified internet-first:",
          env["exe_sha256"][:8], env["disc_sha256"][:8], flush=True)

    # ---- offline checks BEFORE any boot (the R48/R49 precedent) -----
    chk = offline_checks()
    assert all(chk.values()), f"offline policy checks failed: {chk}"
    print("[r50b] offline policy checks:", chk, flush=True)

    if not os.path.exists(L.CKPT_PATH):
        raise SystemExit("r47b gs1 checkpoint MISSING - the capsule "
                         "contingency (an in-process rebuild) would "
                         "need a fresh disclosed cap; never fabricate")
    R, log, dump = L.make_logger(L.OUT, "boot_log_r50b.json", "r50b")
    if not os.path.exists(L.BOOTS):
        json.dump({"cap": 1, "count": 0, "log": [], "note":
                   "R50b ledger: cap 1 DISCLOSED PRE-RUN = the "
                   "core+rom load ONLY (NO sandbox rollback: the r47b "
                   "gs1 checkpoint SURVIVED on disk, verified "
                   "pre-boot, READ-ONLY use).  Environment re-verified "
                   "internet-first sha-verified 0 boots (upstream EXE "
                   "9b0bfc08... byte-identical, committed wrap-script "
                   "output 042b94bb... byte-identical).  The arms are "
                   "restore-only (restores are NOT boots, r35 "
                   "precedent).",
                   "count_includes_core_load": True},
                  open(L.BOOTS, "w"), indent=1)
    led = L.ledger_use(1, "r50b_capf2000.py",
                       note="boot 1: core+rom load -> restore the "
                            "r47b gs1 checkpoint -> arm A "
                            "(bot_policy5 verbatim @2000, the 8th "
                            "reproduction check) -> arm B "
                            "(bot_policy8 verbatim @2000, the third "
                            "caused-replication attempt) -> arm B2 "
                            "(tier 12/12) only on a B hit")
    log("ledger", count=led["count"], cap=led["cap"], out=L.OUT)
    log("environment", **env)
    log("offline_checks", **chk)
    CKPT = open(L.CKPT_PATH, "rb").read()
    log("checkpoint_loaded", path=L.CKPT_PATH, bytes=len(CKPT))
    bee = L.Bee("ws_r50b")
    av = bee.load_game()
    log("boot", core=bee.core.core_name, av=av)

    R45B.CAP_F = CAP_F
    kwA = {"engage": 200, "margin": 16, "flower_hi": 170, "hover_y": 95}
    kwB = {"engage": 200, "flower_hi": 170, "hover_y": 95}
    mA = run_arm(bee, "A2000", P.bot_policy5, kwA, CKPT, log, R, dump)
    mB = run_arm(bee, "B2000", bot_policy8, kwB, CKPT, log, R, dump)
    mB2 = None
    if mB["enemy_hits"] > 0:
        log("margin_floor_hit", b_hits=mB["enemy_hits"],
            revert="tier_pre=12 (GM8 rejected at this checkpoint)")
        mB2 = run_arm(bee, "B2000_r", bot_policy8,
                      dict(kwB, tier_pre=12, tier_in=12),
                      CKPT, log, R, dump)
    best_B = mB2 if (mB2 is not None and mB2["enemy_hits"] == 0) else mB
    oracle = {
        "score_ge_1550": best_B["score"] >= 1550,
        "hits_zero": best_B["enemy_hits"] == 0,
        "caused_ge_2": best_B["pickups_caused"] >= 2,
        "score_ge_1901_predicted": best_B["score"] >= 1901,
    }
    oracle["R50_GOAL"] = bool(oracle["score_ge_1550"]
                              and oracle["hits_zero"]
                              and oracle["caused_ge_2"])
    oracle["R50_FULL_INCL_PREDICTION"] = bool(
        oracle["R50_GOAL"] and oracle["score_ge_1901_predicted"])
    metrics = {
        "schema": "ps1play.r50b-evidence/1",
        "round": "R50 (buzzybee, the 40% track)",
        "boot_ledger": led,
        "environment": env,
        "offline_checks": chk,
        "checkpoint": L.CKPT_PATH + " (READ-ONLY restore, survived)",
        "cap_frames": CAP_F,
        "tiered_margin": {"pre": TIER_PRE, "in": TIER_IN,
                          "t_enter_min": T_ENTER_MIN,
                          "commit_prox": COMMIT_PROX},
        "arm_A2000": mA, "arm_B2000": mB, "arm_B2000_r": mB2,
        "oracle": oracle,
        "control_lineage": {
            "r47_A1700": {"score": 1601, "hits": 0, "passes": 6,
                          "caused": 1},
            "r47_A1800": {"score": 1701, "hits": 0, "passes": 7,
                          "caused": 1},
            "r48_A1700": {"score": 1601, "hits": 0, "passes": 6,
                          "caused": 1},
            "r48_B1700": {"score": 1601, "hits": 0, "passes": 6,
                          "caused": 2},
            "r49_A1800": {"score": 1701, "hits": 0, "passes": 7,
                          "caused": 1},
            "r49_B1800": {"score": 1701, "hits": 0, "passes": 7,
                          "caused": 2},
            "r50_A2000": {"score": mA["score"],
                          "hits": mA["enemy_hits"],
                          "passes": mA["passes"],
                          "caused": mA["pickups_caused"]},
            "r50_B2000": {"score": mB["score"],
                          "hits": mB["enemy_hits"],
                          "passes": mB["passes"],
                          "caused": mB["pickups_caused"]},
        },
        "pass_density_vs_commitment": {
            "note": "the capsule table: the wasp-density risk (the "
                    "8th/9th passes) vs the guarantee planner",
            "B_passes": mB["passes"],
            "B_pickup_detail": mB["pickup_detail"],
            "B_gm_frames": mB["gm_frames"],
            "B_replans": mB["planner_replans"],
            "B_bails": mB["planner_bails"],
        },
        "wall_s": round(time.time() - T0, 1),
    }
    json.dump(metrics, open(os.path.join(L.OUT, "metrics_r50b.json"),
                            "w"), indent=1, default=str)
    log("r50b_verdict", r50_goal=oracle["R50_GOAL"],
        A_score=mA["score"], B_score=mB["score"],
        B_hits=mB["enemy_hits"], B_caused=mB["pickups_caused"],
        B_passes=mB["passes"], B_pickups=mB["pickups_total"],
        B2_score=(mB2 or {}).get("score"),
        B2_caused=(mB2 or {}).get("pickups_caused"))
    dump()
    sb = L.sync_back()
    if sb:
        log("sync_back", note=sb)
    print("[r50b] DONE wall=", round(time.time() - T0, 1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
