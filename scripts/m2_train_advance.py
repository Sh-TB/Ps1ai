#!/usr/bin/env python3
"""m2_train_advance.py — Issue #5 session 7: MISSION 2 (the TRAIN)
advance past px 404 with the full observation kit.

Session-6 (commit f5a6b1a) proved M2 ENTRY: banner -> CONTINUE? one
START -> walk -> M2 spawn px 74.6 (php 74 gren 10) -> a disclosed
RIGHT-hold ride to px 404.1 in 120 chunks.  Everything past 404 is
white space: no entity census, no walker decode, no mission-end
signature (session-6 honest_limits[0]).

This run (one process, one boot) — the PROVEN session-6 entry path:
  1. fresh boot -> the shipped CombatPolicy CONTINUOUSLY to the
     MISSION 1 banner (e2e_policy_trial.run_once control=False — the
     session-5 e2e arm, 3/3, now teardown-aware via the S6-F1 fix).
     RUN m2t1 LESSON: the pin_ckpt control arm is NOT a valid M2-entry
     path — its post-banner S taps re-entered the fragile end window
     (S4-F4), re-armed the D7 pin cycle (S4-F5) and the T phase died
     in it (px frozen 1164/1413, sec (0xB,0x43), score never reset).
     The fresh-boot path is the only one that ever reached M2 (3/3,
     session-6) — use it.
  2. post-banner W/S/Q phases (watch / START taps / quiet) until
     gameplay resumes (the proven session-6 predicates).
  3. phase T: the SAME disclosed RIGHT-hold instrument, but with
     PER-CHUNK observation — 36-slot census + scan_entities +
     scan_section every 3rd chunk — pushed PAST px 404 until budget,
     a real death, or an M2-clear banner (state 0xC -> STOP inputs,
     that is the pass-the-stage evidence; post-clear flow is the next
     session's work).
  4. at the first stable M2 gameplay (score==0, px<100 spawn) SAVE
     STATE "m2_train" — the first durable train anchor (none existed;
     every future run starts on the train instead of re-playing M1).

Teardown awareness (S6-F1 + session-7 telemetry train_vocab_17d.md):
px == 0.0 <=> php == 0 with ZERO counterexamples across 7 recorded
runs -> SCENE_TEARDOWN (tally / CONTINUE? / NOW LOADING / score
reset), never a death.  QUIET-FIRST resolution (the session-6
walk_forward lesson: the M1->M2 ladder — tally -> countdown ->
loading -> score reset -> spawn — is input-free and self-resolves;
input inside it re-arms the end machinery): quiet-wait on
world_stable, and only if the CONTINUE? countdown signature persists
(px 0.0, sec (11,1), flags 255) tap START, bounded.  Real deaths
happen at px != 0 and get the full forensics burst.  The tally-world
trap (px 992 / php 120 reads alive ~100f) is filtered by
world_stable's 90f re-check.

ONE boot per process (the proven in-process constraint).  Evidence:
JSONL + report_*.json + PNGs under evidence issue5_m2_train/.
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
import ps1play.agent.combat as combat               # noqa: E402
from e2e_policy_trial import (snap, alive, px_of, sha_file, run_once,
                              DISC, PLAYER_HP, GRENADES)  # noqa: E402
from lives_banner_variant import raw_slots          # noqa: E402

EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "issue5_m2_train")
T_CHUNKS_DEFAULT = 600       # 30f each -> 18000f ~= 300 game-seconds
T_CHUNK_F = 30
CENSUS_EVERY = 3             # census chunk stride
PNG_EVERY = 15
T_WALL_S = 8.0 * 60          # phase-T wall guard
SPAWN_PX_MAX = 100.0         # a fresh mission spawn sits below this
ANOMALY_PX_MIN = 60.0        # below the mission-start window -> anomaly


def log(*a):
    print("[m2t]", *a, file=sys.stderr, flush=True)


def png(p, name, tag):
    try:
        rgb = p.core.frame_rgb()
        if rgb is not None:
            from PIL import Image
            Image.fromarray(rgb).save(os.path.join(EVID,
                                                  f"{tag}_{name}.png"))
    except Exception as e:                                  # noqa: BLE001
        log("png failed:", repr(e)[:120])


def world_ready(m):
    """A world that LOOKS alive (flags/px/php).  Note the trap: the
    tally's own world satisfies this ~100f after a teardown — callers
    that must not re-enter on it need world_stable()."""
    s = snap(m)
    return s["flags"] == 0xFF and 60.0 < s["px"] < 4096.0 and s["php"] > 0


def world_stable(p, m):
    """Re-check 90f apart: two consecutive world-alive samples with a
    bounded px drift.  The tally world (px 992, php 120) dies back to
    the countdown within ~100f, so it fails this; a real resume
    (endzone px 992 / M2 spawn px 74.6) persists."""
    s1 = snap(m)
    if not (s1["px"] != 0.0 and s1["flags"] == 0xFF and s1["php"] > 0):
        return False
    p.core.run(90, set())
    s2 = snap(m)
    return (s2["px"] != 0.0 and s2["flags"] == 0xFF and s2["php"] > 0
            and abs(s2["px"] - s1["px"]) < 250.0)


def right_probe(p, m, J, tag, label):
    """The ONLY admissible gameplay predicate (session-6): the player
    ADVANCES under RIGHT with flags 0xFF.  RAW observation only."""
    px0 = px_of(m)
    p.core.run(90, {"RIGHT"})
    moved = round(px_of(m) - px0, 1)
    s2 = snap(m)
    J({"ev": "RIGHT_PROBE", "label": label, "from_px": px0,
       "moved_px": moved, **s2})
    png(p, f"{label}_right", tag)
    ok = moved > 8.0 and s2["flags"] == 0xFF
    if ok:
        J({"ev": "GAMEPLAY_AFTER_BANNER", "label": label, **s2})
        log(f"GAMEPLAY AFTER BANNER ({label}) moved {moved}px "
            f"px={s2['px']} sec={s2['sec']}")
    return ok


def post_banner(p, m, J, tag, deaths):
    """The proven session-6 post-scene flow: W (no-input watch) ->
    S (START taps) -> Q (quiet) — each phase hands off on the RIGHT
    probe.  Reused verbatim semantics; also serves as the teardown
    resolution machinery (the countdown needs ONE START)."""
    for w in range(6):
        p.core.run(150, set())
        s = snap(m)
        J({"ev": "W", "step": w, "deaths": deaths, **s})
        png(p, f"W{w}", tag)
        log(f"W{w}: px={s['px']} sec={s['sec']} flags={s['flags']} "
            f"score={s['score']}")
        if world_ready(m) and right_probe(p, m, J, tag, f"W{w}"):
            return "gameplay_seen"
    for k in range(4):
        p.core.run(12, {"START"})
        p.core.run(300, set())
        s = snap(m)
        J({"ev": "S", "tap": k + 1, "deaths": deaths, **s})
        png(p, f"S{k + 1}", tag)
        log(f"S{k + 1}: px={s['px']} sec={s['sec']} flags={s['flags']} "
            f"score={s['score']}")
        if world_ready(m) and right_probe(p, m, J, tag, f"S{k + 1}"):
            return "gameplay_seen"
    for q in range(4):
        p.core.run(300, set())
        s = snap(m)
        J({"ev": "Q", "step": q, **s})
        png(p, f"Q{q}", tag)
        if world_ready(m) and right_probe(p, m, J, tag, f"Q{q}"):
            return "gameplay_seen"
    return "no_gameplay_seen"


def train_phase(p, m, J, tag, t_chunks=T_CHUNKS_DEFAULT):
    """Phase T — the disclosed RIGHT-hold ride with the full census
    kit.  Returns the phase record."""
    spawns_seen = 0
    anchor_saved = False
    st_hist = {}            # entity word0 -> row count (census chunks)
    kind_counts = {}        # scan_entities kind -> count
    php_events = []
    prev = None
    max_px = 0.0
    outcome = "budget"
    end_i = None
    t0 = time.time()
    for i in range(t_chunks):
        if time.time() - t0 > T_WALL_S:
            outcome = "t_wall_guard"
            log("T wall guard at chunk", i)
            break
        s = snap(m)
        # ---- scene teardown (S6-F1): px==0.0 <=> php==0 ----
        # QUIET-FIRST: the ladder (tally/countdown/loading/reset) is
        # input-free — m2t1 showed taps inside it re-arm the pin cycle.
        if s["px"] == 0.0 and s["php"] == 0:
            J({"ev": "SCENE_TEARDOWN", "i": i, **s})
            png(p, f"T{i:03d}_teardown", tag)
            r = "quiet_self_resolved"
            for w in range(90):              # ~2700f quiet budget
                p.core.run(30, set())
                if world_stable(p, m):
                    break
            else:
                # ladder stuck on the CONTINUE? countdown (px 0.0,
                # sec (11,1), flags 255): the ONE proven START accept
                s3 = snap(m)
                if s3["px"] == 0.0 and s3["sec"] == (11, 1) \
                        and s3["flags"] == 255:
                    for k in range(4):
                        p.core.run(12, {"START"})
                        p.core.run(300, set())
                        J({"ev": "TEARDOWN_START", "k": k + 1,
                           **snap(m)})
                        if world_stable(p, m):
                            r = f"start_accept_{k + 1}"
                            break
            s2 = snap(m)
            J({"ev": "TEARDOWN_RESOLVED", "i": i, "result": r, **s2})
            log(f"teardown resolved ({r}) px={s2['px']} "
                f"score={s2['score']} sec={s2['sec']}")
            if s2["flags"] == 0xFF and 0.0 < s2["px"] < SPAWN_PX_MAX \
                    and s2["score"] == 0:
                spawns_seen += 1
                if spawns_seen == 1:
                    J({"ev": "M2_SPAWN", "i": i, **s2,
                       "slots": raw_slots(m)})
                    png(p, "m2_spawn", tag)
                    if not anchor_saved:
                        try:
                            p.save_state("m2_train")
                            anchor_saved = True
                            J({"ev": "M2_ANCHOR_SAVED", "state":
                               "m2_train", **s2})
                            log("ANCHOR SAVED: m2_train "
                                f"px={s2['px']} php={s2['php']}")
                        except Exception as e:              # noqa: BLE001
                            J({"ev": "M2_ANCHOR_FAIL",
                               "err": repr(e)[:120], **s2})
                else:
                    J({"ev": "NEXT_MISSION_SPAWN", "n": spawns_seen,
                       "i": i, **s2, "slots": raw_slots(m)})
                    png(p, f"next_mission_{spawns_seen}", tag)
                    outcome = "mission_chain_advanced"
                    end_i = i
                    break
            prev = None                      # fresh event baseline
            continue
        # ---- real death: px != 0, php == 0 ----
        if s["php"] == 0 and s["px"] != 0.0:
            J({"ev": "T_DEATH", "i": i, **s, "slots": raw_slots(m)})
            log(f"T death i{i} px={s['px']}")
            for fi, fr in enumerate((0, 10, 10, 20)):
                if fr:
                    p.core.run(fr, set())
                png(p, f"T_death_f{fi}", tag)
            got = False
            for w in range(100):             # ~3000f respawn budget
                p.core.run(30, set())
                if alive(m):
                    got = True
                    break
            if not got:
                J({"ev": "T_DEAD_END", **snap(m)})
                png(p, "T_gameover", tag)
                outcome = "m2_game_over"
                end_i = i
                break
            prev = None
            continue
        # ---- transition garbage ----
        if s["px"] > 5000.0:
            p.core.run(60, set())
            continue
        # ---- the mission-clear banner: check BEFORE the anomaly gate
        # (it sits at px 26.4, below ANOMALY_PX_MIN) ----
        sec0 = combat.scan_section(m)
        if sec0["state"] == 0xC:
            J({"ev": "M2_BANNER_0xC", "i": i, **s, "secv": sec0})
            png(p, f"T{i:03d}_banner", tag)
            log(f"MISSION 0xC BANNER i{i} px={s['px']} "
                f"score={s['score']}")
            outcome = "m2_clear_banner"
            end_i = i
            break
        if s["flags"] != 0xFF or s["px"] < ANOMALY_PX_MIN:
            J({"ev": "T_ANOMALY", "i": i, **s})
            png(p, f"T{i:03d}_an", tag)
            p.core.run(60, set())
            prev = None
            continue
        # ---- stable gameplay chunk ----
        sec = sec0
        px = s["px"]
        max_px = max(max_px, px)
        if prev is not None:
            for key in ("php", "gren", "score"):
                if s[key] != prev[key]:
                    php_events.append({"i": i, "key": key,
                                       "from": prev[key], "to": s[key],
                                       "px": px})
        p.core.run(T_CHUNK_F, {"RIGHT"})
        if i % CENSUS_EVERY == 0:
            slots = raw_slots(m)
            ents = combat.scan_entities(m, px=px)
            for sl in slots:
                st_hist[sl["st"]] = st_hist.get(sl["st"], 0) + 1
            for en in ents:
                kind_counts[en.get("kind")] = \
                    kind_counts.get(en.get("kind"), 0) + 1
            J({"ev": "T", "i": i, **s, "secv": {k: sec[k] for k in
                                                ("state", "flags",
                                                 "progress")},
               "slots": slots,
               "ents": [{k: en.get(k) for k in
                         ("slot", "x_px", "dx_px", "st", "hp_a4", "h")}
                        for en in ents]})
        elif i % 10 == 0:
            J({"ev": "T", "i": i, **s, "secv": {k: sec[k] for k in
                                                ("state", "flags",
                                                 "progress")}})
        if i % PNG_EVERY == 0:
            png(p, f"T{i:04d}", tag)
            log(f"T{i} px={px} sec={s['sec']} score={s['score']} "
                f"php={s['php']} gren={s['gren']}")
        prev = s
    rec = {"outcome": outcome, "end_i": end_i, "spawns_seen": spawns_seen,
           "anchor_saved": anchor_saved, "max_px": round(max_px, 1),
           "php_events": php_events,
           "st_hist": {str(k): v for k, v in
                       sorted(st_hist.items(),
                              key=lambda kv: -kv[1])[:16]},
           "kind_counts": {str(k): v for k, v in
                           sorted(kind_counts.items(),
                                  key=lambda kv: -kv[1])[:12]},
           "final": snap(m), "chunks": t_chunks,
           "wall_s": round(time.time() - t0, 1)}
    J({"ev": "T_done", **{k: rec[k] for k in
                          ("outcome", "end_i", "spawns_seen",
                           "anchor_saved", "max_px", "final")}})
    png(p, "T_final", tag)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--chunks", type=int, default=2600,
                    help="fresh-boot M1 chunk budget (e2e banner c=107)")
    ap.add_argument("--t_chunks", type=int, default=T_CHUNKS_DEFAULT)
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    tag = f"m2t{args.run}_{time.strftime('%H%M%S')}"
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    J({"ev": "boot", "run": args.run, "firmware": fw, **snap(m)})
    log(f"=== m2 train advance run {args.run}: booted ({fw}) ===")
    # fresh-boot e2e arm — the ONLY path that ever reached M2 (session-5
    # 3/3 banner, session-6 3/3 M2 entry); the pin_ckpt control arm
    # re-arms the pin cycle on re-entry (m2t1 evidence)
    rec = run_once(p, m, J, tag, args.chunks, control=False)
    J({"ev": "e2e_result", **{k: rec[k] for k in
                              ("outcome", "end_chunk", "deaths")}})
    log("M1 fresh boot:", rec["outcome"], "c=", rec["end_chunk"],
        "deaths=", rec["deaths"])
    post = trec = None
    if rec["outcome"] == "MISSION_BANNER":
        post = post_banner(p, m, J, tag, rec["deaths"])
        J({"ev": "post_banner", "result": post})
        log("post-banner:", post)
        if post == "gameplay_seen":
            trec = train_phase(p, m, J, tag, t_chunks=args.t_chunks)
    else:
        log("M1 fresh boot did not reach the banner — aborting before T")
    out = {"m1": {k: rec[k] for k in
                  ("outcome", "end_chunk", "deaths", "was_deep",
                   "final", "wall_s")},
           "post_banner": post, "train": trec,
           "run": args.run, "firmware": fw,
           "wall_total_s": round(time.time() - t0, 1),
           "frames": p.core.frames_run,
           "game_sha256": sha_file(DISC)}
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    J({"ev": "RUN_DONE", **out})
    jf.close()
    log(f"RUN m2t{args.run}: m1={rec['outcome']} post={post} "
        f"train={trec['outcome'] if trec else None} "
        f"max_px={trec['max_px'] if trec else None} "
        f"wall={out['wall_total_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
