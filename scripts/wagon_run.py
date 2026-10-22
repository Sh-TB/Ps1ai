#!/usr/bin/env python3
"""wagon_run.py — Issue #7 T7: live Mission-1 runs with the wagon
sensor.  Counts wagons crossed (train-section entities that spawn from
the right and despawn behind the player), with honest per-run
disclosure.

Modes
  nocheat  — the proven Issue-5 v1 cadence + controller layer
             (RoutePolicy v1, recover_v2, flags-gate, savestate mission
             restarts — every restart disclosed).  No RAM writes.
  explore  — CHEAT_ASSISTED_EXPLORATION: the Issue-5 VERIFIED
             hp_pair freeze (0x800CA2F6/0x800CA2FE, boot-derived
             values) so the enemy-dense train/POW ride can be crossed
             long enough to enumerate wagons.  Never a no-cheat clear;
             every record carries mode=CHEAT_ASSISTED_EXPLORATION.

Both modes share the WagonSensor (ps1play/agent/wagon.py): entity-table
lifecycle events + full slot dumps at spawns, PNG at first sightings
for offline small/big labeling.
"""
from __future__ import annotations

import argparse
import base64
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
from ps1play.agent.route import RoutePolicy, StallDetector  # noqa: E402
from ps1play.agent.wagon import WagonSensor               # noqa: E402
from mission import ensure_mission                        # noqa: E402
from run_mission1_legit import recover_v2                 # noqa: E402
from issue4_controller import boot                        # noqa: E402
from issue5_controller import (                           # noqa: E402
    ContinueLedger, savestate_recover)

PAIR = (0xCA2F6, 0xCA2FE)          # VERIFIED player-HP pair (#5 A/B)
PAIR_VA = (0x800CA2F6, 0x800CA2FE)
FIRE_HELD_ADVANCE = False          # reverted variable (#5 A/B evidence)
STALL_CHUNKS = 6
STARTUP_GRACE = 6
PNG_PER_FP = 2
PNG_CAP = 80
# Proven pit/hazard cadence (issue5_explore_invuln inv20: 500 chunks,
# 0 HP loss): RIGHT held + B taps (water channels kill instantly; the
# HP freeze cannot help) + UP+Y anti-air bursts (village flyer drones).
PIT_B_PERIOD = 30
PIT_B_LEN = 8
PIT_AA_PERIOD = 45
PIT_AA_LEN = 12


_SENSOR = {}
_TEL = {}


def _log(*a):
    print("[wagon]", *a, file=sys.stderr, flush=True)


def gs_run(p, session, frames, buttons, sensor, out, phase=0,
           pit_mode=False):
    """Run frames with buttons latched; GameShark ticked each frame
    (explore mode); wagon sensor polled (internal `every` limiter).
    pit_mode overlays the proven hazard cadence on the GLOBAL phase
    (chunk partitioning must not change the schedule — inv20)."""
    base = set(buttons) if buttons else set()
    for i in range(frames):
        if pit_mode:
            b = set(base | {"RIGHT"}) if base else {"RIGHT"}
            g = phase + i
            if (g % PIT_B_PERIOD) < PIT_B_LEN:
                b.add("B")
            if (g % PIT_AA_PERIOD) < PIT_AA_LEN:
                b |= {"UP", "Y"}
            p.core.set_buttons(b)
        else:
            p.core.set_buttons(base)
        p.core.run_frame()
        if session is not None:
            session.gs.tick()
        fc = p.core.frames_run
        for ev in sensor.poll(fc):          # internal `every` limiter
            out["events"].append(ev)
            if ev["type"] == "spawn":
                _maybe_png(p, out, ev, fc)
    return phase + frames


def _maybe_png(p, out, ev, fc):
    fp = ev["fp"]
    n = out["fp_png"].get(fp, 0)
    if n >= PNG_PER_FP or out["png_total"] >= PNG_CAP:
        return
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(
            out["dir"], f"spawn_{ev['slot']:02d}_{fp}_{fc:06d}.png"))
        out["fp_png"][fp] = n + 1
        out["png_total"] += 1



