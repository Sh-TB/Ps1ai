#!/usr/bin/env python3
"""msx_m2_extend.py — Issue #5 session 9 (round 6): extend the M2 train
ride PAST the session-8 reproduced frontier (px 822.4) toward the
Mission-2 conclusion, from the durable m2_train anchor.

Run A (m2_train_advance.py --run 7) regenerated the anchor locally:
M2 spawn px 76.4 php 76 gren 10 score 0 (bit-par with session-6/7
spawn telemetry).  This run restores it (one boot per process) and:

  v1: faithful RIGHT-hold ride, per-chunk census; at the first
      scene teardown (px==0.0 & php==0) run the FINE ladder log:
      15f-granularity signature recording, and START accepts ONLY on
      the exact M1-proven countdown signature (px 0.0, sec (11,1),
      flags 255) with world_stable verification after each tap.
      Success = a NEXT mission spawn (score 0, px<100, flags 0xFF)
      or a 0xC-class banner.  Honest terminus otherwise.
  v2: same ride, but on ride-stall (px unchanged >= 8 chunks while
      flags==0xFF) KEEP holding RIGHT through the suspected fade for
      900f before any teardown logic — tests whether the mission
      thread survives the fade when the stick never releases.

Evidence: scratch/issue6_round6_msx/ (jsonl + report + PNGs).
"""
import argparse
import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _REPO)

from ps1play import labconfig                       # noqa: E402
from issue4_controller import boot                  # noqa: E402
from e2e_policy_trial import snap, alive, px_of, sha_file, DISC  # noqa: E402
from lives_banner_variant import raw_slots          # noqa: E402
import ps1play.agent.combat as combat               # noqa: E402

EVID = "/home/z/my-project/ps1ai/scratch/issue6_round6_msx"
CHUNK_F = 30
PNG_EVERY = 10
RIDE_CHUNKS = 420                 # 420*30 = 12600f ~ session-7 ride budget
STALL_CHUNKS = 8                  # px frozen this many chunks -> stall


def log(*a):
    print("[m2x]", *a, file=sys.stderr, flush=True)


def png(p, name, tag):
    try:
        rgb = p.core.frame_rgb()
        if rgb is not None:
            from PIL import Image
            Image.fromarray(rgb).save(os.path.join(EVID,
                                                  f"{tag}_{name}.png"))
    except Exception as e:                                  # noqa: BLE001
        log("png failed:", repr(e)[:120])


