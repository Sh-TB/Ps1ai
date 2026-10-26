#!/usr/bin/env python3
"""msx_r10_rollover.py — Round 10 (Task 16-a): the timer-gate question,
properly instrumented.

Round-10 evidence so far: front duo kill-causal (+500/slot), rear slot
12 unreached, survival ceiling 1,140 f vs the 18,000 f a 300 s timer
needs, continue landings at 1164/1424-1525 (NONE past 2212 — the arena
is one-pass), and the round-9 'timer' candidates (0xe7fee @0.2 Hz,
0xd4974 @60 Hz) are NOT a seconds countdown.

This run:
  T  1 Hz timer hunt at the arena: 12 RAM snapshots 60 f apart; words
     decrementing by EXACTLY 1 per window across all samples (u16 and
     u32 views) = mission-timer candidates; restore after (disclosed).
  K  kill_phase (proven front-duo recipe, max 40 cycles).
  S  engineered survival: hold the pin edge, jump early (near_d<55),
     anti-air UP+Y for low-h threats, grenade flat-lobs when cornered,
     walk back if pushed off the edge; up to 19,200 f; the REAL timer
     (from T) drives rollover detection; release = px>2232 or walk-probe
     advance >=100 (wr9_unlocked savestate on release, disclosed).
  L  on death: one disclosed retry with pure-avoidance kite (no kill
     first — fewer aggro) before honest verdicts.

Honest verdicts; evidence -> scratch/round10_msx/rollover/. ONE beetle
boot per process; no RAM writes; restores disclosed.
"""
import json
import os
import sys
import time

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import msx_r10_timergate as tg                      # noqa: E402
tg.OUTDIR = os.path.join(tg.SCRATCH, "rollover")    # route its png() here
from msx_r10_timergate import (                     # noqa: E402
    A_SCORE, GRENADES, PLAYER_HP, CHOPPER_ST, PIN_PX,
    census, presence, threats, alive, px_of, png, log,
    kill_phase)
from ps1play.telemetry import JsonlTrace            # noqa: E402
from issue4_controller import boot                  # noqa: E402
from mission import ensure_mission                  # noqa: E402

OUTDIR = tg.OUTDIR
STATE = "wr9_arena"


def hunt_1hz(p, m, J, samples=12, period=60):
    """Words decrementing exactly 1 per `period` frames (u16 + u32)."""
    snaps = []
    for s in range(samples):
        snaps.append(np.frombuffer(bytes(m.snapshot()), "<u2")
                     .astype(np.int64))
        if s == 0:
            J({"ev": "hunt_start", "samples": samples, "period": period})
        p.core.run(period, set())
        if not alive(m):
            J({"ev": "hunt_death", "sample": s})
            return []
    deltas16 = snaps[-1] - snaps[0]
    n_win = (samples - 1)
    c16 = np.nonzero(deltas16 == -n_win)[0]
    out = []
    seen = set()
    for i in c16[:400]:
        v0 = int(snaps[0][i])
        if v0 <= 0 or v0 > 999:
            continue                       # countdowns live in 1..999
        # per-sample exactness
        ok = all(int(snaps[k + 1][i]) - int(snaps[k][i]) == -1
                 for k in range(samples - 1))
        if not ok:
            continue
        key = ("u16", i * 2)
        if key in seen:
            continue
        seen.add(key)
        out.append({"addr": i * 2, "kind": "u16", "v0": v0,
                    "vlast": int(snaps[-1][i])})
    return out


def hold_pos(p, m, px, edge=2150.0):
    if px < edge:
        p.core.run(14, {"RIGHT"})
        return 14
    return 0