def continue_rescue(p, trace, chunk, rounds=8, threshold=120):
    """Accept the in-game CONTINUE countdown (legal in-game option).

    Evidence chain: issue4 progress_c200 (CONTINUE screen accepted via
    START taps -> checkpoint respawn with fresh timer + lives) and the
    proven rescue in issue5_explore_invuln (static screen + START tap).
    The Task-13 probe showed the POST-menu flow accepts nothing; the
    countdown overlay is the only interactive continue.  Every accepted
    continue is counted + disclosed by the caller."""
    prev_snap = p.mem.snapshot()
    for i in range(rounds):
        p.core.run(130, set())               # settle through the fade
        p.core.run(8, {"START"})
        p.core.run(100, set())
        for ev in _SENSOR.get("poll", lambda fc: [])(p.core.frames_run):
            pass
        cur_snap = p.mem.snapshot()
        churn = int(np.count_nonzero(np.frombuffer(
            prev_snap, np.uint8) != np.frombuffer(cur_snap, np.uint8)))
        prev_snap = cur_snap
        cur = _TEL["snapshot"](buttons=[], frame=p.core.frames_run)
        if churn > threshold and cur["flags_word"] == 0xFF:
            trace.write({"type": "continue_accepted", "chunk": chunk,
                         "round": i + 1, "disclosed": True,
                         "method": "countdown_start_tap"})
            return True
    trace.write({"type": "continue_rescue_failed", "chunk": chunk,
                 "rounds": rounds})
    return False

