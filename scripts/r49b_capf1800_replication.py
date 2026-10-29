#!/usr/bin/env python3
"""r49b_capf1800_replication.py — R49 (buzzybee, the 40% track, #6).

The capsule lever (R48 close-out), executed verbatim.  R48 took the
FIRST FULL ORACLE PASS: arm B (bot_policy8, the committed seek) 1601/
0 hits/6-of-6/caused 2 at CAP_F 1700 — score >= 1550 AND hits 0 AND
caused >= 2 all TRUE for the first time in seven rounds; the
mechanism confirmed BY NAME (commitment was the caused bottleneck:
the decisive pickup seek_dur 134 in flower mode).

HYPOTHESIS (verbatim, the capsule R49): the caused >= 2 pass
REPLICATES (bot_policy8 is not a one-checkpoint fluke): the same
restore-only protocol at CAP_F 1800 (the R47 clause) reaches
caused >= 2 AGAIN with hits 0 and score >= 1701 predicted by
score = f - 99; the pass-density vs commitment table decides whether
the commitment mechanism scales with wasp density (the 8th/9th wasp
passes).

Method (the capsule): arm A = bot_policy5 verbatim @1800 (the
control line, protocol parity); arm B = bot_policy8 @1800 (the
committed seek verbatim); the oracle line (score >= 1550 AND hits 0
AND caused >= 2) evaluated on B; if B takes a hit the margin floor
files (the R45-B revert protocol: tier 12/12); offline checks BEFORE
any boot (the R48 precedent).

Protocol: restore-only arms from the r47b gs1 checkpoint (READ-ONLY,
survived on disk — verified pre-boot); boot 1 = the core+rom load
ONLY (cap 1 DISCLOSED PRE-RUN); restores are NOT boots (r35
precedent).  Environment re-verified internet-first sha-verified
0 boots (the R47/R48 precedent).

Oracle line (the capsule): score >= 1550 AND hits 0 AND caused >= 2;
plus the R49 prediction check score >= 1701 at 1800f (score = f-99)
and the pass-density table (6 passes @1500f -> 7 @1700f -> ? @1800f).
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

OUT = os.path.join(REPO, "scratch", "r49b")
L.OUT = OUT                                # re-point AFTER the import
L.SHOTS = os.path.join(OUT, "shots")
L.BOOTS = os.path.join(OUT, "boots_used.json")
L.CKPT_PATH = os.path.join(REPO, "scratch", "r47b",
                           "state_r47b_gs1.bin")   # READ-ONLY restore
os.makedirs(L.SHOTS, exist_ok=True)

T0 = time.time()
CAP_F = 1800               # the R47 clause (the replication horizon)
T_ENTER_MIN = 20           # the R45-B tier-switch threshold (verbatim)
TIER_PRE, TIER_IN = 8, 12  # the tiered margin (verbatim)
COMMIT_PROX = 8.0          # the flower-prox commit radius (verbatim)


def main():
    env = verify_environment()
    assert env["internet_first_verified"], \
        f"environment sha mismatch: {env}"
    print("[r49b] environment verified internet-first:",
          env["exe_sha256"][:8], env["disc_sha256"][:8], flush=True)

    # ---- offline checks BEFORE any boot (the R48 precedent) ---------
    chk = offline_checks()
    assert all(chk.values()), f"offline policy checks failed: {chk}"
    print("[r49b] offline policy checks:", chk, flush=True)

    if not os.path.exists(L.CKPT_PATH):
        raise SystemExit("r47b gs1 checkpoint MISSING - the capsule "
                         "contingency (an in-process rebuild) would "
                         "need a fresh disclosed cap; never fabricate")
    log = None
    R, log, dump = L.make_logger(L.OUT, "boot_log_r49b.json", "r49b")
    if not os.path.exists(L.BOOTS):
        json.dump({"cap": 1, "count": 0, "log": [], "note":
                   "R49b ledger: cap 1 DISCLOSED PRE-RUN = the "
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
    led = L.ledger_use(1, "r49b_capf1800_replication.py",
                       note="boot 1: core+rom load -> restore the "
                            "r47b gs1 checkpoint -> arm A "
                            "(bot_policy5 verbatim @1800, the R47 "
                            "control line) -> arm B (bot_policy8 "
                            "verbatim @1800) -> arm B2 (tier 12/12) "
                            "only on a B hit")
    log("ledger", count=led["count"], cap=led["cap"], out=L.OUT)
    log("environment", **env)
    log("offline_checks", **chk)
    CKPT = open(L.CKPT_PATH, "rb").read()
    log("checkpoint_loaded", path=L.CKPT_PATH, bytes=len(CKPT))
    bee = L.Bee("ws_r49b")
    av = bee.load_game()
    log("boot", core=bee.core.core_name, av=av)

    R45B.CAP_F = CAP_F
    kwA = {"engage": 200, "margin": 16, "flower_hi": 170, "hover_y": 95}
    kwB = {"engage": 200, "flower_hi": 170, "hover_y": 95}
    mA = run_arm(bee, "A1800", P.bot_policy5, kwA, CKPT, log, R, dump)
    mB = run_arm(bee, "B1800", bot_policy8, kwB, CKPT, log, R, dump)
    mB2 = None
    if mB["enemy_hits"] > 0:
        log("margin_floor_hit", b_hits=mB["enemy_hits"],
            revert="tier_pre=12 (GM8 rejected at this checkpoint)")
        mB2 = run_arm(bee, "B1800_r", bot_policy8,
                      dict(kwB, tier_pre=12, tier_in=12),
                      CKPT, log, R, dump)
    best_B = mB2 if (mB2 is not None and mB2["enemy_hits"] == 0) else mB
    oracle = {
        "score_ge_1550": best_B["score"] >= 1550,
        "hits_zero": best_B["enemy_hits"] == 0,
        "caused_ge_2": best_B["pickups_caused"] >= 2,
        "score_ge_1701_predicted": best_B["score"] >= 1701,
    }
    oracle["R49_GOAL"] = bool(oracle["score_ge_1550"]
                              and oracle["hits_zero"]
                              and oracle["caused_ge_2"])
    oracle["R49_FULL_INCL_PREDICTION"] = bool(
        oracle["R49_GOAL"] and oracle["score_ge_1701_predicted"])
    metrics = {
        "schema": "ps1play.r49b-evidence/1",
        "round": "R49 (buzzybee, the 40% track)",
        "boot_ledger": led,
        "environment": env,
        "offline_checks": chk,
        "checkpoint": L.CKPT_PATH + " (READ-ONLY restore, survived)",
        "cap_frames": CAP_F,
        "tiered_margin": {"pre": TIER_PRE, "in": TIER_IN,
                          "t_enter_min": T_ENTER_MIN,
                          "commit_prox": COMMIT_PROX},
        "arm_A1800": mA, "arm_B1800": mB, "arm_B1800_r": mB2,
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
            "r49_A1800": {"score": mA["score"],
                          "hits": mA["enemy_hits"],
                          "passes": mA["passes"],
                          "caused": mA["pickups_caused"]},
            "r49_B1800": {"score": mB["score"],
                          "hits": mB["enemy_hits"],
                          "passes": mB["passes"],
                          "caused": mB["pickups_caused"]},
        },
        "pass_density_vs_commitment": {
            "note": "the capsule table: does the commitment mechanism "
                    "scale with wasp density (the 8th/9th passes)?",
            "B_passes": mB["passes"],
            "B_pickup_detail": mB["pickup_detail"],
            "B_gm_frames": mB["gm_frames"],
            "B_replans": mB["planner_replans"],
            "B_bails": mB["planner_bails"],
        },
        "wall_s": round(time.time() - T0, 1),
    }
    json.dump(metrics, open(os.path.join(L.OUT, "metrics_r49b.json"),
                            "w"), indent=1, default=str)
    log("r49b_verdict", r49_goal=oracle["R49_GOAL"],
        A_score=mA["score"], B_score=mB["score"],
        B_hits=mB["enemy_hits"], B_caused=mB["pickups_caused"],
        B_passes=mB["passes"], B_pickups=mB["pickups_total"],
        B2_score=(mB2 or {}).get("score"),
        B2_caused=(mB2 or {}).get("pickups_caused"))
    dump()
    sb = L.sync_back()
    if sb:
        log("sync_back", note=sb)
    print("[r49b] DONE wall=", round(time.time() - T0, 1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
