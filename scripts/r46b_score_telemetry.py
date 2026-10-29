#!/usr/bin/env python3
"""r46b_score_telemetry.py — R46 (buzzybee, the 40% track, Issue #6).

The capsule lever (R45-B close-out), executed verbatim: the score
SOURCE is identifiable.  The 1401 line is INVARIANT across four
policy families (A recipe, policy5, policy6, policy7) = either the
checkpoint's fixed reward structure (6 wasp passes per 1500f) or
something simpler - r23's manifest note says the score word
"climbs +1/frame during play", which would make 1401 ~ survival
frames, not passes.  This round decides it by MEASUREMENT.

Method (the capsule): restore-only, 1 boot max: instrument the arm
loop with a per-frame u32 read at 0x8005883C (cheap: one read per
frame into the jsonl) -> ONE bot_policy5 arm (1500f, the R45-B arm-A
protocol verbatim: same checkpoint, same policy, same CAP_F) -> the
score-source table -> decide the R47 lever from the mechanism, not
from another policy variant.

The run doubles as the determinism check: bot_policy5 at this
checkpoint scored 1401 twice already (R43-B arm B, R45-B arm A) -
a third 1401 (score/hp/passes/flaps equal) confirms cross-process
restore determinism; any divergence is investigated, never averaged.

Doubles as the MSX-R46 mirror lesson applied: per-frame telemetry +
full context = the attribution discipline the MSX readouts lacked.
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

OUT = os.path.join(REPO, "scratch", "r46b")
L.OUT = OUT
L.SHOTS = os.path.join(OUT, "shots")
L.BOOTS = os.path.join(OUT, "boots_used.json")
os.makedirs(L.SHOTS, exist_ok=True)

CKPT_PATH = os.path.join(REPO, "scratch", "r45b",
                         "state_r45b_gs1.bin")   # READ-ONLY use
T0 = time.time()
CAP_F = P.CAP_F                # 1500, protocol parity


def run_arm_telemetry(bee, label, policy, kw, ckpt, log, R, dump):
    """The R45-B run_arm VERBATIM (button timing identical) + the
    per-frame score telemetry: rec["sc"] every frame + a SCORE_DELTA
    event at every change with the full context."""
    bee.unserialize(ckpt)
    w, fh = L.jl_writer(L.OUT, f"frames_{label}.jsonl")
    sticky = {}
    passes, hits, pickups, score_deltas = [], [], [], []
    bail_shapes = []
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
    prev_sc = bee.i32(L.SCORE)
    sc0 = prev_sc
    t_arm = time.time()
    while bee.frames_run - f_start < CAP_F:
        if bee.frames_run - f_start > 0 and \
                (bee.frames_run - f_start) % 150 == 0:
            log("arm_progress", f=bee.frames_run - f_start,
                wall_s=round(time.time() - t_arm, 1),
                score=prev_sc)
        s = bee.obs()
        flap, target, mode = policy(s, sticky, **kw)
        if mode == "flower":
            fx = [f for f in s["fl"]]
            best = None
            for i, (fx_, _fy) in enumerate(fx):
                if 0 < fx_ <= kw["flower_hi"] and \
                        (best is None or fx_ < best[1]):
                    best = (i, fx_)
            idx = best[0] if best else None
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
        # ---- advance (identical button timing to R45-B run_arm) ----
        if flap:
            bee.set_buttons("B")
            for _k in range(2):
                bee.run_frame()
                sc_now = bee.i32(L.SCORE)
                rec["sc"] = sc_now
                if sc_now != prev_sc:
                    score_deltas.append(
                        {"f": bee.frames_run, "d": sc_now - prev_sc,
                         "from": prev_sc, "to": sc_now, "mode": mode,
                         "in_pass": in_pass})
                    prev_sc = sc_now
            bee.set_buttons(set())
            bee.run(1, set())
            flaps += 1
        else:
            bee.run(1, set())
        # per-frame score read (the telemetry core)
        sc_now = bee.i32(L.SCORE)
        rec["sc"] = sc_now
        if sc_now != prev_sc:
            score_deltas.append({
                "f": bee.frames_run, "d": sc_now - prev_sc,
                "from": prev_sc, "to": sc_now, "mode": mode,
                "in_pass": in_pass,
                "f_since_pass_start":
                    (bee.frames_run - pass_start)
                    if pass_start is not None else None})
            prev_sc = sc_now
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
        prev_fl = s2["fl"]
        if bee.frames_run >= next_snap:
            bee.snap(f"r46b_{label}_gameplay", R)
            next_snap += 300
        if bee.i32(L.GS) != 1:
            death_f = bee.frames_run
            break
    fh.close()
    if in_pass:
        passes.append({"start_f": pass_start, "end_f": bee.frames_run,
                       "hit": hit_in_pass, "min_sep": pass_min_sep})
    st = bee.state()
    # ---- the score-source table ------------------------------------
    climbs = [d for d in score_deltas if d["d"] == 1]
    jumps = [d for d in score_deltas if d["d"] != 1]
    in_pass_deltas = [d for d in score_deltas if d.get("in_pass")]
    m = {
        "arm": label, "kw": kw,
        "survival_frames": (death_f - f_start) if death_f \
            else bee.frames_run - f_start,
        "death": death_f is not None, "gs": st["gs"],
        "score": st["score"], "hp": st["hp"], "flaps": flaps,
        "passes": len(passes),
        "dodges": sum(1 for p in passes if not p["hit"]),
        "close_dodges": len([p for p in passes
                             if not p["hit"] and p["min_sep"] < 30]),
        "pass_detail": passes,
        "enemy_hits": len(hits), "hit_detail": hits,
        "pickups_total": len(pickups),
        "pickups_caused": sum(1 for p in pickups if p["caused"]),
        "pickup_detail": pickups,
        "planner_replans": replans, "planner_bails": bails,
        "gm_frames": gm_seen,
        "score_telemetry": {
            "score_at_start": sc0, "score_at_end": st["score"],
            "n_delta_frames": len(score_deltas),
            "n_plus1_climb_frames": len(climbs),
            "sum_of_climbs": sum(d["d"] for d in climbs),
            "jumps": jumps,
            "delta_frames_in_pass": len(in_pass_deltas),
            "climb_frame_density":
                round(len(climbs) /
                      max(1, (st["score"] - sc0)), 3),
        },
        "frames_jsonl": f"frames_{label}.jsonl",
    }
    log(f"{label}_done", **{k: v for k, v in m.items()
                            if not k.endswith("_detail")
                            and k not in ("bail_shapes",
                                          "score_telemetry")})
    log(f"{label}_score_source", **m["score_telemetry"])
    dump()
    return m


def main():
    R, log, dump = L.make_logger(L.OUT, "boot_log_r46b.json", "r46b")
    if not os.path.exists(L.BOOTS):
        json.dump({"cap": 1, "count": 0, "log": [], "note":
                   "R46b ledger: cap 1 disclosed pre-run = the core+rom "
                   "load ONLY (restore-only from the preserved "
                   "scratch/r45b/state_r45b_gs1.bin - it survived the "
                   "round; the checkpoint bytes are NEVER rewritten by "
                   "this round).  Restores are NOT boots (r35 "
                   "precedent).",
                   "count_includes_core_load": True},
                  open(L.BOOTS, "w"), indent=1)
    led = L.ledger_use(2, "r46b_score_telemetry.py",
                       note="boot 1: core+rom load -> restore the "
                            "r45b gs1 checkpoint -> ONE bot_policy5 "
                            "arm 1500f with per-frame 0x8005883C "
                            "telemetry")
    log("ledger", count=led["count"], cap=led["cap"], out=L.OUT)
    if not os.path.exists(CKPT_PATH):
        raise SystemExit("r45b gs1 checkpoint MISSING - never "
                         "fabricate a checkpoint; rebuild would need "
                         "a fresh disclosed cap")
    CKPT = open(CKPT_PATH, "rb").read()
    log("checkpoint_loaded", path=CKPT_PATH, bytes=len(CKPT))
    bee = L.Bee("ws_r46b")
    av = bee.load_game()
    log("boot", core=bee.core.core_name, av=av)

    # ---- ONE-BOOT TIMING PROBE (disclosed in the ledger entry) ------
    # three 60-frame variants, then a clean re-restore before the arm:
    #   a) raw bee.run(60)            = pure emulator throughput
    #   b) obs+policy+run(1) x60      = + per-frame python (r45b loop)
    #   c) b + the score telemetry    = the full r46b loop
    bee.unserialize(CKPT)
    t = time.time(); bee.run(60, set())
    ta = time.time() - t
    t = time.time()
    for _ in range(60):
        s = bee.obs()
        P.bot_policy5(s, {}, engage=200, margin=16,
                      flower_hi=170, hover_y=95)
        bee.run(1, set())
    tb = time.time() - t
    t = time.time()
    for _ in range(60):
        s = bee.obs()
        flap, _tgt, _mode = P.bot_policy5(s, {}, engage=200,
                                          margin=16, flower_hi=170,
                                          hover_y=95)
        bee.run(1, set())
        _sc = bee.i32(L.SCORE)
    tc = time.time() - t
    log("timing_probe", raw60=round(ta, 3),
        loop60=round(tb, 3), tele60=round(tc, 3),
        fps_raw=round(60 / max(ta, 1e-9), 1),
        fps_loop=round(60 / max(tb, 1e-9), 1),
        fps_tele=round(60 / max(tc, 1e-9), 1))
    print(f"[r46b-probe] raw60={ta:.3f}s loop60={tb:.3f}s "
          f"tele60={tc:.3f}s", flush=True)

    mA = run_arm_telemetry(bee, "T", P.bot_policy5,
                           {"engage": 200, "margin": 16,
                            "flower_hi": 170, "hover_y": 95},
                           CKPT, log, R, dump)

    # ---- the determinism check vs R45-B arm A -----------------------
    REF = {"score": 1401, "hp": 5666, "passes": 6, "enemy_hits": 0}
    det = {k: (mA[k] == v) for k, v in REF.items()}
    det["DETERMINISM_OK"] = bool(all(det.values()))

    # ---- the mechanism verdict --------------------------------------
    st = mA["score_telemetry"]
    climbs = st["n_plus1_climb_frames"]
    jumps = st["jumps"]
    total = st["score_at_end"] - st["score_at_start"]
    if climbs and total and st["sum_of_climbs"] == total:
        mechanism = ("PER_FRAME_TIME: the score is a +1/frame climb "
                     "(n=" + str(climbs) + " climb frames = the whole "
                     "gain); the wasp passes and pickups contribute "
                     "NOTHING directly - the 1401 invariant across "
                     "four policy families is survival time, not "
                     "structure")
    elif jumps:
        mechanism = ("MIXED: +1 climbs n=" + str(climbs) +
                     " (" + str(st["sum_of_climbs"]) + ") + jumps " +
                     json.dumps(jumps[:12]))
    else:
        mechanism = ("EVENT_SCORED: no +1 climbs; every delta is a "
                     "discrete event - the pass/pickup structure "
                     "dominates")
    metrics = {
        "schema": "ps1play.r46b-evidence/1",
        "round": "R46 (buzzybee, the 40% track)",
        "boot_ledger": led,
        "checkpoint": CKPT_PATH + " (READ-ONLY restore)",
        "cap_frames": CAP_F,
        "arm_T": mA,
        "determinism_vs_r45b_armA": det,
        "score_mechanism": mechanism,
        "score_source_table": st,
        "wall_s": round(time.time() - T0, 1),
    }
    json.dump(metrics, open(os.path.join(L.OUT, "metrics_r46b.json"),
                            "w"), indent=1, default=str)
    log("r46b_verdict", mechanism=mechanism,
        determinism=det["DETERMINISM_OK"], score=mA["score"],
        hp=mA["hp"], passes=mA["passes"], hits=mA["enemy_hits"])
    dump()
    sb = L.sync_back()
    if sb:
        log("sync_back", note=sb)
    print("[r46b] DONE wall=", round(time.time() - T0, 1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