def run_chunks(p, chunks, trace, label, outdir, mode, budget_min,
               session=None):
    tel = TelemetryAdapter(p)
    policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()
    ledger = ContinueLedger()
    sensor = WagonSensor(p.mem.ram, every=10)
    _SENSOR["poll"] = lambda fc: sensor.poll(fc)
    _TEL["snap"] = tel
    _TEL["snapshot"] = tel.snapshot
    out = {"dir": outdir, "events": [], "fp_png": {}, "png_total": 0}
    t0 = time.time()
    stop = None
    deaths = 0
    max_score = 0
    prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
    trace.write({"type": "run_start", "label": label, "mode": mode,
                 "start": prev})
    try:
        p.save_state("wagon_m1_start")
        trace.write({"type": "checkpoint_saved", "state": "wagon_m1_start"})
    except Exception as e:                     # noqa: BLE001
        trace.write({"type": "checkpoint_save_failed", "err": repr(e)[:200]})
    stall_streak = ladder = 0
    explore_restarts = 0
    rgb_prev = p.core.frame_rgb()
    phase = 0
    c = -1
    for c in range(chunks):
        if time.time() - t0 > budget_min * 60:
            stop = "BUDGET_TIME"
            break
        segs = policy.decide(60, det)
        for s in segs:
            btns = set(s["btns"] or set())
            if FIRE_HELD_ADVANCE and "RIGHT" in btns:
                btns.add("Y")
            if session is not None:
                # explore: proven pit-cadence overlay on global phase
                phase = gs_run(p, session, s["frames"], btns, sensor,
                               out, phase=phase, pit_mode=True)
            else:
                p.core.run(s["frames"], btns if btns else None)
                fc = p.core.frames_run
                for ev in sensor.poll(fc):   # internal `every` limiter
                    out["events"].append(ev)
                    if ev["type"] == "spawn":
                        _maybe_png(p, out, ev, fc)
        cur = tel.snapshot(buttons=sorted(set().union(
            *[s["btns"] or set() for s in segs])),
            frame=p.core.frames_run)
        rgb_now = p.core.frame_rgb()
        churn_px = None
        if rgb_prev is not None and rgb_now is not None:
            churn_px = round(float(np.abs(
                rgb_prev.astype(np.int16) -
                rgb_now.astype(np.int16)).mean()), 3)
        rgb_prev = rgb_now
        max_score = max(max_score, cur["score"])
        trace.write({"type": "chunk", "chunk": c, "telemetry": cur,
                     "churn_px": churn_px,
                     "spawns_so_far": len(sensor.spawns)})
        # ---- out-of-gameplay / death handling ----
        game_over = cur["flags_word"] == 0x1
        death_evt = cur["score"] < prev["score"] - 200
        if game_over or death_evt:
            deaths += 1
            trace.write({"type": "death_recovery", "chunk": c,
                         "attempt": deaths,
                         "trigger": "game_over_screen" if game_over
                         else "score_collapse"})
            if session is not None:
                # explore: HP freeze active; deaths are instant-death
                # paths (pits) or lives exhaustion.  Lives-remaining
                # deaths respawn automatically (no savestate loads
                # mid-run — inv13/14 lesson).
                if not game_over:
                    if deaths > 24:
                        stop = "STOP_DEAD_LOOP_EXPLORE"
                        break
                    trace.write({"type": "checkpoint_respawn", "chunk": c,
                                 "disclosed": True})
                    det.reset()
                    prev = tel.snapshot(buttons=[],
                                        frame=p.core.frames_run)
                    rgb_prev = p.core.frame_rgb()
                    continue
                # CONTINUE countdown first: the interactive continue
                # (START on the countdown overlay) respawns Marco at
                # the game's own CHECKPOINT with a fresh timer+lives
                # (issue4 progress_c200 evidence).  Every acceptance is
                # counted + disclosed.  Only a missed countdown falls
                # back to the savestate mission restart.
                if continue_rescue(p, trace, c):
                    ledger.on_continue_restart()
                    det.reset()
                    prev = tel.snapshot(buttons=[],
                                        frame=p.core.frames_run)
                    rgb_prev = p.core.frame_rgb()
                    continue
                if explore_restarts < 3:
                    ok = savestate_recover(p, tel, trace, c, ledger,
                                           outdir)
                    if ok:
                        explore_restarts += 1
                        det.reset()
                        prev = tel.snapshot(
                            buttons=[], frame=p.core.frames_run)
                        rgb_prev = p.core.frame_rgb()
                        continue
                stop = "STOP_GAMEOVER_EXPLORE"
                break
            # nocheat: the proven controller layer (issue5_controller)
            ledger.observe(prev["score"])
            if deaths > 12:
                stop = "STOP_DEAD_LOOP"
                break
            if not game_over:
                recover_v2(p, log=_log)
            g = ensure_mission(p, tries=4, log=_log,
                               want_hp_cands=False)
            after = tel.snapshot(buttons=[], frame=p.core.frames_run)
            if g.get("in_mission") and after["flags_word"] == 0xFF:
                det.reset()
                prev = after
                rgb_prev = p.core.frame_rgb()
                continue
            ok = savestate_recover(p, tel, trace, c, ledger, outdir)
            if not ok:
                stop = "STOP_RESTART_FAILED"
                break
            over, reason = ledger.should_stop()
            if over:
                stop = reason
                break
            det.reset()
            prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
            rgb_prev = p.core.frame_rgb()
            continue
        prev = cur
        # ---- stall ladder (pixel churn) ----
        in_grace = c < STARTUP_GRACE
        stalled = churn_px is not None and churn_px < 3.0
        stall_streak = 0 if (not stalled or in_grace) else \
            stall_streak + 1
        if not stalled:
            ladder = 0
        if stall_streak >= STALL_CHUNKS:
            ladder += 1
            stall_streak = 0
            if ladder == 1:
                if session is not None:
                    # arena gate: sustained anti-air vulcan fire (the
                    # chopper squad falls with its red leader — AQM)
                    gs_run(p, session, 120, {"UP", "Y"}, sensor, out,
                           phase=phase, pit_mode=True)
                else:
                    p.core.run(20, {"RIGHT"})
                    p.core.run(40, {"RIGHT", "B"})
            elif ladder == 2:
                if cur["grenades"] > 0:
                    if session is not None:
                        gs_run(p, session, 8, set(), sensor, out,
                               phase=phase)
                        gs_run(p, session, 30, {"A"}, sensor, out,
                               phase=phase)
                    else:
                        p.core.run(8, set())
                        p.core.run(30, {"A"})
                if session is not None:
                    gs_run(p, session, 60, {"UP", "Y"}, sensor, out,
                           phase=phase, pit_mode=True)
                else:
                    p.core.run(30, {"RIGHT", "Y"})
            elif ladder == 3:
                if session is not None:
                    gs_run(p, session, 60, {"LEFT", "Y"}, sensor, out)
                    gs_run(p, session, 120, {"RIGHT", "Y"}, sensor, out)
                else:
                    p.core.run(60, {"LEFT", "Y"})
                    p.core.run(120, {"RIGHT", "Y"})
            else:
                stop = f"STOP_STALLED chunk={c}"
                break
            det.reset()
            prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
            rgb_prev = p.core.frame_rgb()
            continue
        if c % 50 == 0:
            rgb = p.core.frame_rgb()
            if rgb is not None:
                Image.fromarray(rgb).save(os.path.join(
                    outdir, f"progress_c{c:03d}.png"))
    summ = sensor.summary()
    report = {
        "schema": "ps1play-wagon-run/1",
        "label": label,
        "mode": mode,
        "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
        "chunks_run": c + 1 if c >= 0 else 0,
        "stop_reason": stop or "BUDGET_CHUNKS",
        "deaths": deaths,
        "restarts": ledger.continues,
        "explore_mission_restarts": explore_restarts,
        "max_score": max_score,
        "wallclock_s": round(time.time() - t0, 1),
        "disclosed": {
            "mode": mode,
            "hp_pair_freeze": mode == "explore",
            "pair_va": [hex(a) for a in PAIR_VA],
            "note": ("explore mode uses the Issue-5 VERIFIED hp_pair "
                     "freeze; counts from it are exploration evidence, "
                     "never a no-cheat clear") if mode == "explore"
            else "no RAM writes, no cheats",
        },
        "sensor": summ,
    }
    trace.write({"type": "run_end", **{k: v for k, v in report.items()
                                       if k != "sensor"}})
    json.dump(report, open(os.path.join(outdir,
                                        "wagon_report.json"), "w"),
              indent=1)
    json.dump(out["events"], open(os.path.join(outdir,
                                               "wagon_events.json"), "w"))
    _log("report:", json.dumps({k: report[k] for k in
                                ("label", "mode", "chunks_run",
                                 "stop_reason", "max_score")}))

    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("nocheat", "explore"),
                    default="nocheat")
    ap.add_argument("--chunks", type=int, default=400)
    ap.add_argument("--budget-min", type=float, default=55.0)
    ap.add_argument("--tag", default="noc1")
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir,
                          f"issue7_wagon_{args.tag}")
    os.makedirs(outdir, exist_ok=True)
    _log("boot (fresh process; second in-process boot SEGFAULTs)")
    p, fwmode = boot()
    _log("fw:", fwmode)
    trace = JsonlTrace(os.path.join(outdir, "trace.jsonl"))
    # gate into mission with the proven navigator
    g = ensure_mission(p, tries=6, log=_log, want_hp_cands=False)
    _log("mission gate:", g.get("in_mission"))
    trace.write({"type": "boot", "fw": fwmode,
                 "in_mission": bool(g.get("in_mission"))})
    if args.mode == "explore":
        session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
        # boot-derived freeze values, captured in real play
        v0 = int(p.mem.u16(PAIR[0]))
        v1 = int(p.mem.u16(PAIR[1]))
        codes = [GSCode(f"8{PAIR[0]:07X} {v0 & 0xFFFF:04X}"),
                 GSCode(f"8{PAIR[1]:07X} {v1 & 0xFFFF:04X}")]
        session.enable("hp_pair_freeze_wagon", codes)
        trace.write({"type": "cheat_enabled", "disclosed": True,
                     "codes": [c.raw for c in codes],
                     "mode": "CHEAT_ASSISTED_EXPLORATION"})
        _log("hp_pair freeze:", [c.raw for c in codes])
    else:
        session = None
    report = run_chunks(p, args.chunks, trace, args.tag, outdir,
                        args.mode, args.budget_min, session=session)
    trace.close() if hasattr(trace, "close") else None
    print(json.dumps({k: report[k] for k in
                      ("label", "mode", "chunks_run", "stop_reason",
                       "deaths", "max_score")}, indent=1))


if __name__ == "__main__":
    main()