def ride(p, m, J, tag, variant):
    """RIGHT-hold ride from the restored anchor with full census."""
    prev = None
    max_px = 0.0
    php_events = []
    st_hist = {}
    kind_counts = {}
    stall_run = 0
    last_px = None
    outcome = "budget"
    end_i = None
    t0 = time.time()
    for i in range(RIDE_CHUNKS):
        if time.time() - t0 > 420.0:
            outcome = "wall_guard"
            log("wall guard at chunk", i)
            break
        s = snap(m)
        # ---- scene teardown: px==0.0 <=> php==0 (S6-F1) ----
        if s["px"] == 0.0 and s["php"] == 0:
            J({"ev": "TEARDOWN", "i": i, **s})
            png(p, f"T{i:03d}_td", tag)
            if variant == "v3":
                outcome, end_i = teardown_watch(p, m, J, tag, i)
            elif variant == "v4":
                outcome, end_i = teardown_m3(p, m, J, tag, i)
            elif variant == "v5":
                outcome, end_i = teardown_m3(p, m, J, tag, i, feed=True)
            elif variant == "v6":
                outcome, end_i = teardown_taps(p, m, J, tag, i)
            else:
                outcome, end_i = teardown_fine(p, m, J, tag, i)
            break
        # ---- real death ----
        if s["php"] == 0 and s["px"] != 0.0:
            J({"ev": "DEATH", "i": i, **s, "slots": raw_slots(m)})
            png(p, f"T{i:03d}_death", tag)
            got = False
            for w in range(100):
                p.core.run(30, set())
                if alive(m):
                    got = True
                    break
            if not got:
                J({"ev": "DEAD_END", **snap(m)})
                png(p, "gameover", tag)
                outcome, end_i = "m2_game_over", i
                break
            prev = None
            continue
        sec0 = combat.scan_section(m)
        if sec0["state"] == 0xC:
            J({"ev": "M2_BANNER_0xC", "i": i, **s, "secv": sec0})
            png(p, f"T{i:03d}_banner", tag)
            outcome, end_i = "m2_clear_banner", i
            break
        if s["flags"] != 0xFF or s["px"] < 60.0:
            J({"ev": "ANOMALY", "i": i, **s})
            png(p, f"T{i:03d}_an", tag)
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
        # ---- stall detection (v2 lever) ----
        if last_px is not None and abs(px - last_px) < 1.0:
            stall_run += 1
        else:
            stall_run = 0
        last_px = px
        if variant == "v2" and stall_run == STALL_CHUNKS:
            J({"ev": "STALL_HOLD_RIGHT", "i": i, "px": px, **s})
            png(p, f"T{i:03d}_stall", tag)
            # keep holding RIGHT through the suspected fade: 900f
            p.core.run(900, {"RIGHT"})
            s2 = snap(m)
            J({"ev": "AFTER_HOLD", "i": i, **s2})
            png(p, f"T{i:03d}_afterhold", tag)
            if s2["px"] == 0.0 and s2["php"] == 0:
                outcome, end_i = teardown_watch(p, m, J, tag, i) \
                    if variant == "v3" else teardown_fine(p, m, J, tag, i)
                break
            prev = None
            continue
        p.core.run(CHUNK_F, {"RIGHT"})
        if i % 3 == 0:
            slots = raw_slots(m)
            ents = combat.scan_entities(m, px=px)
            for sl in slots:
                st_hist[sl["st"]] = st_hist.get(sl["st"], 0) + 1
            for en in ents:
                kind_counts[en.get("kind")] = \
                    kind_counts.get(en.get("kind"), 0) + 1
            J({"ev": "T", "i": i, **s, "secv": {k: sec0[k] for k in
                                                ("state", "flags",
                                                 "progress")},
               "slots": slots,
               "ents": [{k: en.get(k) for k in
                         ("slot", "x_px", "dx_px", "st", "hp_a4", "h")}
                        for en in ents]})
        elif i % 5 == 0:
            J({"ev": "T", "i": i, **s, "secv": {k: sec0[k] for k in
                                                ("state", "flags",
                                                 "progress")}})
        if i % PNG_EVERY == 0:
            png(p, f"T{i:04d}", tag)
            log(f"T{i} px={px} sec={s['sec']} score={s['score']} "
                f"php={s['php']} gren={s['gren']}")
        prev = s
    rec = {"outcome": outcome, "end_i": end_i, "max_px": round(max_px, 1),
           "php_events": php_events,
           "st_hist": {str(k): v for k, v in
                       sorted(st_hist.items(), key=lambda kv: -kv[1])[:16]},
           "kind_counts": {str(k): v for k, v in
                           sorted(kind_counts.items(),
                                  key=lambda kv: -kv[1])[:12]},
           "final": snap(m), "wall_s": round(time.time() - t0, 1)}
    J({"ev": "RIDE_done", **{k: rec[k] for k in
                             ("outcome", "end_i", "max_px", "final")}})
    png(p, "ride_final", tag)
    return rec


def teardown_watch(p, m, J, tag, i0):
    """v3: observe-ONLY long watch after the M2-end loading: what does
    the game become after NOW LOADING completes?  10800f budget, 30f
    sampling, PNG every 100f.  No inputs at all.  Detects a next-
    mission spawn signature if one appears."""
    outcome = "watch_budget"
    seq = []
    for w in range(360):                     # 360*30 = 10800f
        p.core.run(30, set())
        s = snap(m)
        f = w * 30
        seq.append({"f": f, "px": s["px"], "php": s["php"],
                    "score": s["score"], "sec": list(s["sec"]),
                    "flags": s["flags"]})
        if w % 4 == 0:                       # PNG every 120f
            png(p, f"wt{i0}_f{f:05d}", tag)
        if (s["flags"] == 0xFF and 0.0 < s["px"] < 100.0
                and s["score"] == 0 and s["php"] > 0):
            J({"ev": "NEXT_SPAWN_WATCH", "f": f, **s})
            png(p, f"wt{i0}_spawn_f{f:05d}", tag)
            try:
                p.save_state("m3_spawn")
                J({"ev": "M3_ANCHOR_SAVED", **s})
            except Exception as e:                          # noqa: BLE001
                J({"ev": "M3_ANCHOR_FAIL", "err": repr(e)[:120]})
            outcome = "next_mission_spawn"
            break
        if s["px"] != 0.0 and s["php"] > 0 and s["flags"] == 0xFF:
            J({"ev": "WORLD_ALIVE_WATCH", "f": f, **s})
            png(p, f"wt{i0}_alive_f{f:05d}", tag)
            outcome = "world_alive"
            break
    J({"ev": "WATCH_done", "i": i0, "outcome": outcome,
       "transitions": [x for j, x in enumerate(seq)
                       if j and any(x[k] != seq[j - 1][k]
                                    for k in ("px", "php", "score",
                                              "flags"))]})
    with open(os.path.join(EVID, f"watch_i{i0}_full.json"), "w") as f:
        json.dump(seq, f, default=str)
    png(p, f"wt{i0}_final", tag)
    return outcome, i0


