#!/usr/bin/env python3
"""r44b_flower_superiority.py — R44 (buzzybee, the 40% track, Issue #6).

The capsule lever, executed: DOMINANCE -> SCORE SUPERIORITY.  The
guarantee planner ties A at 1401 because it inherits the policy3
flower logic verbatim and spends its dodge windows purely defensively
(bot_policy5's plan_exit returns the FIRST guaranteed candidate sorted
by same-side + nearest-to-current-y).  R44 widens the flower seek INTO
the guarantee safe phases:

  bot_policy6: among the GUARANTEED (side, target) candidates, prefer
  the one whose hold-y is CLOSEST to the nearest reachable flower
  (0 < fx <= flower_hi); the guarantee filter is unchanged (the whole
  danger window with the GM margin), so the flower seek can never
  sacrifice safety - if the flower itself is not guarantee-reachable,
  the planner takes the guaranteed candidate nearest to it, and when
  NOTHING is guaranteed, the recorded bail fires unchanged.  The
  return-to-safe trajectory therefore always satisfies the guarantee
  at the danger-window boundary (the capsule's exact condition);
  closed-loop per-frame replanning absorbs the model error.

  Secondary: name the bail geometry - every unplanned dodge frame
  records the predicted band [wy-13, wy+43], the bee y, and whether
  the band covers the whole flyable column (an unavoidable sweep).

Protocol: arm A = the recorded bot-A recipe verbatim (bot_policy2,
engage=150, margin=16, flower_hi=160, hover_y=95), arm B =
bot_policy6 (engage=200, margin=16, flower_hi=170, hover_y=95),
1500f each, both through the SAME runner (run_arm44 = the R43-B
run_arm + the bail-shape capture; no behavior change).  Restore-only:
the r43b gs1 checkpoint is PRESERVED (scratch/r43b/state_r43b_gs1.bin)
-> 1 boot (the core+rom load) + 2 restores; restores are not boots
(r35 precedent); a checkpoint-loss rebuild would be disclosed.

Oracle (the capsule): B enemy_hits == 0 AND B score > A score AND
B score >= 1500 AND B pickups_caused >= 2.
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

# ---- retarget the libs to the R44b scratch dir (after P's import re-
# targeted them to r43b; R44b must not write into R43-B evidence) -------
OUT = os.path.join(REPO, "scratch", "r44b")
L.OUT = OUT
L.SHOTS = os.path.join(OUT, "shots")
L.BOOTS = os.path.join(OUT, "boots_used.json")
L.CKPT_PATH = os.path.join(REPO, "scratch", "r43b",
                           "state_r43b_gs1.bin")   # the PRESERVED ckpt
os.makedirs(L.SHOTS, exist_ok=True)

T0 = time.time()
CAP_F = P.CAP_F                # 1500, protocol parity
GM = P.GM                      # 12


def plan_exit6(by, bvy, ey, evy, ex, engage, margin, flowers):
    """The flower-seeking guarantee planner.  Identical candidate
    enumeration + guarantee filter to plan_exit; the selection among
    guaranteed candidates minimizes the distance to the nearest
    reachable flower (fallback: the plan_exit preference)."""
    horizon = max(2, min(P.SIM_CAP, int((ex + 36.0) / 1.5) + 2))
    win = P.danger_window(ex, horizon)
    center = ey + 15.0
    if win is None:            # window over: wasp past, anything goes
        side = "above" if by < center else "below"
        return False, float(by), side, True
    # the flower target: nearest reachable flower (the policy3 rule)
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
        # FLOWER SEEK: guaranteed candidates ranked by flower proximity
        cands.sort(key=lambda c: (abs(c[1] - fl_target),
                                  0 if (c[0] == "above") == (by < center)
                                  else 1, abs(c[1] - by)))
    else:
        cands.sort(key=lambda c: (0 if (c[0] == "above") == (by < center)
                                  else 1, abs(c[1] - by)))
    best_g = None
    for side, tgt in cands:
        traj = P.sim_bee_hold(by, bvy, side, tgt, horizon)
        if P.guaranteed(traj, ey, evy, win, side):
            best_g = (side, tgt)
            break
    if best_g is not None:
        side, tgt = best_g
        flap = P.traj_control_now(by, bvy, side, tgt)
        return flap, float(tgt), side, True
    # ---- bail: maximize the distance from the band center ----------
    side = "above" if by < center else "below"
    if side == "above":
        tgt = max(L.Y_MIN + 4, L.Y_MIN + 10)
    else:
        tgt = min(L.Y_MAX - 4, L.Y_MAX - 10)
    flap = P.traj_control_now(by, bvy, side, tgt)
    return flap, float(tgt), side, False


def bot_policy6(s, sticky, engage=200, margin=16, flower_hi=170,
                hover_y=95):
    by, bvy = s["by"], s["bvy"]
    ex, ey, evy = s["e"][0], s["e"][1], s["e"][2]
    if L.PASS_END_X < ex <= engage:
        flap, target, side, planned = plan_exit6(by, bvy, ey, evy, ex,
                                                 engage, margin, s["fl"])
        prev_side = sticky.get("side")
        flipped = (sticky.get("vy") is not None
                   and (sticky["vy"] < 0) != (evy < 0))
        sticky["vy"] = evy
        sticky["side"] = side
        sticky["planned"] = planned
        sticky["flip"] = bool(flipped or
                              (prev_side is not None
                               and prev_side != side))
        return flap, target, "dodge"
    # no-wasp windows: the verbatim policy3 flower logic (unchanged)
    sticky["side"] = None
    sticky["vy"] = None
    sticky["planned"] = None
    sticky["flip"] = False
    best = None
    for i, (fx, fy) in enumerate(s["fl"]):
        if 0 < fx <= flower_hi and (best is None or fx < best[1]):
            best = (i, fx, fy)
    if best:
        target = max(L.Y_MIN + 2, min(L.Y_MAX - 2, best[2] + 5))
        return (by > target + 4 and bvy > -3000), target, "flower"
    return (by > hover_y and bvy > -3000), hover_y, "hover"


def run_arm44(bee, label, policy, kw, ckpt, log, R, dump):
    """The R43-B run_arm verbatim + the bail-shape capture (secondary);
    no behavior change - both arms run through this same runner."""
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
    while bee.frames_run - f_start < CAP_F:
        s = bee.obs()
        flap, target, mode = policy(s, sticky, **kw)
        if mode == "flower":
            idx = P.seek_target_idx(s, kw)
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
            if sticky.get("planned"):
                bails += 0
            else:
                bails += 1
                ex_, ey_ = s["e"][0], s["e"][1]
                top, bot = ey_ - 13, ey_ + 43
                covers = (top <= L.Y_MIN + GM and bot >= L.Y_MAX - GM)
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
            passes.append({"start_f": pass_start, "end_f": bee.frames_run,
                           "hit": hit_in_pass, "min_sep": pass_min_sep})
        hp_now = bee.i32(L.HEALTH)
        dh = hp_now - prev_hp
        prev_hp = hp_now
        if dh <= -1000:
            hit_in_pass = True
            hits.append({"f": bee.frames_run, "dh": dh, "by": s2["by"],
                         "bvy": s2["bvy"], "e": s2["e"], "mode": mode,
                         "side": sticky.get("side"),
                         "planned": sticky.get("planned"),
                         "f_since_pass_start": (bee.frames_run
                                                - pass_start)
                         if pass_start is not None else None})
            log(f"{label}_enemy_edge", **hits[-1])
            if n_hit_snap < 2:
                bee.snap(f"r44b_{label}_hit", R)
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
                bee.snap(f"r44b_{label}_flower", R)
                n_fl_snap += 1
        prev_fl = s2["fl"]
        if bee.frames_run >= next_snap:
            bee.snap(f"r44b_{label}_gameplay", R)
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
        "death": death_f is not None, "gs": st["gs"], "score": st["score"],
        "hp": st["hp"], "flaps": flaps,
        "passes": len(passes),
        "dodges": sum(1 for p in passes if not p["hit"]),
        "close_dodges": len(close), "pass_detail": passes,
        "enemy_hits": len(hits), "hit_detail": hits,
        "pickups_total": len(pickups),
        "pickups_caused": sum(1 for p in pickups if p["caused"]),
        "pickup_detail": pickups,
        "planner_replans": replans, "planner_bails": bails,
        "bail_shapes": bail_shapes,
        "frames_jsonl": f"frames_{label}.jsonl",
    }
    log(f"{label}_done", **{k: v for k, v in m.items()
                            if not k.endswith("_detail")
                            and k != "bail_shapes"})
    dump()
    return m


def main():
    R, log, dump = L.make_logger(L.OUT, "boot_log_r44b.json", "r44b")
    if not os.path.exists(L.BOOTS):
        json.dump({"cap": 1, "count": 0, "log": [], "note":
                   "R44b ledger: cap 1 disclosed pre-run = the core+rom "
                   "load itself; the gs1 checkpoint is PRESERVED "
                   "(scratch/r43b/state_r43b_gs1.bin) -> restore-only "
                   "arms (restores are NOT boots, r35 precedent); a "
                   "checkpoint-loss rebuild would be disclosed as the "
                   "1 boot", "count_includes_core_load": True},
                  open(L.BOOTS, "w"), indent=1)
    led = L.ledger_use(1, "r44b_flower_superiority.py",
                       note="core+rom load (the disclosed 1 boot) -> "
                            "restore the preserved r43b gs1 checkpoint "
                            "-> arm A (bot-A recipe verbatim) 1500f -> "
                            "restore -> arm B (bot_policy6 flower-"
                            "seeking guarantee) 1500f")
    log("ledger", count=led["count"], cap=led["cap"], out=L.OUT)
    bee = L.Bee("ws_r44b")
    av = bee.load_game()
    log("boot", core=bee.core.core_name, av=av)
    if not os.path.exists(L.CKPT_PATH):
        raise SystemExit("the preserved gs1 checkpoint is MISSING - "
                         "a rebuild boot would need fresh disclosure")
    CKPT = open(L.CKPT_PATH, "rb").read()
    log("checkpoint_restored", src=L.CKPT_PATH, bytes=len(CKPT))

    mA = run_arm44(bee, "A", L.bot_policy2,
                   {"engage": 150, "margin": 16, "flower_hi": 160,
                    "hover_y": 95}, CKPT, log, R, dump)
    mB = run_arm44(bee, "B", bot_policy6,
                   {"engage": 200, "margin": 16, "flower_hi": 170,
                    "hover_y": 95}, CKPT, log, R, dump)

    superior = (mB["enemy_hits"] == 0 and mB["score"] > mA["score"]
                and mB["score"] >= 1500 and mB["pickups_caused"] >= 2)
    covers = [b for b in mB["bail_shapes"] if b["covers_column"]]
    metrics = {
        "schema": "ps1play.r44b-evidence/1",
        "round": "R44 (buzzybee, the 40% track)",
        "boot_ledger": led,
        "checkpoint": L.CKPT_PATH + " (preserved, restore-only)",
        "cap_frames": CAP_F,
        "guarantee_margin_px": GM,
        "arm_A": mA,
        "arm_B": mB,
        "superiority_oracle": {
            "b_hits_zero": mB["enemy_hits"] == 0,
            "b_score_gt_A": mB["score"] > mA["score"],
            "b_score_ge_1500": mB["score"] >= 1500,
            "b_caused_ge_2": mB["pickups_caused"] >= 2,
            "SCORE_SUPERIOR": bool(superior),
        },
        "bail_geometry": {
            "bails": mB["planner_bails"],
            "replans": mB["planner_replans"],
            "covers_column_count": len(covers),
            "named_shape": ("full-column-sweep (unavoidable)"
                            if covers and len(covers) >= 3
                            else "partial-column (positionable)"),
        },
        "wall_s": round(time.time() - T0, 1),
    }
    json.dump(metrics, open(os.path.join(L.OUT, "metrics_r44b.json"),
                            "w"), indent=1, default=str)
    log("r44b_verdict", superior=bool(superior),
        A_hits=mA["enemy_hits"], B_hits=mB["enemy_hits"],
        A_score=mA["score"], B_score=mB["score"],
        A_caused=mA["pickups_caused"], B_caused=mB["pickups_caused"],
        B_bails=mB["planner_bails"], B_covers=len(covers))
    dump()
    sb = L.sync_back()
    if sb:
        log("sync_back", note=sb)
    print("[r44b] DONE wall=", round(time.time() - T0, 1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
