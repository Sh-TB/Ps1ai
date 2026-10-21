#!/usr/bin/env python3
"""issue5_explore_invuln.py — CHEAT_ASSISTED_EXPLORATION run with the
VERIFIED invincibility profile, pushing through the helicopter barrier
(segment S000 far end) as deep into Mission 1 as the budget allows.

User priority (translated): "become invincible first; keep shooting
and advancing to the end of the map; the damage that kills must be
fully disabled; map enemy shots / firing paths."

Profile isolation (ps1play.agent.cheatprof):
  * CHEAT_ASSISTED_EXPLORATION — explicit --opt-in required; every
    enabled code is logged with exact frames; this run is NEVER
    reportable as a no-cheat clear.
  * Codes (each individually VERIFIED in the registry):
      hp_pair_freeze  8<live_f6> <val> + 8<live_fe> <val>  (per-boot
                      derivation via bounded hit-diff scan)
      bombs           800398BE 2400 (instruction patch, boot-indep.)
  * The published 3-line invuln patch stays OFF (registry: FAILED).

Mechanics:
  * GameShark tick EVERY frame (hardware-faithful pre-engage + poke).
  * Hit sensor: i-frame word 0xCA30C (u16) still fires when a hit
    lands even with HP frozen -> per-chunk hit markers + screenshots
    = enemy-fire map.
  * Stall ladder: L1 jump, L2 grenade, L3 unstick, L4/L5 UP+Y anti-air
    bursts (helicopter flies above), L6 stop.
  * Rolling deep checkpoint every 40 chunks (savestate cp_deep).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
from PIL import Image                                     # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from ps1play.telemetry import TelemetryAdapter, JsonlTrace  # noqa: E402
from ps1play.agent.cheatprof import (                     # noqa: E402
    CheatSession, CHEAT_ASSISTED)
from ps1play.agent.gameshark import GSCode                # noqa: E402
from ps1play.agent.perception import PerceptionGuard      # noqa: E402
from ps1play.agent.route import RoutePolicy               # noqa: E402
from mission import ensure_mission                        # noqa: E402
from issue4_controller import boot                        # noqa: E402
from run_mission1_legit import recover_v2                 # noqa: E402
from validate_inv2 import PAIR, FLAGS, read_flags, freeze_test  # noqa

IFRAME = 0xCA30C            # u16 damage-window word (partial gate)
PER_LIFE = 0xCA2E0          # u16 per-life accumulator: RESETS ON DEATH
                            # (Issue #3 anchor) — the death sensor
BOMBS_PATCH = "800398BE 2400"
CHUNK = 60


def _log(*a):
    print("[explore-inv]", *a, file=sys.stderr, flush=True)


def shot(p, outdir, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(outdir, name))


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--opt-in", action="store_true",
                    help="explicit consent for CHEAT_ASSISTED_EXPLORATION")
    ap.add_argument("--chunks", type=int, default=500)
    ap.add_argument("--minutes", type=float, default=40.0)
    ap.add_argument("--tag", default="inv1")
    ap.add_argument("--resume", default=None,
                    help="evidence dir of the run to resume (loads "
                         "cp_deep + runstate.json; no re-anchoring)")
    ap.add_argument("--evidence-dir", default=None)
    a = ap.parse_args(argv)
    if not a.opt_in:
        ap.error("--opt-in required: this run uses VERIFIED cheats and "
                 "is never reportable as a no-cheat clear")
    if a.resume:
        a.evidence_dir = a.resume
    elif a.evidence_dir is None:
        base = labconfig.resolve_path("evidence_dir") or os.path.join(
            _REPO, "evidence_local")
        a.evidence_dir = os.path.join(
            base,
            f"explore_invuln_{a.tag}_{time.strftime('%Y%m%d_%H%M%S')}")
    return a


def confirm_pair(p, danger_f=480):
    """No-cheat confirmation that the candidate HP pair (0xCA2F6/0xCA2FE)
    still co-drops on hits THIS boot. Returns (codrops, trajectory).
    A co-drop = BOTH words strictly decreased in the same frame."""
    p.load_state("cb")
    p.core.run(10, set())
    from validate_inv2 import danger_walk
    danger_walk(p)
    prev = (int(p.mem.u16(PAIR[0])), int(p.mem.u16(PAIR[1])))
    codrops = 0
    traj = []
    for _ in range(danger_f):
        p.core.run_frame()
        pr = (int(p.mem.u16(PAIR[0])), int(p.mem.u16(PAIR[1])))
        if pr[0] < prev[0] and pr[1] < prev[1]:
            codrops += 1
        traj.append(pr)
        prev = pr
    p._advance()
    return codrops, traj


def _save_runstate(rs_path, chunk, total, hp_pair, max_score, hits,
                   deaths, stop, pit_mode=False):
    with open(rs_path, "w") as f:
        json.dump({"chunk": chunk, "chunks_target": total,
                   "hp_pair": hp_pair, "max_score": max_score,
                   "hits": hits[-80:], "deaths_unexpected": deaths,
                   "stop": stop, "pit_mode": pit_mode,
                   "t": time.strftime("%Y-%m-%d %H:%M:%S")},
                  f, indent=1)


def run_segment_frames(p, session, segs, pit_mode):
    """Execute policy segments per-frame with GS tick. In pit_mode the
    advance is overridden with a hazard cadence: RIGHT held, B tap
    every 30f for 8f (water channels kill instantly and HP-freeze
    cannot help), plus UP+Y anti-air bursts every 45f (the village
    flyer/helicopter drones hover above)."""
    for s in segs:
        btns = set(s["btns"] or set()) or None
        n = s["frames"]
        if pit_mode:
            base = ({"RIGHT"} | (btns or set())) if btns else {"RIGHT"}
            for i in range(n):
                b = set(base)
                if (i % 30) < 8:
                    b.add("B")
                if (i % 45) < 12:
                    b |= {"UP", "Y"}
                p.core.run_frame()
                p.core.set_buttons(b)
                session.gs.tick()
            p.core.set_buttons(set())
        else:
            for _ in range(n):
                p.core.run_frame()
                session.gs.tick()


def main():
    args = parse_args()
    os.makedirs(args.evidence_dir, exist_ok=True)
    t0 = time.time()
    budget_s = args.minutes * 60.0
    rs_path = os.path.join(args.evidence_dir, "runstate.json")
    trace = JsonlTrace(os.path.join(args.evidence_dir, "trace.jsonl"))

    p, fwmode = boot()

    if args.resume:
        rs = json.load(open(rs_path))
        trace.write({"type": "resume", "from_chunk": rs["chunk"],
                     "hp_pair": rs["hp_pair"], "disclosed": True})
        _log(f"resume from chunk {rs['chunk']} pair {rs['hp_pair']}")
        p.load_state("cp_deep")
        g = ensure_mission(p, tries=4, log=_log, want_hp_cands=False)
        if not g.get("in_mission") or read_flags(p) != 0xFF:
            sys.exit("!! cp_deep reload did not reach gameplay")
        f6, fe = rs["hp_pair"]
        codes = [GSCode(f"8{PAIR[0]:07X} {f6 & 0xFFFF:04X}"),
                 GSCode(f"8{PAIR[1]:07X} {fe & 0xFFFF:04X}"),
                 GSCode(BOMBS_PATCH)]
        session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
        session.enable("invuln_explore", codes)
        for _ in range(2):
            p.core.run_frame()
            session.gs.tick()
        trace.write({"type": "cheats_enabled", "codes":
                     [c.raw for c in codes], "hp_pair": [f6, fe],
                     "disclosed": True, "note": "resumed lineage"})
        start_chunk = rs["chunk"] + 1
        total_chunks = max(rs.get("chunks_target", 0),
                           start_chunk + 150)   # each resume extends
        c = start_chunk - 1
        max_score = rs.get("max_score", 0)
        hits = rs.get("hits", [])
        deaths = 0            # per-segment stop counter (history in trace)
        sensor_deaths = rs.get("sensor_deaths", 0)
        clean_streak = 0
        pit_mode = rs.get("pit_mode", True)
        dead_recently = 0
        static_streak = 0
        pl_death_ref = int(p.mem.u16(PER_LIFE))
        ladder = 0
        stalled_streak = 0
        stop = None
        policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
        tel = TelemetryAdapter(p)
        prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
        churn_prev = p.mem.snapshot()
    else:
        g = ensure_mission(p, tries=6, log=_log, want_hp_cands=False)
        if not g.get("in_mission"):
            sys.exit("!! mission gate failed")
        _log("in mission")
        trace.write({"type": "run_start", "label": args.tag,
                     "profile": CHEAT_ASSISTED, "opt_in": True,
                     "game": p.game, "core": p.core_path,
                     "t": time.strftime("%Y-%m-%d %H:%M:%S")})

    # ---- anchors (each its own event test) — fresh runs only ----
    if not args.resume:
        session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
        guard = PerceptionGuard(p)
        anch = guard.anchor(log=_log)
        if not anch.get("ok"):
            sys.exit("!! bombs anchor failed")
        trace.write({"type": "anchor", "role": "bombs",
                     "addr": hex(guard.addrs["bombs"]),
                     "series": anch.get("series")})
        p.save_state("cb")

    v0 = (int(p.mem.u16(PAIR[0])), int(p.mem.u16(PAIR[1])))
    codrops = 0
    traj = []
    trial = trial_ok = None
    if not args.resume:
        if v0[0] < 50 or v0[1] < 50:
            sys.exit(f"!! pair words look wrong at cb: {v0}")
        _log("confirming HP pair co-drop on hits (no cheats) ...")
        codrops, traj = confirm_pair(p)
        trace.write({"type": "anchor", "role": "hp_pair",
                     "pair": [hex(a) for a in PAIR], "codrops": codrops,
                     "traj_head": traj[:10], "traj_tail": traj[-10:]})
        if codrops < 3:
            sys.exit(f"!! HP pair co-drop not reproduced this boot "
                     f"(codrops={codrops}) — refusing to freeze")
        _log(f"pair co-drop confirmed ({codrops}x); freeze trial ...")
        trial, trial_ok = freeze_test(p, session, list(PAIR), tag="pair")
        trace.write({"type": "freeze_trial", "role": "hp_pair",
                     "ok": trial_ok,
                     "control": {k: trial["control"][k]
                                 for k in ("held", "alive",
                                           "pair0", "pair1")},
                     "treatment": {k: trial["treatment"][k]
                                   for k in ("held", "alive", "pair0",
                                             "pair1", "codes")}})
        if not trial_ok:
            sys.exit("!! pair freeze trial failed (control/treatment) — "
                     "refusing exploration with unverified freeze")
        _log("freeze trial PASSED (control damaged, treatment held+alive)")

    # ---- engage cheats from the clean cb state (fresh runs only) ----
    if not args.resume:
        p.load_state("cb")
        p.core.run(10, set())
        f6 = int(p.mem.u16(PAIR[0]))
        fe = int(p.mem.u16(PAIR[1]))
        codes = [GSCode(f"8{PAIR[0]:07X} {f6 & 0xFFFF:04X}"),
                 GSCode(f"8{PAIR[1]:07X} {fe & 0xFFFF:04X}"),
                 GSCode(BOMBS_PATCH)]
        session.enable("invuln_explore", codes)
        for _ in range(2):                   # hardware-GS pre-engage
            p.core.run_frame()
            session.gs.tick()
        trace.write({"type": "cheats_enabled",
                     "codes": [c.raw for c in codes],
                     "hp_pair": [f6, fe], "disclosed": True,
                     "note": "exploration-only; never a no-cheat clear"})
        _log(f"cheats ON: pair {f6}/{fe} frozen + bombs patch")

    # ---- exploration loop ----
    if not args.resume:
        tel = TelemetryAdapter(p)
        policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
        prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
        max_score = prev["score"]
        ladder = 0
        stalled_streak = 0
        hits = []
        deaths = 0
        sensor_deaths = 0
        clean_streak = 0
        pit_mode = bool(getattr(args, "pit_mode", False))
        dead_recently = 0
        static_streak = 0
        pl_death_ref = int(p.mem.u16(PER_LIFE))
        stop = None
        start_chunk = 0
        c = start_chunk - 1
        total_chunks = args.chunks
        p.save_state("cp_safe")
        p.save_state("cp_deep")
        churn_prev = p.mem.snapshot()
        _save_runstate(rs_path, start_chunk, total_chunks, [f6, fe],
                       max_score, hits, deaths, stop, pit_mode)
    for c in range(start_chunk, total_chunks):
        if stop:
            break
        if time.time() - t0 > budget_s - 90:
            stop = "BUDGET_TIME"
            break
        # per-frame run + per-frame GS tick (hardware-faithful)
        run_segment_frames(p, session, policy.decide(CHUNK, None),
                           pit_mode)
        cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
        churn = int(np.count_nonzero(p.mem.snapshot() != churn_prev))
        churn_prev = p.mem.snapshot()
        ifr = int(p.mem.u16(IFRAME))
        pl_now = int(p.mem.u16(PER_LIFE))
        pair_now = (int(p.mem.u16(PAIR[0])), int(p.mem.u16(PAIR[1])))
        cheats_active = pair_now == (f6, fe)
        max_score = max(max_score, cur["score"])
        evs = tel.events(prev, cur)
        for e in evs:
            trace.write({"type": "event", "chunk": c, **e})
        if ifr > 0:
            hits.append({"chunk": c, "iframe": ifr,
                         "camera_fx": cur["camera_fx"],
                         "score": cur["score"]})
            if len(hits) % 5 == 1:
                shot(p, args.evidence_dir, f"hit_c{c:03d}.png")
        # ---- death sensor: per-life accumulator reset ----
        # (per_life resets on death per Issue #3; under HP-freeze there
        # is no damage, so a reset is a REAL death — counted for
        # disclosure and pit-avoidance, NOT as a fatal stop)
        death_now = (pl_death_ref - pl_now) > 30 or (
            pl_now < 30 and pl_death_ref > 100)
        if death_now:
            sensor_deaths += 1
            pit_mode = True
            dead_recently = 10
            clean_streak = 0
            static_streak = 0
            trace.write({"type": "death_detected", "chunk": c,
                         "attempt": sensor_deaths,
                         "sensor": "per_life_reset",
                         "per_life": [pl_death_ref, pl_now],
                         "pit_mode": True, "disclosed": True})
        else:
            clean_streak += 1
            if clean_streak > 40 and pit_mode:
                pit_mode = False
                trace.write({"type": "pit_mode_off", "chunk": c,
                             "clean_streak": clean_streak})
        pl_death_ref = pl_now
        # ---- CONTINUE-countdown rescue: static screen + flags 255
        #      = countdown overlay (game over with 0 lives shows it
        #      BEFORE the flags flip); START accepts the continue ----
        if death_now or (cur["flags_word"] == 0xFF and churn < 60):
            static_streak = static_streak + 1 if churn < 60 else 0
        else:
            static_streak = 0
        if static_streak >= 4:
            trace.write({"type": "continue_rescue", "chunk": c,
                         "static_streak": static_streak,
                         "action": "START tap", "disclosed": True})
            p.core.run(8, {"START"})
            for _ in range(8):
                p.core.run_frame()
                session.gs.tick()
            static_streak = 0
            prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
        if dead_recently > 0:
            dead_recently -= 1
        trace.write({"type": "chunk", "chunk": c, "telemetry": cur,
                     "iframe": ifr, "hp_pair": list(pair_now),
                     "per_life": pl_now, "cheats_active": cheats_active,
                     "churn": churn, "pit_mode": pit_mode,
                     "sensor_deaths": sensor_deaths,
                     "policy_stats": dict(policy.stats)})
        if not cheats_active:
            stop = "STOP_CHEAT_LOST"
            trace.write({"type": "stop", "chunk": c, "reason": stop,
                         "telemetry": cur})
            break
        # ---- stall ladder (movement evidence: churn/score/camera) ----
        cam_gain = cur["camera_fx"] - prev["camera_fx"]
        score_gain = cur["score"] - prev["score"]
        stalled = churn < 250 and score_gain <= 0 and cam_gain <= 0
        stalled_streak = 0 if not stalled else stalled_streak + 1
        if stalled_streak >= 8:
            ladder += 1
            stalled_streak = 0
            if ladder == 1:
                trace.write({"type": "stall_l1_jump", "chunk": c})
                p.core.run(20, {"RIGHT"})
                p.core.run(40, {"RIGHT", "B"})
            elif ladder == 2:
                trace.write({"type": "stall_l2_grenade", "chunk": c,
                             "grenades": cur["grenades"]})
                p.core.run(8, set())
                p.core.run(30, {"A"})
                p.core.run(30, {"RIGHT", "Y"})
            elif ladder == 3:
                trace.write({"type": "stall_l3_unstick", "chunk": c})
                p.core.run(60, {"LEFT", "Y"})
                p.core.run(120, {"RIGHT", "Y"})
            elif ladder in (4, 5):
                # anti-air: the helicopter boss flies above — UP+Y burst
                trace.write({"type": "stall_antiair", "chunk": c,
                             "level": ladder})
                p.core.run(90 if ladder == 4 else 180, {"UP", "Y"})
                p.core.run(60, {"RIGHT", "Y"})
            else:
                stop = f"STOP_STALLED chunk={c}"
                trace.write({"type": "stop", "chunk": c, "reason": stop,
                             "telemetry": cur})
                break
            for _ in range(30):              # keep GS alive in ladders
                p.core.run_frame()
                session.gs.tick()
            prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
            continue
        # ---- death safety net ----
        # pit_mode engages after ANY death: instant-death hazards (water
        # channels / pits) bypass HP entirely, so the freeze cannot stop
        # them — only jumping does. Instant-death signature = death with
        # no recent i-frame hits (hits list tail).
        if cur["flags_word"] != 0xFF:
            deaths += 1
            recent_hits = [h for h in hits[-10:]
                           if h["chunk"] >= c - 12]
            sig = ("damage" if recent_hits else "instant_pit")
            pit_mode = True
            trace.write({"type": "death_unexpected", "chunk": c,
                         "attempt": deaths, "signature": sig,
                         "disclosed": True})
            if deaths > 6:
                stop = "STOP_DEAD_LOOP"
                break
            # 1) in-place recovery
            recover_v2(p, log=_log)
            g = ensure_mission(p, tries=4, log=_log, want_hp_cands=False)
            if g.get("in_mission") and read_flags(p) == 0xFF:
                prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
                continue
            # 2) bounded CONTINUE accept (disclosed; the SLUS port sits
            #    on CONTINUE? countdown after GAME OVER)
            okc = False
            for i in range(10):
                p.core.run(130, set())
                for btn in ({"START"}, {"Y"}):
                    p.core.run(8, btn)
                    p.core.run(100, set())
                    for _ in range(2):
                        p.core.run_frame()
                        session.gs.tick()
                    if read_flags(p) == 0xFF:
                        okc = True
                        break
                if okc:
                    break
            trace.write({"type": "continue_attempt", "chunk": c,
                         "accepted": okc, "disclosed": True})
            if okc:
                prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
                continue
            # 3) checkpoint reload (deep, then safe)
            reloaded = False
            for st in ("cp_deep", "cp_safe"):
                try:
                    p.load_state(st)
                    g = ensure_mission(p, tries=3, log=_log,
                                       want_hp_cands=False)
                    if read_flags(p) == 0xFF:
                        trace.write({"type": "checkpoint_reload",
                                     "chunk": c, "state": st})
                        reloaded = True
                        break
                except Exception as e:                    # noqa: BLE001
                    trace.write({"type": "checkpoint_reload_failed",
                                 "chunk": c, "state": st,
                                 "err": repr(e)[:120]})
            if not reloaded:
                stop = "STOP_RECOVER_FAILED"
                trace.write({"type": "stop", "chunk": c, "reason": stop})
                break
            prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
            continue
        # ---- checkpoints + progress shots ----
        if c % 40 == 39 and dead_recently == 0:
            try:
                p.save_state("cp_deep")
                _save_runstate(rs_path, c, total_chunks, [f6, fe],
                               max_score, hits, deaths, stop, pit_mode)
                trace.write({"type": "checkpoint_saved", "chunk": c,
                             "state": "cp_deep", "pit_mode": pit_mode})
            except Exception as e:                        # noqa: BLE001
                trace.write({"type": "checkpoint_save_failed",
                             "chunk": c, "err": repr(e)[:150]})
        if c % 25 == 0:
            shot(p, args.evidence_dir, f"progress_c{c:03d}.png")
        prev = cur

    report = {
        "label": args.tag, "profile": CHEAT_ASSISTED,
        "chunks_run": c + 1 if c >= 0 else 0,
        "stop_reason": stop or "BUDGET_END",
        "deaths_unexpected": deaths,
        "max_score": max_score,
        "hits_total": len(hits),
        "hits": hits[:80],
        "cheats": [x.raw for x in codes],
        "hp_pair_frozen": [f6, fe],
        "disclosure": "CHEAT_ASSISTED_EXPLORATION run — never a "
                      "no-cheat clear; survival via VERIFIED data-freeze "
                      "codes (hp_pair_freeze + bombs patch)",
        "final": prev,
    }
    trace.write({"type": "run_end", **report})
    with open(os.path.join(args.evidence_dir, "report.json"), "w") as f:
        json.dump(report, f, indent=1, default=str)
    shot(p, args.evidence_dir, "final.png")
    session.disable_all()
    _log("report:", os.path.join(args.evidence_dir, "report.json"))
    _log("stop:", report["stop_reason"], "chunks:", report["chunks_run"],
         "max_score:", max_score, "hits:", len(hits))


if __name__ == "__main__":
    main()