def teardown_m3(p, m, J, tag, i0, feed=False):
    """v4: watch for the post-loading world, then PROVE input
    responsiveness (the session-8 attract discriminator), save the
    m3_spawn anchor, and RIDE Mission 3 with census.
    feed=True (v5): tap SELECT 1f every 240f during the wait — tests
    whether the attract hijack is an input-free-frame timer."""
    # ---- phase A: wait for a world-alive sample (no inputs) ----
    spawned = None
    for w in range(400):                     # 12000f budget
        if feed and w and w % 16 == 0:       # every 240f: 1f SELECT
            p.core.run(1, {"SELECT"})
        p.core.run(15, set())
        s = snap(m)
        if s["px"] != 0.0 and s["php"] > 0 and s["flags"] == 255:
            spawned = {"f": w * 15, **s}
            break
    if not spawned:
        J({"ev": "M3_NO_SPAWN", "i": i0, "feed": feed})
        png(p, f"m3{i0}_nospawn", tag)
        return "no_spawn", i0
    J({"ev": "M3_SPAWN_SEEN", "i": i0, "feed": feed, **spawned})
    png(p, f"m3{i0}_spawn", tag)
    # ---- phase B: the input causality battery ----
    px0 = px_of(m)
    p.core.run(90, {"RIGHT"})
    s1 = snap(m)
    moved = round(s1["px"] - px0, 1)
    J({"ev": "M3_RIGHT_PROBE", "px0": px0, "moved": moved, **s1})
    png(p, f"m3{i0}_right", tag)
    input_ok = moved > 8.0
    score0 = s1["score"]
    ents0 = combat.scan_entities(m, px=s1["px"])
    p.core.run(120, {"B"})                   # PSX CROSS = fire
    s2 = snap(m)
    ents1 = combat.scan_entities(m, px=s2["px"])
    J({"ev": "M3_FIRE_PROBE", "score0": score0, "score1": s2["score"],
       "ents0": len(ents0), "ents1": len(ents1), **s2})
    png(p, f"m3{i0}_fire", tag)
    if not input_ok:
        J({"ev": "M3_INPUT_DEAD", **s2})
        png(p, f"m3{i0}_inputdead", tag)
        return "attract_like_no_input", i0
    # ---- phase C: the m3 anchor + the ride ----
    try:
        p.save_state("m3_spawn")
        J({"ev": "M3_ANCHOR_SAVED", **s2})
        log("M3 ANCHOR SAVED px=", s2["px"])
    except Exception as e:                                  # noqa: BLE001
        J({"ev": "M3_ANCHOR_FAIL", "err": repr(e)[:120]})
    max_px = s2["px"]
    php_events = []
    prev = s2
    outcome = "m3_budget"
    for i in range(300):
        s = snap(m)
        if s["px"] == 0.0 and s["php"] == 0:
            J({"ev": "M3_TEARDOWN", "i": i, **s})
            png(p, f"m3{i}_td", tag)
            outcome = "m3_teardown"
            break
        if s["php"] == 0 and s["px"] != 0.0:
            J({"ev": "M3_DEATH", "i": i, **s})
            png(p, f"m3{i}_death", tag)
            for w in range(100):
                p.core.run(30, set())
                if alive(m):
                    break
            prev = None
            continue
        sec0 = combat.scan_section(m)
        if sec0["state"] == 0xC:
            J({"ev": "M3_BANNER_0xC", "i": i, **s, "secv": sec0})
            png(p, f"m3{i}_banner", tag)
            outcome = "m3_clear_banner"
            break
        if s["flags"] != 255 or s["px"] < 60.0:
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
        p.core.run(30, {"RIGHT"})
        if i % 3 == 0:
            ents = combat.scan_entities(m, px=px)
            J({"ev": "M3T", "i": i, **s,
               "secv": {k: sec0[k] for k in ("state", "flags",
                                             "progress")},
               "ents": [{k: en.get(k) for k in
                         ("slot", "x_px", "dx_px", "st", "hp_a4")}
                        for en in ents]})
        elif i % 5 == 0:
            J({"ev": "M3T", "i": i, **s})
        if i % 10 == 0:
            png(p, f"m3T{i:03d}", tag)
            log(f"M3T{i} px={px} sec={s['sec']} score={s['score']} "
                f"php={s['php']}")
        prev = s
    J({"ev": "M3_done", "outcome": outcome, "max_px": round(max_px, 1),
       "php_events": php_events, "final": snap(m)})
    png(p, "m3_final", tag)
    return f"m3_{outcome}", i0


