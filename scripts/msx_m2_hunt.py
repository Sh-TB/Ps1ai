#!/usr/bin/env python3
"""msx_m2_hunt.py — Issue #5 session 10 / Issue #6 round 7 (task 17-a):
the ATTRACT-FLAG RAM HUNT (the recorded session-9 next lever).

One boot per process.  Restore the durable m2_train anchor -> faithful
RIGHT-hold ride to the scripted crash (S6-F1 teardown: px==0.0 &
php==0) -> during the post-crash NOW LOADING window take DENSE RAM
snapshots with FlipTracker:
  - 30f baseline sampling;
  - 3f granularity inside the scheduled window f[1000,1500) (the
    session-9 observed hijack onset f~1150-1250);
  - ADAPTIVE 3f granularity for 180f after an auto-detected onset
    (visual churn burst: madiff > 8.0 twice in a row).
Everything is diffed per byte; the tracker records first/last change
frame + count + start/end values for the offline ranker.

At the WINTER world spawn (session-9: px 120.3 php 120 score 0
input-DEAD attract demo) this run also:
  - saves the durable state "m2_winter" (force-test arm B checkpoint);
  - saves "m2_loading" mid-loading (force-test arm A checkpoint);
  - re-proves the control battery on THIS winter instance (quiet drift
    vs RIGHT delta vs score/php sanity) — the honest input-DEAD
    control for the force test.

No RAM writes here (observe-only).  Evidence: scratch/issue6_round7_msx/.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _REPO)

from ps1play import labconfig                       # noqa: E402
from issue4_controller import boot                  # noqa: E402
from e2e_policy_trial import snap, px_of, sha_file, DISC  # noqa: E402
from lives_banner_variant import raw_slots          # noqa: E402
import ps1play.agent.combat as combat               # noqa: E402
from msx_ramhunt_util import (FlipTracker, read_known, madiff,  # noqa: E402
                              sampling_gap, png, jlog, wall_out,
                              A_FLAGS)

EVID = "/home/z/my-project/ps1ai/scratch/issue6_round7_msx"
CHUNK_F = 30
RIDE_CHUNKS = 420
RIDE_WALL_S = 420.0
WATCH_BUDGET_F = 5400          # ~90 s of game time post-teardown
DENSE_SPANS = ((1000, 1500),)  # scheduled dense window (observed onset)
ONSET_MADIFF = 8.0
ONSET_HOLD = 2                 # consecutive samples above threshold
PNG_AT = (300, 600, 900, 1200, 1500, 1800, 2400, 3000, 3600, 4200,
          4800, 5400)


def log(*a):
    print("[m2h]", *a, file=sys.stderr, flush=True)


def ride(p, m, J, tag):
    """Faithful RIGHT-hold ride from the restored anchor to the
    scripted crash.  Returns the ride record (teardown obs included)."""
    prev = None
    max_px = 0.0
    php_events = []
    outcome = "budget"
    end_i = None
    td_obs = None
    t0 = time.time()
    for i in range(RIDE_CHUNKS):
        if wall_out(t0, RIDE_WALL_S):
            outcome = "wall_guard"
            log("ride wall guard at chunk", i)
            break
        s = snap(m)
        if s["px"] == 0.0 and s["php"] == 0:
            J({"ev": "TEARDOWN", "i": i, "f_rel": 0, **s})
            png(p, "td", tag)
            td_obs = s
            outcome, end_i = "teardown", i
            break
        if s["php"] == 0 and s["px"] != 0.0:
            J({"ev": "DEATH", "i": i, **s, "slots": raw_slots(m)})
            png(p, f"T{i:03d}_death", tag)
            got = False
            for w in range(100):
                p.core.run(30, set())
                s2 = snap(m)
                if s2["flags"] == 0xFF and s2["px"] != 0.0 \
                        and s2["php"] > 0:
                    got = True
                    break
            if not got:
                J({"ev": "DEAD_END", **snap(m)})
                outcome, end_i = "m2_game_over", i
                break
            prev = None
            continue
        sec0 = combat.scan_section(m)
        if sec0["state"] == 0xC:
            J({"ev": "M2_BANNER_0xC", "i": i, **s, "secv": sec0})
            outcome, end_i = "m2_clear_banner", i
            break
        if s["flags"] != 0xFF or s["px"] < 60.0 or s["px"] > 5000.0:
            p.core.run(60, set())
            prev = None
            continue
        px = s["px"]
        max_px = max(max_px, px)
        if prev is not None:
            for key in ("php", "gren", "score"):
                if s[key] != prev[key]:
                    php_events.append({"i": i, "key": key,
                                       "from": prev[key], "to": s[key],
                                       "px": px})
        p.core.run(CHUNK_F, {"RIGHT"})
        if i % 10 == 0:
            J({"ev": "R", "i": i, **s,
               "secv": {k: sec0[k] for k in ("state", "flags",
                                             "progress")}})
            log(f"R{i} px={px} score={s['score']} php={s['php']} "
                f"gren={s['gren']}")
        prev = s
    rec = {"outcome": outcome, "end_i": end_i, "max_px": round(max_px, 1),
           "php_events": php_events, "td_obs": td_obs,
           "wall_s": round(time.time() - t0, 1)}
    J({"ev": "RIDE_done", **{k: rec[k] for k in
                             ("outcome", "end_i", "max_px", "td_obs")}})
    return rec


def loading_watch(p, m, J, tag, ev_id):
    """Dense-snapshot watch of the post-crash loading window.  Returns
    (tracker, series, onset_f, outcome)."""
    tr = FlipTracker(m.ram)
    series = []
    onset_f = None
    hi_run = 0
    dense_until = -1
    score_reset_f = None
    score_at_td = None
    rgb_prev = p.core.frame_rgb()
    f = 0
    outcome = "watch_budget"
    spawn_seen = None
    loading_png_saved = False
    while f < WATCH_BUDGET_F:
        gap = sampling_gap(f, base=30, dense_spans=DENSE_SPANS,
                           dense_until=dense_until)
        p.core.run(gap, set())
        f += gap
        s = snap(m)
        k = read_known(m)
        rgb_now = p.core.frame_rgb()
        md = madiff(rgb_prev, rgb_now)
        rgb_prev = rgb_now
        if score_at_td is None and s["score"]:
            score_at_td = s["score"]
        if score_reset_f is None and score_at_td and s["score"] == 0:
            score_reset_f = f
            J({"ev": "SCORE_RESET", "f": f, **s})
        rec = {"f": f, "gap": gap, "madiff": md, **s,
               "flags32": k["flags32"], "sec_st": k["sec_st"],
               "sec_fl": k["sec_fl"], "prog": k["prog"]}
        series.append(rec)
        tr.step(f, m.ram)
        if f in PNG_AT:
            png(p, f"ld_f{f:05d}", tag)
        # ---- adaptive onset detection (visual churn burst) ----
        if onset_f is None and md is not None and md > ONSET_MADIFF:
            hi_run += 1
            if hi_run >= ONSET_HOLD:
                onset_f = f
                dense_until = f + 180
                J({"ev": "HIJACK_ONSET", "f": f, "madiff": md, **s})
                png(p, f"onset_f{f:05d}", tag)
                log(f"auto onset at f={f} madiff={md}")
        elif md is not None and md <= ONSET_MADIFF:
            hi_run = 0
        # ---- durable mid-loading checkpoint (force-test arm A) ----
        if not loading_png_saved and f >= 600:
            try:
                p.save_state("m2_loading")
                J({"ev": "M2_LOADING_SAVED", "f": f, **s})
                log(f"m2_loading saved at f={f}")
            except Exception as e:                          # noqa: BLE001
                J({"ev": "M2_LOADING_FAIL", "err": repr(e)[:120]})
            loading_png_saved = True
        # ---- winter spawn?  (alive + stable 90f) ----
        if (spawn_seen is None and s["px"] != 0.0 and s["php"] > 0
                and s["flags"] == 0xFF):
            p.core.run(90, set())
            s2 = snap(m)
            if (s2["px"] != 0.0 and s2["php"] > 0 and s2["flags"] == 0xFF):
                spawn_seen = {"f": f, **s2}
                J({"ev": "WINTER_SPAWN", **spawn_seen})
                png(p, "winter_spawn", tag)
                try:
                    p.save_state("m2_winter")
                    J({"ev": "M2_WINTER_SAVED", **s2})
                    log(f"m2_winter saved px={s2['px']}")
                except Exception as e:                      # noqa: BLE001
                    J({"ev": "M2_WINTER_FAIL", "err": repr(e)[:120]})
                outcome = "winter_spawn"
                break
            f += 90
            tr.step(f, m.ram)
            continue
    return tr, series, onset_f, outcome, score_reset_f


def winter_battery(p, m, J, tag):
    """CONTROL battery on the unmodified winter world (this instance):
    quiet drift -> RIGHT delta -> score/php sanity.  The honest
    input-DEAD control for the force-test arms."""
    px0 = px_of(m)
    p.core.run(90, set())
    drift = round(px_of(m) - px0, 1)
    s1 = snap(m)
    J({"ev": "BAT_QUIET", "px0": px0, "drift": drift, **s1})
    png(p, "bat_quiet", tag)
    p.core.run(90, {"RIGHT"})
    moved = round(px_of(m) - px0 - drift, 1)
    s2 = snap(m)
    J({"ev": "BAT_RIGHT", "moved_net": moved, **s2})
    png(p, "bat_right", tag)
    p.core.run(60, set())
    s3 = snap(m)
    J({"ev": "BAT_QUIET2", **s3})
    live = moved > 8.0 and s3["score"] == s1["score"] and s3["php"] > 0
    verdict = "INPUT_LIVE" if live else "INPUT_DEAD"
    J({"ev": "BAT_VERDICT", "verdict": verdict, "drift": drift,
       "moved_net": moved, "score_q": s1["score"], "score_r": s3["score"],
       "php_q": s1["php"], "php_r": s3["php"]})
    log(f"winter control battery: drift={drift} moved_net={moved} "
        f"score {s1['score']}->{s3['score']} php {s1['php']}->"
        f"{s3['php']} -> {verdict}")
    return verdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, default=1)
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    tag = f"m2h{args.run}_{time.strftime('%H%M%S')}"
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jlog(jf, ev)

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    J({"ev": "boot", "run": args.run, "firmware": fw, **snap(m)})
    log(f"=== m2 hunt run {args.run}: booted ({fw}) ===")
    p.load_state("m2_train")
    p.core.run(2, set())
    s0 = snap(m)
    J({"ev": "anchor_restored", **s0})
    log(f"anchor restored: px={s0['px']} php={s0['php']} "
        f"score={s0['score']} gren={s0['gren']}")
    png(p, "anchor", tag)
    rd = ride(p, m, J, tag)
    tr = series = None
    onset_f = outcome_w = score_reset_f = None
    battery = None
    if rd["outcome"] == "teardown":
        tr, series, onset_f, outcome_w, score_reset_f = \
            loading_watch(p, m, J, tag, rd["end_i"])
        if outcome_w == "winter_spawn":
            battery = winter_battery(p, m, J, tag)
    out = {"run": args.run, "firmware": fw,
           "anchor": s0, "ride": rd,
           "watch_outcome": outcome_w, "onset_f": onset_f,
           "score_reset_f": score_reset_f, "battery": battery,
           "wall_total_s": round(time.time() - t0, 1),
           "frames": p.core.frames_run, "game_sha256": sha_file(DISC)}
    if tr is not None:
        meta = {"kind": "m2_postcrash_loading", "run": args.run,
                "tag": tag, "onset_f": onset_f,
                "score_reset_f": score_reset_f,
                "anchor": s0, "td_obs": rd["td_obs"],
                "budget_f": WATCH_BUDGET_F,
                "sample_fs": [r["f"] for r in series],
                "madiff": [r["madiff"] for r in series],
                "battery": battery}
        out["tracker"] = tr.save(os.path.join(EVID, f"{tag}_tracker.npz"),
                                 meta)
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    with open(os.path.join(EVID, f"{tag}_series.json"), "w") as f:
        json.dump(series, f, default=str)
    J({"ev": "RUN_DONE", **{k: out[k] for k in
                            ("run", "watch_outcome", "onset_f",
                             "score_reset_f", "battery", "wall_total_s")}})
    jf.close()
    log(f"RUN m2h{args.run}: ride={rd['outcome']} watch={outcome_w} "
        f"onset={onset_f} battery={battery} wall={out['wall_total_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
