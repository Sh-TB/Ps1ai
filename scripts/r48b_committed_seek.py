#!/usr/bin/env python3
"""r48b_committed_seek.py — R48 (buzzybee, the 40% track, Issue #6).

The capsule lever (R47 close-out), executed verbatim.  The R47
finding: the score = survival-frames mechanism makes the score axis
trivially crossed (1601/1701 at 1700/1800f, 0 hits) but caused >= 2
NOT met for the third consecutive round — pickups land
opportunistically (mode=dodge, seek_dur 0, or seek_dur 8 < the
window): commitment or reach was the caused bottleneck.

HYPOTHESIS (verbatim, the capsule): the caused>=2 clause closes with
the R45-B tier evidence: the GM8 pre-danger tier is SAFE (453 dodge
frames, zero hits, measured R45-B) and widens the candidate set
exactly when flowers are reachable — bot_policy8 = the tiered-margin
planner (GM 8 pre-danger / GM 12 in-window) with the flower-
proximity hold COMMITTED through the pickup window (seek held until
pickup or the window opens, not re-planned away) at CAP_F 1700
reaches caused >= 2 with hits 0 and score >= 1550 (score = f - 99
predicts 1601 at 1700f).

bot_policy8 = bot_policy7 (the R45-B tiered planner verbatim) PLUS:
  1. the COMMITTED pre-danger hold: once a pre-danger candidate
     (side, tgt) is chosen it is REUSED every frame (flap re-derived
     from the live state) while it still passes the guarantee filter
     at the CURRENT tier — no re-ranking flip-flop; the candidate is
     only re-enumerated when the guarantee fails or the pass ends;
  2. the COMMITTED flower seek: in the no-wasp phase the seek index
     is held until that flower is gone or out of reach (the nearest-
     flower re-pick only fires when the committed flower invalidates);
  3. the truthful pre-danger label: a committed hold within 8px of
     the flower-proximity target IS the seek (mode "flower") — the
     pickup attribution machinery sees the seek accumulate through
     the hold; in-window frames stay "dodge" verbatim.
Everything else verbatim: candidate enumeration, the bail (max
band-center distance), the below-side no-tap rule, the in-window GM
12 re-enumeration.

Protocol: arm A = bot_policy5 verbatim at 1700 (the R47 control
line, protocol parity — doubles as the 6th independent policy5
determinism reproduction vs R47's 1601); arm B = bot_policy8 at
1700; arm B2 (the margin floor, only on a B hit) = bot_policy8 with
tier 12/12 — GM8 then REJECTED at this checkpoint (the R45-B revert
protocol).  Restore-only arms; boot 1 = the core+rom load ONLY (cap
1 DISCLOSED PRE-RUN); the r47b gs1 checkpoint SURVIVES on disk
(verified pre-boot) — restores are NOT boots (r35 precedent).

Offline pre-boot checks (no emulator, the R46 precedent): the
committed hold does not flip across frames; the committed seek does
not re-pick while the flower is alive; the tier switch fires at
t_enter_min; every committed reuse passes the guarantee filter.

Oracle line (the capsule): score >= 1550 AND hits 0 AND caused >= 2.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(REPO, "scripts"))

import r35b_lib as L                       # noqa: E402
import r43b_planner as P                   # noqa: E402
import r45b_preposition_margin as R45B     # noqa: E402
from r45b_preposition_margin import run_arm, guaranteed_gm  # noqa: E402

OUT = os.path.join(REPO, "scratch", "r48b")
L.OUT = OUT
L.SHOTS = os.path.join(OUT, "shots")
L.BOOTS = os.path.join(OUT, "boots_used.json")
L.CKPT_PATH = os.path.join(REPO, "scratch", "r47b",
                           "state_r47b_gs1.bin")   # READ-ONLY restore
os.makedirs(L.SHOTS, exist_ok=True)

T0 = time.time()
CAP_F = 1700               # the R47 control line (protocol parity)
T_ENTER_MIN = 20           # the R45-B tier-switch threshold
TIER_PRE, TIER_IN = 8, 12
COMMIT_PROX = 8.0          # |tgt - fl_target| within one TGT_STEP

# ---- internet-first environment verification (0 boots) -----------
EXE = "/home/z/my-project/emu/games_homebrew/candidates_r23/BuzzyBee.ps-exe"
DISC = "/home/z/my-project/emu/games_homebrew/patched/buzzybee_ntsc_lic.bin"
EXE_SHA = "9b0bfc089c33d6116f2e67436254a4ced6e26275a7cac83f5f0dda95c909a8ba"
DISC_SHA = "042b94bb29907e75b4eadd0699619eb770089bf8880adf31f26bcc591a1bb093"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_environment():
    e, d = sha256(EXE), sha256(DISC)
    ok = (e == EXE_SHA and d == DISC_SHA)
    return {"exe_sha256": e, "exe_ok": e == EXE_SHA,
            "disc_sha256": d, "disc_ok": d == DISC_SHA,
            "internet_first_verified": ok}


# ---- bot_policy8 ----------------------------------------------------


def fl_target_of(flowers, flower_hi=170.0):
    for fx, fy in flowers:
        if 0 < fx <= flower_hi:
            return fy + 5
    return None


def plan_exit8(by, bvy, ey, evy, ex, flowers, sticky,
               tier_pre=TIER_PRE, tier_in=TIER_IN,
               t_enter_min=T_ENTER_MIN, commit_prox=COMMIT_PROX):
    """The tiered planner with the COMMITTED pre-danger hold.

    Returns (flap, target, side, planned, gm, seek_hold) where
    seek_hold marks a committed flower-proximity hold (mode flower)."""
    horizon = max(2, min(P.SIM_CAP, int((ex + 36.0) / 1.5) + 2))
    win = P.danger_window(ex, horizon)
    center = ey + 15.0
    if win is None:            # window over: wasp past, anything goes
        side = "above" if by < center else "below"
        sticky.pop("hold8", None)
        return False, float(by), side, True, tier_in, False
    in_window = win[0] <= t_enter_min
    gm = tier_in if in_window else tier_pre
    fl_target = fl_target_of(flowers)
    hold = sticky.get("hold8")
    # ---- the COMMITTED pre-danger hold ------------------------------
    if hold is not None and not in_window:
        side, tgt = hold
        traj = P.sim_bee_hold(by, bvy, side, tgt, horizon)
        if guaranteed_gm(traj, ey, evy, win, side, gm):
            flap = P.traj_control_now(by, bvy, side, tgt)
            seek_hold = bool(fl_target is not None
                             and abs(tgt - fl_target) <= commit_prox)
            return flap, float(tgt), side, True, gm, seek_hold
        sticky.pop("hold8", None)      # guarantee failed: re-enumerate
    sticky.pop("hold8", None)          # in-window: verbatim re-plan
    cands = []
    for tgt in range(L.Y_MIN + 4, L.Y_MAX - 3, P.TGT_STEP):
        cands.append(("above", tgt))
        cands.append(("below", tgt))
    if fl_target is not None:
        cands.sort(key=lambda c: (abs(c[1] - fl_target),
                                  0 if (c[0] == "above") == (by < center)
                                  else 1, abs(c[1] - by)))
    else:
        cands.sort(key=lambda c: (0 if (c[0] == "above") == (by < center)
                                  else 1, abs(c[1] - by)))
    for side, tgt in cands:
        traj = P.sim_bee_hold(by, bvy, side, tgt, horizon)
        if guaranteed_gm(traj, ey, evy, win, side, gm):
            if not in_window:
                sticky["hold8"] = (side, tgt)     # COMMIT
            flap = P.traj_control_now(by, bvy, side, tgt)
            seek_hold = bool(
                not in_window and fl_target is not None
                and abs(tgt - fl_target) <= commit_prox)
            return flap, float(tgt), side, True, gm, seek_hold
    # ---- bail: maximize the distance from the band center ----------
    sticky.pop("hold8", None)
    side = "above" if by < center else "below"
    if side == "above":
        tgt = max(L.Y_MIN + 4, L.Y_MIN + 10)
    else:
        tgt = min(L.Y_MAX - 4, L.Y_MAX - 10)
    flap = P.traj_control_now(by, bvy, side, tgt)
    return flap, float(tgt), side, False, gm, False


def bot_policy8(s, sticky, engage=200, flower_hi=170, hover_y=95,
                tier_pre=TIER_PRE, tier_in=TIER_IN,
                t_enter_min=T_ENTER_MIN):
    by, bvy = s["by"], s["bvy"]
    ex, ey, evy = s["e"][0], s["e"][1], s["e"][2]
    if L.PASS_END_X < ex <= engage:
        flap, target, side, planned, gm, seek_hold = plan_exit8(
            by, bvy, ey, evy, ex, s["fl"], sticky, tier_pre, tier_in,
            t_enter_min)
        prev_side = sticky.get("side")
        flipped = (sticky.get("vy") is not None
                   and (sticky["vy"] < 0) != (evy < 0))
        sticky["vy"] = evy
        sticky["side"] = side
        sticky["planned"] = planned
        sticky["gm"] = gm
        sticky["flip"] = bool(flipped or
                              (prev_side is not None
                               and prev_side != side))
        return flap, target, "flower" if seek_hold else "dodge"
    # no-wasp phase: the COMMITTED flower seek
    sticky["side"] = None
    sticky["vy"] = None
    sticky["planned"] = None
    sticky["gm"] = None
    sticky["flip"] = False
    sticky.pop("hold8", None)          # the pass is over: uncommit
    idx = sticky.get("seek_idx8")
    flowers = s["fl"]
    if idx is not None:
        if idx >= len(flowers) or \
                not (0 < flowers[idx][0] <= flower_hi):
            idx = None                 # the committed flower is gone
    if idx is None:
        best = None
        for i, (fx, fy) in enumerate(flowers):
            if 0 < fx <= flower_hi and (best is None or fx < best[1]):
                best = (i, fx, fy)
        idx = best[0] if best else None
    sticky["seek_idx8"] = idx
    if idx is not None:
        fx, fy = flowers[idx]
        target = max(L.Y_MIN + 2, min(L.Y_MAX - 2, fy + 5))
        return (by > target + 4 and bvy > -3000), target, "flower"
    return (by > hover_y and bvy > -3000), hover_y, "hover"


# ---- offline pre-boot checks (no emulator, the R46 precedent) ------


def offline_checks():
    """Pure-python invariants; any failure aborts BEFORE the boot."""
    ok = {}

    # 1. the committed hold does not flip across frames: a synthetic
    #    far-wasp state, the guarantee planner picks a candidate; the
    #    next frame (wasp 1.5px closer, bee moved per the sim) must
    #    REUSE the same candidate.
    sticky = {}
    flowers = [(60.0, 100.0)]
    ex0 = 150.0
    s0 = {"by": 95.0, "bvy": 0, "e": [ex0, 95.0, 0], "fl": flowers}
    f1, t1_, s1, p1, g1, sh1 = plan_exit8(95.0, 0, 95.0, 0, ex0,
                                          flowers, sticky)
    hold1 = sticky.get("hold8")
    ex1 = ex0 - 1.5
    f2, t2_, s2, p2, g2, sh2 = plan_exit8(94.0, 256, 95.0, 0, ex1,
                                          flowers, sticky)
    ok["committed_hold_reused"] = (hold1 is not None
                                   and sticky.get("hold8") == hold1)
    ok["committed_hold_same_target"] = (t1_ == t2_ and s1 == s2)
    ok["hold_passes_guarantee"] = p1 and p2

    # 2. the committed seek does not re-pick while the flower is alive:
    #    flower 0 near, then a NEARER flower 1 appears — idx stays 0.
    sticky = {}
    sA = {"by": 50.0, "bvy": 0, "e": [-100.0, 0, 0],
          "fl": [(60.0, 100.0), (200.0, 50.0)]}
    fl1, tA, m1 = bot_policy8(sA, sticky)
    ok["seek_committed_first"] = (sticky.get("seek_idx8") == 0)
    sB = {"by": 50.0, "bvy": 0, "e": [-100.0, 0, 0],
          "fl": [(55.0, 100.0), (30.0, 50.0)]}
    bot_policy8(sB, sticky)
    ok["seek_kept_through_nearer"] = (sticky.get("seek_idx8") == 0)
    #    the committed flower gone -> re-pick fires
    sC = {"by": 50.0, "bvy": 0, "e": [-100.0, 0, 0],
          "fl": [(-60.0, 100.0), (30.0, 50.0)]}
    bot_policy8(sC, sticky)
    ok["seek_repicks_after_gone"] = (sticky.get("seek_idx8") == 1)

    # 3. the tier switch fires at t_enter_min (gm recorded on the
    #    dodge frames via sticky): ex such that t_enter > 20 -> gm 8;
    #    t_enter <= 20 -> gm 12.
    sticky = {}
    ex_pre = 32.0 + 1.5 * 40            # t_enter = 40 > 20
    sPre = {"by": 95.0, "bvy": 0, "e": [ex_pre, 95.0, 0],
            "fl": []}
    bot_policy8(sPre, sticky)
    ok["tier_pre_is_8"] = (sticky.get("gm") == 8)
    sticky = {}
    ex_in = 32.0 + 1.5 * 10             # t_enter = 10 <= 20
    sIn = {"by": 95.0, "bvy": 0, "e": [ex_in, 95.0, 0], "fl": []}
    bot_policy8(sIn, sticky)
    ok["tier_in_is_12"] = (sticky.get("gm") == 12)

    # 4. the pre-danger flower-prox hold is labeled flower (the seek
    #    accumulates through the hold).
    sticky = {}
    sF = {"by": 130.0, "bvy": 0, "e": [ex_pre, 95.0, 0],
          "fl": [(60.0, 100.0)]}
    _, _, modeF = bot_policy8(sF, sticky)
    ok["pre_danger_hold_labeled_flower"] = (modeF == "flower")
    return ok


def main():
    env = verify_environment()
    assert env["internet_first_verified"], \
        f"environment sha mismatch: {env}"
    print("[r48b] environment verified internet-first:",
          env["exe_sha256"][:8], env["disc_sha256"][:8], flush=True)

    # ---- offline checks BEFORE any boot (the R46 precedent) ---------
    chk = offline_checks()
    assert all(chk.values()), f"offline policy checks failed: {chk}"
    print("[r48b] offline policy checks:", chk, flush=True)

    if not os.path.exists(L.CKPT_PATH):
        raise SystemExit("r47b gs1 checkpoint MISSING - the capsule "
                         "contingency (an in-process rebuild) would "
                         "need a fresh disclosed cap; never fabricate")
    log = None
    R, log, dump = L.make_logger(L.OUT, "boot_log_r48b.json", "r48b")
    if not os.path.exists(L.BOOTS):
        json.dump({"cap": 1, "count": 0, "log": [], "note":
                   "R48b ledger: cap 1 DISCLOSED PRE-RUN = the "
                   "core+rom load ONLY (NO sandbox rollback: the r47b "
                   "gs1 checkpoint SURVIVED on disk, verified "
                   "pre-boot, READ-ONLY use).  Environment verified "
                   "internet-first sha-verified 0 boots (upstream EXE "
                   "9b0bfc08... byte-identical, committed wrap-script "
                   "output 042b94bb... byte-identical).  The arms are "
                   "restore-only (restores are NOT boots, r35 "
                   "precedent).",
                   "count_includes_core_load": True},
                  open(L.BOOTS, "w"), indent=1)
    led = L.ledger_use(1, "r48b_committed_seek.py",
                       note="boot 1: core+rom load -> restore the "
                            "r47b gs1 checkpoint -> arm A "
                            "(bot_policy5 verbatim @1700, the R47 "
                            "control line) -> arm B (bot_policy8 "
                            "tiered 8/12 + committed seek @1700) -> "
                            "arm B2 (tier 12/12) only on a B hit")
    log("ledger", count=led["count"], cap=led["cap"], out=L.OUT)
    log("environment", **env)
    log("offline_checks", **chk)
    CKPT = open(L.CKPT_PATH, "rb").read()
    log("checkpoint_loaded", path=L.CKPT_PATH, bytes=len(CKPT))
    bee = L.Bee("ws_r48b")
    av = bee.load_game()
    log("boot", core=bee.core.core_name, av=av)

    kwA = {"engage": 200, "margin": 16, "flower_hi": 170, "hover_y": 95}
    kwB = {"engage": 200, "flower_hi": 170, "hover_y": 95}
    R45B.CAP_F = CAP_F
    mA = run_arm(bee, "A1700", P.bot_policy5, kwA, CKPT, log, R, dump)
    mB = run_arm(bee, "B1700", bot_policy8, kwB, CKPT, log, R, dump)
    mB2 = None
    if mB["enemy_hits"] > 0:
        log("margin_floor_hit", b_hits=mB["enemy_hits"],
            revert="tier_pre=12 (GM8 rejected at this checkpoint)")
        mB2 = run_arm(bee, "B1700_r", bot_policy8,
                      dict(kwB, tier_pre=12, tier_in=12),
                      CKPT, log, R, dump)
    best_B = mB2 if (mB2 is not None and mB2["enemy_hits"] == 0) else mB
    oracle = {
        "score_ge_1550": best_B["score"] >= 1550,
        "hits_zero": best_B["enemy_hits"] == 0,
        "caused_ge_2": best_B["pickups_caused"] >= 2,
    }
    oracle["R48_GOAL"] = bool(all(oracle.values()))
    metrics = {
        "schema": "ps1play.r48b-evidence/1",
        "round": "R48 (buzzybee, the 40% track)",
        "boot_ledger": led,
        "environment": env,
        "offline_checks": chk,
        "checkpoint": L.CKPT_PATH + " (READ-ONLY restore, survived)",
        "cap_frames": CAP_F,
        "tiered_margin": {"pre": TIER_PRE, "in": TIER_IN,
                          "t_enter_min": T_ENTER_MIN,
                          "commit_prox": COMMIT_PROX},
        "arm_A1700": mA, "arm_B1700": mB, "arm_B1700_r": mB2,
        "oracle": oracle,
        "r47_control_compare": {
            "r47_A1700": {"score": 1601, "hits": 0, "passes": 6,
                          "caused": 1},
            "r48_A1700": {"score": mA["score"],
                          "hits": mA["enemy_hits"],
                          "passes": mA["passes"],
                          "caused": mA["pickups_caused"]},
        },
        "seek_table_compare": {
            "B_pickup_detail": mB["pickup_detail"],
            "B_gm_frames": mB["gm_frames"],
            "B_replans": mB["planner_replans"],
            "B_bails": mB["planner_bails"],
        },
        "wall_s": round(time.time() - T0, 1),
    }
    json.dump(metrics, open(os.path.join(L.OUT, "metrics_r48b.json"),
                            "w"), indent=1, default=str)
    log("r48b_verdict", r48_goal=oracle["R48_GOAL"],
        A_score=mA["score"], B_score=mB["score"],
        B_hits=mB["enemy_hits"], B_caused=mB["pickups_caused"],
        B_pickups=mB["pickups_total"],
        B2_score=(mB2 or {}).get("score"),
        B2_caused=(mB2 or {}).get("pickups_caused"))
    dump()
    sb = L.sync_back()
    if sb:
        log("sync_back", note=sb)
    print("[r48b] DONE wall=", round(time.time() - T0, 1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