def teardown_taps(p, m, J, tag, i0):
    """v6: bounded START taps EARLY in the post-M2 loading window
    (f300/f900/f1500) — a hidden CONTINUE?/mission prompt would sit
    there before the attract logo hijacks at ~f1200-2400.  Any tap
    that wakes a world runs the input battery + M3 ride."""
    taps = (300, 900, 1500)
    outcome = "taps_no_effect"
    for ti, tf in enumerate(taps):
        p.core.run(tf if ti == 0 else taps[ti] - taps[ti - 1] - 252,
                   set())
        s0 = snap(m)
        if s0["px"] != 0.0 and s0["php"] > 0 and s0["flags"] == 255:
            J({"ev": "EARLY_WORLD", "tap": ti, **s0})
            outcome = "world_before_tap"
            break
        p.core.run(12, {"START"})
        p.core.run(240, set())
        s = snap(m)
        J({"ev": "EARLY_TAP", "tap": ti, "f": tf, **s})
        png(p, f"td{i0}_tap{ti}", tag)
        if s["px"] != 0.0 and s["php"] > 0 and s["flags"] == 255:
            J({"ev": "TAP_WOKE_WORLD", "tap": ti, **s})
            png(p, f"td{i0}_woke", tag)
            outcome = "tap_woke_world"
            break
    if outcome in ("tap_woke_world", "world_before_tap"):
        return teardown_m3_tail(p, m, J, tag, i0)
    # honest watch to terminus
    for w in range(160):
        p.core.run(30, set())
        s = snap(m)
        if s["px"] != 0.0 and s["php"] > 0 and s["flags"] == 255:
            J({"ev": "LATE_WORLD", "f": 1500 + w * 30, **s})
            png(p, f"td{i0}_late", tag)
            outcome = "late_world_after_taps"
            return teardown_m3_tail(p, m, J, tag, i0)
    J({"ev": "TAPS_done", "i": i0, "outcome": outcome,
       "final": snap(m)})
    png(p, f"td{i0}_tapsfinal", tag)
    return outcome, i0


def teardown_m3_tail(p, m, J, tag, i0):
    """Shared tail of v6: input battery + m3 anchor + ride."""
    px0 = px_of(m)
    p.core.run(90, {"RIGHT"})
    s1 = snap(m)
    moved = round(s1["px"] - px0, 1)
    J({"ev": "M3_RIGHT_PROBE", "px0": px0, "moved": moved, **s1})
    png(p, f"m3{i0}_right", tag)
    if moved <= 8.0:
        J({"ev": "M3_INPUT_DEAD", **s1})
        png(p, f"m3{i0}_inputdead", tag)
        return "attract_like_no_input", i0
    try:
        p.save_state("m3_spawn")
        J({"ev": "M3_ANCHOR_SAVED", **s1})
        log("M3 ANCHOR SAVED px=", s1["px"])
    except Exception as e:                                  # noqa: BLE001
        J({"ev": "M3_ANCHOR_FAIL", "err": repr(e)[:120]})
    max_px = s1["px"]
    prev = s1
    outcome = "m3_budget"
    for i in range(240):
        s = snap(m)
        if s["px"] == 0.0 and s["php"] == 0:
            J({"ev": "M3_TEARDOWN", "i": i, **s})
            png(p, f"m3{i}_td", tag)
            outcome = "m3_teardown"
            break
        if s["php"] == 0 and s["px"] != 0.0:
            J({"ev": "M3_DEATH", "i": i, **s})
            png(p, f"m3{i}_death", tag)
            for w in range(100):
                p.core.run(30, set())
                if alive(m):
                    break
            prev = None
            continue
        sec0 = combat.scan_section(m)
        if sec0["state"] == 0xC:
            J({"ev": "M3_BANNER_0xC", "i": i, **s, "secv": sec0})
            png(p, f"m3{i}_banner", tag)
            outcome = "m3_clear_banner"
            break
        if s["flags"] != 255 or s["px"] < 60.0:
            p.core.run(60, set())
            prev = None
            continue
        px = s["px"]
        max_px = max(max_px, px)
        p.core.run(30, {"RIGHT"})
        if i % 3 == 0:
            ents = combat.scan_entities(m, px=px)
            J({"ev": "M3T", "i": i, **s,
               "secv": {k: sec0[k] for k in ("state", "flags",
                                             "progress")},
               "ents": [{k: en.get(k) for k in
                         ("slot", "x_px", "dx_px", "st", "hp_a4")}
                        for en in ents]})
        elif i % 5 == 0:
            J({"ev": "M3T", "i": i, **s})
        if i % 10 == 0:
            png(p, f"m3T{i:03d}", tag)
            log(f"M3T{i} px={px} sec={s['sec']} score={s['score']} "
                f"php={s['php']}")
        prev = s
    J({"ev": "M3_done", "outcome": outcome, "max_px": round(max_px, 1),
       "final": snap(m)})
    png(p, "m3_final", tag)
    return f"m3_{outcome}", i0