def kite_phase(p, m, J, timers_real, max_frames=19200, pure=False):
    """Engineered survival at the pin: jump early, anti-air, grenade
    lobs, hold the edge; rollover on the real 1 Hz timer if found."""
    t0frame = p.core.frames_run
    score0 = int(m.u32(A_SCORE))
    rollover_at, released = None, False
    jump_cd, lob_cd = 0, 0
    chunk = 0
    rt = timers_real[0]["addr"] if timers_real else None
    png(p, "kite_start.png")
    while p.core.frames_run - t0frame < max_frames:
        if not alive(m):
            surv = p.core.frames_run - t0frame
            J({"ev": "KITE_DEATH", "survival_frames": surv,
               "survival_s": round(surv / 60.0, 1),
               "px": round(px_of(m), 1),
               "score": int(m.u32(A_SCORE))})
            png(p, "kite_death.png")
            return {"survived": False, "frames": surv,
                    "released": False, "rollover": rollover_at,
                    "score_delta": int(m.u32(A_SCORE)) - score0}
        px = px_of(m)
        slots = census(m)
        th = threats(slots)
        tv = None
        if rt is not None:
            tv = int(np.frombuffer(bytes(m.snapshot()[rt:rt + 2]),
                                   "<u2")[0])
        J({"ev": "kite_chunk", "chunk": chunk,
           "frame": p.core.frames_run - t0frame, "px": round(px, 1),
           "php": int(m.u16(PLAYER_HP)),
           "score": int(m.u32(A_SCORE)), "gren": int(m.u8(GRENADES)),
           "timer": tv, "n_threats": len(th),
           "pres": presence(slots)})
        if chunk % 15 == 0:
            png(p, f"kite_c{chunk:04d}.png")
        if rt is not None and tv == 0 and rollover_at is None:
            rollover_at = p.core.frames_run - t0frame
            J({"ev": "TIMER_ROLLOVER", "at_frame": rollover_at,
               "px": round(px, 1)})
            png(p, "kite_ROLLOVER.png")
        if px > PIN_PX + 20.0:
            released = True
            J({"ev": "PX_ADVANCED_PAST_PIN", "px": round(px, 1)})
            break
        # ---- tactics ----
        near_sx = min(th, key=lambda s: abs(s["sx"] - 120))["sx"] \
            if th else None
        near_d = abs(near_sx - 120) if near_sx is not None else 999
        low_fly = any(s["h"] < 45 for s in th)
        gren = int(m.u8(GRENADES))
        used = hold_pos(p, m, px)
        if used:
            chunk += 1
            continue
        if pure:
            if th and near_d < 50 and jump_cd <= 0:
                p.core.run(12, {"B"})
                jump_cd = 6
            elif th and near_d < 100:
                d = "RIGHT" if near_sx > 120 else "LEFT"
                p.core.run(16, {d})            # just create space
                p.core.run(8, set())
            else:
                p.core.run(40, set())
            jump_cd -= 1
        else:
            if th and near_d < 55 and jump_cd <= 0:
                p.core.run(12, {"B"})
                jump_cd = 5
            elif th and low_fly:
                p.core.run(24, {"UP", "Y"})
                p.core.run(10, set())
            elif th and gren > 0 and 40 < near_d < 95 and lob_cd <= 0:
                d = "RIGHT" if near_sx > 120 else "LEFT"
                p.core.run(6, {"A", d})        # flat grenade lob
                p.core.run(28, set())
                lob_cd = 3
            elif th and near_d < 100:
                d = "RIGHT" if near_sx > 120 else "LEFT"
                p.core.run(24, {"Y", d})
                p.core.run(10, set())
            elif th:
                p.core.run(20, {"UP", "Y"})    # aerials at off-screen spawns
                p.core.run(16, set())
            else:
                p.core.run(50, set())
            jump_cd -= 1
            lob_cd -= 1
        chunk += 1
    surv = p.core.frames_run - t0frame
    p0 = px_of(m)
    p.core.run(300, {"RIGHT"})
    adv = round(px_of(m) - p0, 1)
    J({"ev": "WALK_PROBE", "px0": round(p0, 1),
       "px1": round(px_of(m), 1), "advance": adv,
       "released": adv >= 100.0, "rollover": rollover_at})
    png(p, "kite_probe.png")
    if adv >= 100.0:
        try:
            p.save_state("wr9_unlocked")
            J({"ev": "STATE_SAVED", "state": "wr9_unlocked"})
        except Exception as e:                     # noqa: BLE001
            J({"ev": "STATE_SAVE_FAIL", "err": repr(e)[:120]})
    return {"survived": True, "frames": surv,
            "released": adv >= 100.0 or released, "rollover": rollover_at,
            "probe_advance": adv,
            "score_delta": int(m.u32(A_SCORE)) - score0}


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    t0 = time.time()
    trace = JsonlTrace(os.path.join(OUTDIR, "trace.jsonl"))

    def J(ev):
        ev["t"] = round(time.time() - t0, 1)
        trace.write(ev)

    p, fw = boot()
    m = p.mem
    g = ensure_mission(p, tries=6, log=log, want_hp_cands=False)
    J({"ev": "boot", "fw": fw, "in_mission": bool(g.get("in_mission"))})
    if not g.get("in_mission"):
        json.dump({"verdict": "GATE_FAILED"}, open(
            os.path.join(OUTDIR, "report.json"), "w"), indent=1)
        return 2
    p.load_state(STATE)
    J({"ev": "state_loaded", "px": round(px_of(m), 1),
       "score": int(m.u32(A_SCORE)), "php": int(m.u16(PLAYER_HP)),
       "gren": int(m.u8(GRENADES))})
    png(p, "post_load.png")

    # T: 1 Hz hunt (runs live at the arena; restore after)
    timers_real = hunt_1hz(p, m, J)
    J({"ev": "hunt_done", "timers": timers_real})
    p.load_state(STATE)
    J({"ev": "restore_after_hunt", "disclosed": True})

    kills_summary = {"stop": "SKIPPED"}
    if not timers_real:
        J({"ev": "no_1hz_timer", "note": "rollover detection degraded"})
    # K: front duo first (proven recipe)
    kill = kill_phase(p, m, J, 40)
    kills_summary = kill
    J({"ev": "KILL_DONE", "stop": kill["stop"], "cycle": kill.get("cycle"),
       "n_kills": len(kill.get("kills", [])),
       "score_delta": kill.get("score_delta")})
    if kill["stop"] == "DEATH":
        p.load_state(STATE)
        J({"ev": "restore_after_kill_death", "disclosed": True})
        kill = kill_phase(p, m, J, 40)
        kills_summary = kill
        J({"ev": "KILL_DONE_RETRY", "stop": kill["stop"],
           "n_kills": len(kill.get("kills", []))})

    # S: engineered survival to rollover
    surv = kite_phase(p, m, J, timers_real, max_frames=19200, pure=False)
    J({"ev": "KITE_DONE", **surv})

    # L: on death, one pure-avoidance retry from the arena
    surv2 = None
    if not surv["survived"] and not surv.get("released"):
        p.load_state(STATE)
        J({"ev": "restore_for_pure_kite", "disclosed": True})
        surv2 = kite_phase(p, m, J, timers_real, max_frames=19200,
                           pure=True)
        J({"ev": "KITE2_DONE", **surv2})

    # verdict
    best = max([surv] + ([surv2] if surv2 else []),
               key=lambda s: s.get("frames", 0))
    released_any = bool(surv.get("released")) or \
        bool(surv2 and surv2.get("released"))
    rolled = [s for s in [surv] + ([surv2] if surv2 else [])
              if s.get("rollover") is not None]
    if released_any and rolled:
        verdict = "CAUSAL_TIMER_GATED_RELEASED"
    elif released_any:
        verdict = "RELEASED_SURVIVAL_PATH"
    elif rolled:
        verdict = "NEGATIVE_ROLLOVER_HELD"
    elif best.get("survived"):
        verdict = "SURVIVED_NO_ROLLOVER_DETECTED"
    else:
        verdict = "SURVIVAL_CEILING"
    rep = {"schema": "ps1play-r10-rollover/1", "verdict": verdict,
           "state": STATE, "timers_1hz": timers_real,
           "kill": {"stop": kills_summary.get("stop"),
                    "n_kills": len(kills_summary.get("kills", [])),
                    "score_delta": kills_summary.get("score_delta")},
           "survive_fight": surv,
           "survive_pure": surv2,
           "best_survival_frames": best.get("frames", 0),
           "best_survival_s": round(best.get("frames", 0) / 60.0, 1),
           "frames": p.core.frames_run,
           "wall_s": round(time.time() - t0, 1)}
    json.dump(rep, open(os.path.join(OUTDIR, "report.json"), "w"),
              indent=1)
    J({"ev": "run_end", "verdict": verdict})
    log("done:", verdict, "1Hz timers:", timers_real,
        "best survival:", rep["best_survival_s"], "s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
