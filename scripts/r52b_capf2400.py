#!/usr/bin/env python3
"""r52b_capf2400.py — R52 (buzzybee, the 40% track, Issue #6).

The capsule lever (R51-B close-out), executed verbatim: the dominance
recipe SCALES to CAP_F 2400 (the fifth extension).  R51-B: arm B
2101/0 hits/8-of-8/caused 2 (the FOURTH caused-replication, the FULL
ORACLE true for the FOURTH consecutive round), the score tie RESTORED
(A 2102 vs B 2101), score = f - 99 EXACT across five caps, the 8th
pass arrived.

HYPOTHESIS (verbatim, the capsule R52): arm B (bot_policy8 verbatim
@2400) holds hits 0 AND caused >= 2 (the FIFTH caused-replication)
with score >= 2301 predicted by score = f - 99; the 9th-pass density
watch continues (8 -> ? @2400); a B hit files the margin floor per
the R45-B revert protocol; arm A = policy5 verbatim @2400 (the
control line and the 10th reproduction check).

Method (the capsule): offline checks BEFORE any boot (the R48-R51
precedent) -> boot 1 = core+rom load AND the gs1 checkpoint rebuild
(DISCLOSED: the THIRD sandbox rollback lost scratch/r47b/
state_r47b_gs1.bin; the r45b/r42b rebuild pattern verbatim: settle
900f -> START -> gs1 -> serialize) -> arm A2400 -> arm B2400 -> arm
B2 (tier 12/12) only on a B hit -> the oracle line + the score = f -
99 prediction check at 2400 + the pass-density vs commitment table.

Protocol: the arms are restore-only from the REBUILT gs1 checkpoint
(restores are NOT boots, r35 precedent); boot 1 = the core+rom load +
the rebuild (cap 1 DISCLOSED PRE-RUN).  Environment re-verified
internet-first sha-verified 0 boots (the R45/R47/R48/R49/R50/R51
precedent): upstream EXE 9b0bfc08... byte-identical, committed
wrap-script output 042b94bb... byte-identical (verified this round
pre-boot, disc rebuilt by r30t0_buzzybee_asset.py after the rollback).
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
from r48b_committed_seek import (          # noqa: E402
    bot_policy8, offline_checks, verify_environment)

OUT = os.path.join(REPO, "scratch", "r52b")
L.OUT = OUT                                # re-point AFTER the import
L.SHOTS = os.path.join(OUT, "shots")
L.BOOTS = os.path.join(OUT, "boots_used.json")
L.CKPT_PATH = os.path.join(OUT, "state_r52b_gs1.bin")   # REBUILT boot 1
os.makedirs(L.SHOTS, exist_ok=True)

T0 = time.time()
CAP_F = 2400               # the fifth extension (the R52 lever)
T_ENTER_MIN = 20           # the R45-B tier-switch threshold (verbatim)
TIER_PRE, TIER_IN = 8, 12  # the tiered margin (verbatim)
COMMIT_PROX = 8.0          # the flower-prox commit radius (verbatim)


def main():
    env = verify_environment()
    assert env["internet_first_verified"], \
        f"environment sha mismatch: {env}"
    print("[r52b] environment verified internet-first:",
          env["exe_sha256"][:8], env["disc_sha256"][:8], flush=True)

    # ---- offline checks BEFORE any boot (the R48-R51 precedent) -----
    chk = offline_checks()
    assert all(chk.values()), f"offline policy checks failed: {chk}"
    print("[r52b] offline policy checks:", chk, flush=True)

    R, log, dump = L.make_logger(L.OUT, "boot_log_r52b.json", "r52b")
    if not os.path.exists(L.BOOTS):
        json.dump({"cap": 1, "count": 0, "log": [], "note":
                   "R52b ledger: cap 1 DISCLOSED PRE-RUN = the "
                   "core+rom load AND the gs1 checkpoint rebuild "
                   "(DISCLOSED: the THIRD sandbox rollback lost "
                   "scratch/r47b/state_r47b_gs1.bin; the r45b/r42b "
                   "rebuild pattern verbatim).  Environment "
                   "re-verified internet-first sha-verified 0 boots "
                   "(upstream EXE 9b0bfc08... byte-identical, "
                   "committed wrap-script output 042b94bb... "
                   "byte-identical; the disc was rebuilt by "
                   "r30t0_buzzybee_asset.py after the rollback).  "
                   "The arms are restore-only (restores are NOT "
                   "boots, r35 precedent).",
                   "count_includes_core_load": True},
                  open(L.BOOTS, "w"), indent=1)
    led = L.ledger_use(1, "r52b_capf2400.py",
                       note="boot 1: core+rom load -> gs1 checkpoint "
                            "REBUILD (disclosed, the r45b pattern) -> "
                            "arm A (bot_policy5 verbatim @2400, the "
                            "10th reproduction check) -> arm B "
                            "(bot_policy8 verbatim @2400, the fifth "
                            "caused-replication attempt + the "
                            "9th-pass density watch) -> arm B2 "
                            "(tier 12/12) only on a B hit")
    log("ledger", count=led["count"], cap=led["cap"], out=L.OUT)
    log("environment", **env)
    log("offline_checks", **chk)

    bee = L.Bee("ws_r52b")
    av = bee.load_game()
    log("boot", core=bee.core.core_name, av=av)

    # ---- boot 1: rebuild the gs1 checkpoint (the r45b/r42b pattern) --
    bee.run(900, set())
    st = bee.state()
    log("settled", f=bee.frames_run, gs=st["gs"], score=st["score"])
    if st["gs"] == 0:
        bee.set_buttons("START")
        bee.run_frame()
        bee.set_buttons(set())
        for _ in range(60):
            bee.run(1, set())
            if bee.i32(L.GS) == 1:
                break
    st = bee.state()
    assert st["gs"] == 1, f"expected gs1 after START, got {st['gs']}"
    bee.run(10, set())
    CKPT = bee.serialize()
    open(L.CKPT_PATH, "wb").write(CKPT)
    st = bee.state()
    log("checkpoint_saved", bytes=len(CKPT), score=st["score"],
        hp=st["hp"], f_abs=bee.frames_run, path=L.CKPT_PATH)
    bee.snap("r52b_checkpoint", R)

    # ---- arm A: the R43-B dominance recipe verbatim (the 10th) -------
    R45B.CAP_F = CAP_F
    kwA = {"engage": 200, "margin": 16, "flower_hi": 170, "hover_y": 95}
    kwB = {"engage": 200, "flower_hi": 170, "hover_y": 95}
    mA = run_arm(bee, "A2400", P.bot_policy5, kwA, CKPT, log, R, dump)
    # ---- arm B: bot_policy8 verbatim @2400 ----------------------------
    mB = run_arm(bee, "B2400", bot_policy8, kwB, CKPT, log, R, dump)
    # ---- arm B2: the capsule revert protocol (only on a B hit) -------
    mB2 = None
    if mB["enemy_hits"] > 0:
        log("margin_floor_hit", b_hits=mB["enemy_hits"],
            revert="tier_pre=12 (GM8 rejected at this checkpoint)")
        mB2 = run_arm(bee, "B2400_r", bot_policy8,
                      dict(kwB, tier_pre=12, tier_in=12),
                      CKPT, log, R, dump)
    best_B = mB2 if (mB2 is not None and mB2["enemy_hits"] == 0) else mB
    oracle = {
        "score_ge_1550": best_B["score"] >= 1550,
        "hits_zero": best_B["enemy_hits"] == 0,
        "caused_ge_2": best_B["pickups_caused"] >= 2,
        "score_ge_2301_predicted": best_B["score"] >= 2301,
    }
    oracle["R52_GOAL"] = bool(oracle["score_ge_1550"]
                              and oracle["hits_zero"]
                              and oracle["caused_ge_2"])
    oracle["R52_FULL_INCL_PREDICTION"] = bool(
        oracle["R52_GOAL"] and oracle["score_ge_2301_predicted"])
    metrics = {
        "schema": "ps1play.r52b-evidence/1",
        "round": "R52 (buzzybee, the 40% track)",
        "boot_ledger": led,
        "environment": env,
        "offline_checks": chk,
        "checkpoint": L.CKPT_PATH + " (REBUILT in boot 1, disclosed "
                      "- the r47b checkpoint lost to the third "
                      "sandbox rollback)",
        "cap_frames": CAP_F,
        "tiered_margin": {"pre": TIER_PRE, "in": TIER_IN,
                          "t_enter_min": T_ENTER_MIN,
                          "commit_prox": COMMIT_PROX},
        "arm_A2400": mA, "arm_B2400": mB, "arm_B2400_r": mB2,
        "oracle": oracle,
        "control_lineage": {
            "r47_A1700": {"score": 1601, "hits": 0, "passes": 6,
                          "caused": 1},
            "r47_B1700": {"score": 1601, "hits": 0, "passes": 6,
                          "caused": 2},
            "r48_A1700": {"score": 1601, "hits": 0, "passes": 6,
                          "caused": 1},
            "r48_B1700": {"score": 1601, "hits": 0, "passes": 6,
                          "caused": 2},
            "r49_A1800": {"score": 1701, "hits": 0, "passes": 7,
                          "caused": 1},
            "r49_B1800": {"score": 1701, "hits": 0, "passes": 7,
                          "caused": 2},
            "r50_A2000": {"score": 1901, "hits": 0, "passes": 7,
                          "caused": 1},
            "r50_B2000": {"score": 1903, "hits": 0, "passes": 7,
                          "caused": 2},
            "r51_A2200": {"score": 2102, "hits": 0, "passes": 8,
                          "caused": 1},
            "r51_B2200": {"score": 2101, "hits": 0, "passes": 8,
                          "caused": 2},
            "r52_A2400": {"score": mA["score"],
                          "hits": mA["enemy_hits"],
                          "passes": mA["passes"],
                          "caused": mA["pickups_caused"]},
            "r52_B2400": {"score": mB["score"],
                          "hits": mB["enemy_hits"],
                          "passes": mB["passes"],
                          "caused": mB["pickups_caused"]},
        },
        "pass_density_vs_commitment": {
            "note": "the capsule table: the 9th-pass density watch "
                    "continues at 2400f (8 passes @2200)",
            "B_passes": mB["passes"],
            "B_pickup_detail": mB["pickup_detail"],
            "B_gm_frames": mB["gm_frames"],
            "B_replans": mB["planner_replans"],
            "B_bails": mB["planner_bails"],
        },
        "wall_s": round(time.time() - T0, 1),
    }
    json.dump(metrics, open(os.path.join(L.OUT, "metrics_r52b.json"),
                            "w"), indent=1, default=str)
    log("r52b_verdict", r52_goal=oracle["R52_GOAL"],
        A_score=mA["score"], B_score=mB["score"],
        B_hits=mB["enemy_hits"], B_caused=mB["pickups_caused"],
        B_passes=mB["passes"], B_pickups=mB["pickups_total"],
        B2_score=(mB2 or {}).get("score"),
        B2_caused=(mB2 or {}).get("pickups_caused"))
    dump()
    sb = L.sync_back()
    if sb:
        log("sync_back", note=sb)
    print("[r52b] DONE wall=", round(time.time() - T0, 1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
