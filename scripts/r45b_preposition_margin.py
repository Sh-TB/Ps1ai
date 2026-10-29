#!/usr/bin/env python3
"""r45b_preposition_margin.py — R45 (buzzybee, the 40% track, Issue #6).

The capsule lever (R44 close-out), executed: the R44-B tie was a
flower-SUPPLY limit — the candidate that would reach the flower is
exactly the one the guarantee filter rejects.  R45 loosens the filter
ONLY in the pre-danger phase and pre-positions during it:

  bot_policy7 = the guarantee planner with a TIERED margin:
    - pre-danger (the danger window opens > t_enter_min frames out):
      GM 8 — more candidates pass the guarantee filter, and the
      policy6 flower-proximity selection can pick a hold-y near the
      reachable flower BEFORE the window opens (the seek-timing
      pre-position);
    - in-window (t_enter <= t_enter_min): GM 12 verbatim (the
      calibrated margin — the closed-loop per-frame replanning
      re-selects at the tier switch).
    Everything else verbatim: candidate enumeration, the flower-
    proximity selection, the bail (max band-center distance), the
    below-side no-tap rule.
  The capsule fallback protocol, implemented: any hit in arm B
  => arm B2 = the same planner with tier_pre = 12 (the revert);
  the margin floor is then FILED (GM 8 rejected at this checkpoint).

Protocol: arm A = bot_policy5 (the R43-B dominance recipe) verbatim,
arm B = bot_policy7 (tier 8/12), arm B2 = bot_policy7 (tier 12/12,
only on a B hit), 1500f each, same runner (run_arm44 semantics).
Restore-only arms; boot 1 = the core+rom load AND the gs1 checkpoint
rebuild (settle 900f -> START -> gs1 -> serialize) — DISCLOSED: the
sandbox rollback lost scratch/r43b/state_r43b_gs1.bin; the disc was
rebuilt internet-first sha-verified BEFORE this boot (upstream EXE
9b0bfc08... byte-identical, committed wrap script output 042b94bb...
byte-identical — the r42b precedent, 0 boots).

Oracle (the capsule): B hits == 0 AND B score >= 1550 AND
B pickups_caused >= 2 (score superiority over the 1401 tie line;
A/B exactness holds via the shared checkpoint).
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

OUT = os.path.join(REPO, "scratch", "r45b")
L.OUT = OUT
L.SHOTS = os.path.join(OUT, "shots")
L.BOOTS = os.path.join(OUT, "boots_used.json")
L.CKPT_PATH = os.path.join(OUT, "state_r45b_gs1.bin")
os.makedirs(L.SHOTS, exist_ok=True)

T0 = time.time()
CAP_F = P.CAP_F                # 1500, protocol parity
T_ENTER_MIN = 20               # tier-switch threshold (frames)
TIER_PRE, TIER_IN = 8, 12


def guaranteed_gm(traj, ey, evy, win, side, gm):
    """r43b_planner.guaranteed verbatim with the margin as a
    parameter (the module global GM is otherwise identical)."""
    for t in range(win[0] - 1, win[1]):
        y = traj[t]
        wy = L.predict_wasp_y(ey, evy, t + 1)
        top, bot = wy - 13, wy + 43
        if side == "above":
            if y > top - gm:
                return False
        else:
            if y < bot + gm:
                return False
    return True


def plan_exit7(by, bvy, ey, evy, ex, flowers, tier_pre=TIER_PRE,
               tier_in=TIER_IN, t_enter_min=T_ENTER_MIN):
    """The tiered-margin flower-seeking guarantee planner.

    Identical candidate enumeration + selection + bail to
    r44b.plan_exit6; the ONLY change is the margin fed to the
    guarantee filter, tiered by the time until the danger window
    opens (pre-danger tier_pre=8, in-window tier_in=12)."""
    horizon = max(2, min(P.SIM_CAP, int((ex + 36.0) / 1.5) + 2))
    win = P.danger_window(ex, horizon)
    center = ey + 15.0
    if win is None:            # window over: wasp past, anything goes
        side = "above" if by < center else "below"
        return False, float(by), side, True, tier_in
    gm = tier_in if win[0] <= t_enter_min else tier_pre
    fl_target = None
    for fx, fy in flowers:
        if 0 < fx <= 170.0:
            fl_target = fy + 5
            break
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
            flap = P.traj_control_now(by, bvy, side, tgt)
            return flap, float(tgt), side, True, gm
    # ---- bail: maximize the distance from the band center ----------
    side = "above" if by < center else "below"
    if side == "above":
        tgt = max(L.Y_MIN + 4, L.Y_MIN + 10)
    else:
        tgt = min(L.Y_MAX - 4, L.Y_MAX - 10)
    flap = P.traj_control_now(by, bvy, side, tgt)
    return flap, float(tgt), side, False, gm


def bot_policy7(s, sticky, engage=200, flower_hi=170, hover_y=95,
                tier_pre=TIER_PRE, tier_in=TIER_IN,
                t_enter_min=T_ENTER_MIN):
    by, bvy = s["by"], s["bvy"]
    ex, ey, evy = s["e"][0], s["e"][1], s["e"][2]
    if L.PASS_END_X < ex <= engage:
        flap, target, side, planned, gm = plan_exit7(
            by, bvy, ey, evy, ex, s["fl"], tier_pre, tier_in,
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
        return flap, target, "dodge"
    # no-wasp windows: the verbatim policy3 flower logic (unchanged)
    sticky["side"] = None
    sticky["vy"] = None
    sticky["planned"] = None
    sticky["gm"] = None
    sticky["flip"] = False
    best = None
    for i, (fx, fy) in enumerate(s["fl"]):
        if 0 < fx <= flower_hi and (best is None or fx < best[1]):
            best = (i, fx, fy)
    if best:
        target = max(L.Y_MIN + 2, min(L.Y_MAX - 2, best[2] + 5))
        return (by > target + 4 and bvy > -3000), target, "flower"
    return (by > hover_y and bvy > -3000), hover_y, "hover"


def seek_target_idx(s, kw):
    best = None
    for i, (fx, fy) in enumerate(s["fl"]):
        if 0 < fx <= kw["flower_hi"] and (best is None or fx < best[1]):
            best = (i, fx)
    return best[0] if best else None


def run_arm(bee, label, policy, kw, ckpt, log, R, dump):
    """The R44-B run_arm44 VERBATIM (protocol parity) + the gm-tier
    capture on dodge frames + the death/gs watch; no behavior change."""
    bee.unserialize(ckpt)
    w, fh = L.jl_writer(L.OUT, f"frames_{label}.jsonl")
    sticky = {}
    passes, hits, pickups, bail_shapes = [], [], [], []
    seek = {"idx": None, "since": None}
    n_fl_snap = n_hit_snap = 0
    in_pass, hit_in_pass = False, False
    pass_start, pass_min_sep = None, 10 ** 9
    prev_hp = bee.i32(L.HEALTH)
    prev_fl = bee.obs()["fl"]
    f_start = bee.frames_run
    flaps = 0
    death_f = None
    next_snap = bee.frames_run + 300
    replans = 0
    bails = 0
    gm_seen = {}
    while bee.frames_run - f_start < CAP_F:
        s = bee.obs()
        flap, target, mode = policy(s, sticky, **kw)
        if mode == "flower":
            idx = seek_target_idx(s, kw)
            if seek["idx"] != idx:
                seek["idx"], seek["since"] = idx, bee.frames_run
        else:
            seek["idx"], seek["since"] = None, None
        rec = {"ph": label, "f": bee.frames_run, "mode": mode,
               "tgt": round(target, 1), "side": sticky.get("side"),
               "planned": sticky.get("planned"),
               "flip": sticky.get("flip"),
               "by": s["by"], "bvy": s["bvy"], "e": s["e"], "fl": s["fl"]}
        if mode == "dodge":
            replans += 1
            gm = sticky.get("gm")
            if gm is not None:
                gm_seen[gm] = gm_seen.get(gm, 0) + 1
            if sticky.get("planned"):
                pass
            else:
                bails += 1
                ex_, ey_ = s["e"][0], s["e"][1]
                top, bot = ey_ - 13, ey_ + 43
                covers = (top <= L.Y_MIN + P.GM
                          and bot >= L.Y_MAX - P.GM)
                bail_shapes.append({"f": bee.frames_run, "by": s["by"],
                                    "bvy": s["bvy"], "ex": ex_,
                                    "ey": ey_, "band_top": top,
                                    "band_bot": bot,
                                    "covers_column": covers,
                                    "side": sticky.get("side")})
        if flap:
            bee.set_buttons("B")
            for _k in range(2):
                bee.run_frame()
            bee.set_buttons(set())
            bee.run(1, set())
            flaps += 1
        else:
            bee.run(1, set())
        s2 = bee.obs()
        rec["f_end"] = bee.frames_run
        rec.update(by=s2["by"], bvy=s2["bvy"], e=s2["e"], fl=s2["fl"])
        w(rec)
        ex, ey = s2["e"][0], s2["e"][1]
        if L.PASS_END_X < ex <= kw["engage"]:
            if not in_pass:
                in_pass, hit_in_pass = True, False
                pass_start, pass_min_sep = bee.frames_run, 10 ** 9
            pass_min_sep = min(pass_min_sep,
                               max(ex - L.BEE_X2,
                                   abs(s2["by"] - ey) - 13))
        elif in_pass:
            in_pass = False
            passes.append({"start_f": pass_start,
                           "end_f": bee.frames_run,
                           "hit": hit_in_pass,
                           "min_sep": pass_min_sep})
        hp_now = bee.i32(L.HEALTH)
        dh = hp_now - prev_hp
        prev_hp = hp_now
        if dh <= -1000:
            hit_in_pass = True
            hits.append({"f": bee.frames_run, "dh": dh, "by": s2["by"],
                         "bvy": s2["bvy"], "e": s2["e"], "mode": mode,
                         "side": sticky.get("side"),
                         "planned": sticky.get("planned"),
                         "gm": sticky.get("gm"),
                         "f_since_pass_start":
                             (bee.frames_run - pass_start)
                             if pass_start is not None else None})
            log(f"{label}_enemy_edge", **hits[-1])
            if n_hit_snap < 2:
                bee.snap(f"r45b_{label}_hit", R)
                n_hit_snap += 1
        elif dh >= 900:
            picked = [i for i in range(3)
                      if prev_fl[i][0] > 0 and s2["fl"][i][0] <= -49]
            seek_dur = (bee.frames_run - seek["since"]) \
                if (seek["idx"] is not None and mode == "flower" and
                    picked and seek["idx"] in picked and
                    seek["since"] is not None) else 0
            recent_seek = (seek["since"] is not None
                           and bee.frames_run - seek["since"]
                           <= P.PICKUP_WINDOW_F)
            caused = bool((mode == "flower" and picked
                           and seek_dur >= P.SEEK_MIN_F)
                          or (picked and recent_seek))
            pickups.append({"f": bee.frames_run, "dh": dh,
                            "picked_idx": picked, "seek_dur": seek_dur,
                            "caused": caused, "mode": mode,
                            "recent_seek": bool(recent_seek)})
            log(f"{label}_flower_edge", **pickups[-1])
            if n_fl_snap < 2:
                bee.snap(f"r45b_{label}_flower", R)
                n_fl_snap += 1
        prev_fl = s2["fl"]
        if bee.frames_run >= next_snap:
            bee.snap(f"r45b_{label}_gameplay", R)
            next_snap += 300
        if bee.i32(L.GS) != 1:
            death_f = bee.frames_run
            break
    fh.close()
    if in_pass:
        passes.append({"start_f": pass_start, "end_f": bee.frames_run,
                       "hit": hit_in_pass, "min_sep": pass_min_sep})
    st = bee.state()
    close = [p for p in passes if not p["hit"] and p["min_sep"] < 30]
    m = {
        "arm": label, "kw": kw,
        "survival_frames": (death_f - f_start) if death_f \
            else bee.frames_run - f_start,
        "death": death_f is not None, "gs": st["gs"],
        "score": st["score"], "hp": st["hp"], "flaps": flaps,
        "passes": len(passes),
        "dodges": sum(1 for p in passes if not p["hit"]),
        "close_dodges": len(close), "pass_detail": passes,
        "enemy_hits": len(hits), "hit_detail": hits,
        "pickups_total": len(pickups),
        "pickups_caused": sum(1 for p in pickups if p["caused"]),
        "pickup_detail": pickups,
        "planner_replans": replans, "planner_bails": bails,
        "gm_frames": gm_seen,
        "bail_shapes": bail_shapes,
        "frames_jsonl": f"frames_{label}.jsonl",
    }
    log(f"{label}_done", **{k: v for k, v in m.items()
                            if not k.endswith("_detail")
                            and k != "bail_shapes"})
    dump()
    return m


def main():
    R, log, dump = L.make_logger(L.OUT, "boot_log_r45b.json", "r45b")
    if not os.path.exists(L.BOOTS):
        json.dump({"cap": 1, "count": 0, "log": [], "note":
                   "R45b ledger: cap 1 disclosed pre-run = the core+rom "
                   "load AND the gs1 checkpoint rebuild (DISCLOSED: the "
                   "sandbox rollback lost scratch/r43b/"
                   "state_r43b_gs1.bin; the disc was rebuilt internet-"
                   "first sha-verified before this boot: upstream EXE "
                   "9b0bfc08... byte-identical, committed wrap-script "
                   "output 042b94bb... byte-identical — the r42b "
                   "precedent, 0 boots); the arms are restore-only "
                   "(restores are NOT boots, r35 precedent)",
                   "count_includes_core_load": True},
                  open(L.BOOTS, "w"), indent=1)
    led = L.ledger_use(1, "r45b_preposition_margin.py",
                       note="boot 1: core+rom load -> gs1 checkpoint "
                            "rebuild (disclosed) -> arm A (bot_policy5 "
                            "verbatim) -> arm B (bot_policy7 tiered "
                            "8/12) -> arm B2 (tier 12/12) only on a B "
                            "hit")
    log("ledger", count=led["count"], cap=led["cap"], out=L.OUT)
    bee = L.Bee("ws_r45b")
    av = bee.load_game()
    log("boot", core=bee.core.core_name, av=av)

    # ---- boot 1: rebuild the gs1 checkpoint (r42b pattern) ----------
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
    bee.snap("r45b_checkpoint", R)

    # ---- arm A: the R43-B dominance recipe verbatim ------------------
    mA = run_arm(bee, "A", P.bot_policy5,
                 {"engage": 200, "margin": 16, "flower_hi": 170,
                  "hover_y": 95}, CKPT, log, R, dump)
    # ---- arm B: the tiered-margin pre-position planner ---------------
    mB = run_arm(bee, "B", bot_policy7,
                 {"engage": 200, "flower_hi": 170, "hover_y": 95},
                 CKPT, log, R, dump)
    # ---- arm B2: the capsule revert protocol (only on a B hit) -------
    mB2 = None
    if mB["enemy_hits"] > 0:
        log("margin_floor_hit", b_hits=mB["enemy_hits"],
            revert="tier_pre=12")
        mB2 = run_arm(bee, "B2", bot_policy7,
                      {"engage": 200, "flower_hi": 170, "hover_y": 95,
                       "tier_pre": 12, "tier_in": 12},
                      CKPT, log, R, dump)

    best_B = mB2 if (mB2 is not None
                     and (mB2["enemy_hits"] == 0
                          and mB["enemy_hits"] > 0)) else mB
    oracle = {
        "b_hits_zero": best_B["enemy_hits"] == 0,
        "b_score_ge_1550": best_B["score"] >= 1550,
        "b_caused_ge_2": best_B["pickups_caused"] >= 2,
    }
    oracle["SCORE_GOAL"] = bool(all(oracle.values()))
    covers = [b for b in mB["bail_shapes"] if b["covers_column"]]
    metrics = {
        "schema": "ps1play.r45b-evidence/1",
        "round": "R45 (buzzybee, the 40% track)",
        "boot_ledger": led,
        "checkpoint": L.CKPT_PATH + " (rebuilt in boot 1, disclosed)",
        "disc_rebuild": {"exe_sha256": "9b0bfc08...c909a8ba "
                                       "(byte-identical)",
                         "disc_sha256": "042b94bb...bb093 "
                                        "(byte-identical)",
                         "boots_used": 0},
        "tiered_margin": {"pre": TIER_PRE, "in": TIER_IN,
                          "t_enter_min": T_ENTER_MIN},
        "cap_frames": CAP_F,
        "arm_A": mA,
        "arm_B": mB,
        "arm_B2": mB2,
        "margin_floor_filed": bool(mB2 is not None),
        "oracle": oracle,
        "bail_geometry": {
            "bails": mB["planner_bails"],
            "replans": mB["planner_replans"],
            "covers_column_count": len(covers),
        },
        "wall_s": round(time.time() - T0, 1),
    }
    json.dump(metrics, open(os.path.join(L.OUT, "metrics_r45b.json"),
                            "w"), indent=1, default=str)
    log("r45b_verdict", score_goal=oracle["SCORE_GOAL"],
        A_hits=mA["enemy_hits"], B_hits=mB["enemy_hits"],
        A_score=mA["score"], B_score=mB["score"],
        B2_score=(mB2 or {}).get("score"),
        A_caused=mA["pickups_caused"], B_caused=mB["pickups_caused"],
        B_gm_frames=mB["gm_frames"])
    dump()
    sb = L.sync_back()
    if sb:
        log("sync_back", note=sb)
    print("[r45b] DONE wall=", round(time.time() - T0, 1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