def teardown_fine(p, m, J, tag, i0):
    """Fine-grained teardown ladder: 15f sampling, START accepts ONLY
    on the exact countdown signature, world_stable verified."""
    ladder = []
    accepted = None
    outcome = "teardown_unresolved"
    for w in range(240):                     # 240*15 = 3600f budget
        p.core.run(15, set())
        s = snap(m)
        rec = {"f": w * 15, "px": s["px"], "php": s["php"],
               "score": s["score"], "sec": list(s["sec"]),
               "flags": s["flags"]}
        ladder.append(rec)
        # next-mission spawn?
        if s["flags"] == 0xFF and 0.0 < s["px"] < 100.0 and s["score"] == 0:
            J({"ev": "NEXT_SPAWN", "i": i0, **s, "slots": raw_slots(m)})
            png(p, "next_spawn", tag)
            try:
                p.save_state("m3_spawn")
                J({"ev": "M3_ANCHOR_SAVED", "state": "m3_spawn", **s})
                log("M3 ANCHOR SAVED px=", s["px"], "php=", s["php"])
            except Exception as e:                          # noqa: BLE001
                J({"ev": "M3_ANCHOR_FAIL", "err": repr(e)[:120]})
            outcome = "next_mission_spawn"
            break
        # exact countdown signature -> the ONE proven START accept
        if (s["px"] == 0.0 and s["sec"] == (11, 1) and s["flags"] == 255
                and w * 15 >= 300 and accepted is None):
            J({"ev": "COUNTDOWN_TAP", "f": w * 15, **s})
            png(p, f"td{i0}_countdown", tag)
            p.core.run(12, {"START"})
            p.core.run(300, set())
            accepted = True
            s2 = snap(m)
            J({"ev": "AFTER_TAP", **s2})
            png(p, f"td{i0}_aftertap", tag)
            if s2["px"] != 0.0:
                outcome = "start_accepted_resume"
                break
    J({"ev": "LADDER", "i": i0, "outcome": outcome,
       "ladder": ladder[::4]})             # every 4th sample to jsonl
    with open(os.path.join(EVID, f"ladder_i{i0}_full.json"), "w") as f:
        json.dump(ladder, f, default=str)
    png(p, f"td{i0}_final", tag)
    return outcome, i0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=("v1", "v2", "v3", "v4", "v5",
                                          "v6"),
                    default="v1")
    ap.add_argument("--run", type=int, default=1)
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    tag = f"m2x{args.run}_{args.variant}_{time.strftime('%H%M%S')}"
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    J({"ev": "boot", "variant": args.variant, "firmware": fw, **snap(m)})
    log(f"=== extend {args.variant} run {args.run}: booted ({fw}) ===")
    p.load_state("m2_train")
    p.core.run(2, set())
    s0 = snap(m)
    J({"ev": "anchor_restored", **s0})
    log(f"anchor restored: px={s0['px']} php={s0['php']} "
        f"score={s0['score']} gren={s0['gren']}")
    png(p, "anchor", tag)
    rec = ride(p, m, J, tag, args.variant)
    out = {"variant": args.variant, "run": args.run, "firmware": fw,
           "anchor": s0, "ride": rec,
           "wall_total_s": round(time.time() - t0, 1),
           "frames": p.core.frames_run, "game_sha256": sha_file(DISC)}
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    J({"ev": "RUN_DONE", **out})
    jf.close()
    log(f"RUN {tag}: outcome={rec['outcome']} max_px={rec['max_px']} "
        f"wall={out['wall_total_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
