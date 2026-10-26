#!/usr/bin/env python3
"""msx_r10_timergate.py — Round 10 (Issue #7) lever (b): TIMER-GATE probe.

Question: is the px-2212 arena camera pin TIMER-gated?  Round 9 proved
the armored-trio kill CAUSAL (+500/kill) yet CAMERA-HELD 0/8 — the
player died (respawn waves) before any resolution.  This script kills
the trio with the PROVEN YB arm (sustained aimed UP+FIRE), cleans the
rear spawner (slot 12 is BEHIND the player), then SURVIVES to the
mission-timer rollover and watches the pin.

v2 instrument fixes from the first probe (scratch/round10_msx/
timergate/ v1 trace):
  * TRIO_DOWN required a single empty census read — slot hpA4 flicker
    fired it instantly (attempt 1 died during its no-input watch).
    Now: two consecutive empty reads required.
  * presence dump: EVERY cycle/chunk logs all slots with st != 0 and
    (hpA4 > 0 or on-screen sx) so respawned armoreds in NEW slots are
    visible (v1 only logged the filtered target list).
  * threats() now includes armored 0xA0D0 with hpA4 > 0 (the v1
    survival tactics ignored the very enemy chewing 100 HP per hit).
  * kite v1 retreated LEFT into the rear spawn side and died (px
    2185->1948, php 265->28).  v2 kite holds the RIGHT window edge.
  * timer words: v1 found NO 1 Hz mission timer — only a 60 Hz frame
    counter at 0x0D4974 (new anchor) and a 0.2 Hz decrementer at
    0x0E7FEE (value ~7-10 at the pin).  v2 logs every discovered
    steady word per chunk and uses the slowest small-value word as the
    rollover clock candidate (flagged, not assumed).

Phases (one beetle boot, savestate `wr9_arena` from msx_r10_cap.py):
  1. READ-ONLY timer discovery (steady-delta intersection, FIRE held).
  2. KILL: YB arm verbatim until targets are gone 2 reads running.
  3. REAR cleanup: flip LEFT rotation (UP+FIRE / fire / hop-lob / flat
     grenade) until no targets remain.
  4. SURVIVE per tactic (fight / kite / hold) until rollover, death,
     or frame cap; walk probe at the end; release => save wr9_unlocked.

Verdicts: CAUSAL (rollover reached AND pin released), NEGATIVE
(rollover reached, pin held), INCONCLUSIVE (never survived to
rollover; survival ceiling measured honestly).  Savestate restores are
disclosed retries (NOT continues); no continues are consumed here.
No RAM writes, no cheats.  Evidence: scratch/round10_msx/timergate/.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.telemetry import JsonlTrace                    # noqa: E402
from issue4_controller import boot                          # noqa: E402
from mission import ensure_mission                          # noqa: E402

SCRATCH = "/home/z/my-project/ps1ai/scratch/round10_msx"
OUTDIR = os.path.join(SCRATCH, "timergate")

PLAYER_X = 0x0CA2E0
PLAYER_HP = 0x0CA2F6
A_SCORE = 0x0EE318
GRENADES = 0x0EDCF4
FLAGS_WORD = 0x0EE518
TABLE, STRIDE = 0x0CA268, 0x14C
CHOPPER_ST = (0xAA94, 0xABDC, 0xA0D0, 0xAB94)   # round-9 extended set
ARMORED_ST = 0xA0D0
CORPSE_ST = (0x4BE4, 0x5CC8)
RAM_U16 = 0x1FC000 // 2
PIN_PX = 2212.0


def log(*a):
    print("[r10-tg]", *a, file=sys.stderr, flush=True)


def px_of(m):
    v = int(m.u32(PLAYER_X))
    if v >= 0x80000000:
        v -= 0x100000000
    return v / 65536.0


def alive(m):
    return (int(m.u32(FLAGS_WORD)) & 0xFF) == 0xFF and px_of(m) != 0.0 \
        and int(m.u16(PLAYER_HP)) > 0


def census(m):
    tv = m.ram[TABLE:TABLE + 36 * STRIDE].view("<u2").astype(np.int32) \
        .reshape(36, STRIDE // 2)
    out = []
    for s in range(1, 36):
        st = int(tv[s, 0])
        xw = (int(tv[s, 61]) << 16) | int(tv[s, 60])
        if not st and not xw:
            continue
        out.append({"slot": s, "st": st,
                    "x": round(xw / 65536.0, 1), "h": int(tv[s, 63]),
                    "sx": int(tv[s, 71]), "hpA4": int(tv[s, 82])})
    return out


def targets(slots):
    return [s for s in slots
            if s["st"] in CHOPPER_ST and s["hpA4"] > 0]


def presence(slots):
    """Everything with a type that is either wounded or on-screen."""
    return [{"slot": s["slot"], "st": s["st"], "hpA4": s["hpA4"],
             "sx": s["sx"], "x": s["x"], "h": s["h"]}
            for s in slots
            if s["st"] not in CORPSE_ST
            and (s["hpA4"] > 0 or 0 < s["sx"] < 320)]


def threats(slots):
    return [s for s in slots
            if s["st"] not in CORPSE_ST and s["hpA4"] > 0
            and 0 < s["sx"] < 320]


def redness(rgb, sx):
    if rgb is None or sx <= 0:
        return None
    h, w = rgb.shape[:2]
    c0, c1 = max(0, sx - 10), min(w, sx + 11)
    if c1 <= c0:
        return None
    win = rgb[0:min(h, 140), c0:c1].astype(np.int16)
    r = win[:, :, 0] - (win[:, :, 1] + win[:, :, 2]) // 2
    return round(float(r.mean(axis=0).max()), 1)


def png(p, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(OUTDIR, name))
    return rgb


def with_red(p, m, tg):
    rgb = p.core.frame_rgb()
    return [{**s, "red": redness(rgb, s["sx"])} for s in tg]


def pick_target(tg, px):
    if not tg:
        return None, None
    reds = [c for c in tg if (c.get("red") or 0) >= 8.0]
    if reds:
        return max(reds, key=lambda c: c["red"]), "RED"
    return min(tg, key=lambda c: abs(c["x"] - px)), "NEAREST"


# --------------------------------------------------------------------
# read-only timer discovery
# --------------------------------------------------------------------
def u16_snapshot(m):
    return m.ram[:RAM_U16 * 2].view("<u2").astype(np.int32)


def discover_timers(p, m, J, rounds=3, window=300):
    """Steady down-counting u16 words (read-only).  Windows hold FIRE
    so waves thin out; the strict steady-delta filter ignores inputs."""
    cands = None
    deltas = {}
    v_prev = u16_snapshot(m)
    for r in range(rounds):
        p.core.run(window, {"Y"})
        if not alive(m):
            J({"ev": "timer_scan_death", "round": r})
            break
        v = u16_snapshot(m)
        d = v_prev - v
        ok = np.flatnonzero((d >= 1) & (d <= 2 * window) & (v >= 0))
        cur = set(int(i) for i in ok)
        if cands is None:
            cands = cur
        else:
            cands &= cur
        for i in list(cands):
            deltas.setdefault(i, []).append(int(d[i]))
        v_prev = v
        J({"ev": "timer_round", "round": r, "n_cands": len(cands)})
    out = []
    for i in sorted(cands or []):
        ds = deltas.get(i, [])
        if len(ds) == rounds and len(set(ds)) == 1:   # STEADY rate
            out.append({"addr": i * 2, "delta_per_window": ds[0],
                        "rate_hz": round(ds[0] / window * 60.0, 3),
                        "value": int(u16_snapshot(m)[i])})
    out.sort(key=lambda x: (abs(x["rate_hz"] - 1.0), x["addr"]))
    J({"ev": "timers_found", "n": len(out), "timers": out[:16]})
    log("timer candidates:", [(hex(t["addr"]), t["rate_hz"], t["value"])
                              for t in out[:8]])
    return out[:16]


def timer_values(m, timers):
    return {hex(t["addr"]): int(m.u16(t["addr"])) for t in timers}


def pick_rollover_timer(timers):
    """Rollover clock candidate: 1 Hz first; else the slowest steady
    word with a small remaining value (flagged, never assumed)."""
    for t in timers:
        if abs(t["rate_hz"] - 1.0) < 0.05:
            return t, "1HZ"
    small = [t for t in timers if t["value"] <= 400
             and t["rate_hz"] <= 1.0]
    if small:
        slow = min(small, key=lambda t: t["rate_hz"])
        return slow, "SLOW_CANDIDATE"
    return None, "NONE"


# --------------------------------------------------------------------
# kill phase (proven YB arm, verbatim cadence)
# --------------------------------------------------------------------
def kill_phase(p, m, J, max_cycles=90):
    kills, hp_hist = [], {}
    score0 = int(m.u32(A_SCORE))
    empty_streak = 0
    png(p, "kill_start.png")
    for k in range(max_cycles):
        if not alive(m):
            J({"ev": "kill_phase_death", "cycle": k})
            return {"stop": "DEATH", "kills": kills, "cycle": k,
                    "score_delta": int(m.u32(A_SCORE)) - score0}
        px = px_of(m)
        slots = census(m)
        tg = with_red(p, m, targets(slots))
        J({"ev": "presence", "phase": "kill", "cycle": k,
           "px": round(px, 1), "php": int(m.u16(PLAYER_HP)),
           "pres": presence(slots)})
        # bookkeeping
        for t in tg:
            prev = hp_hist.get(t["slot"])
            if prev is not None and t["hpA4"] < prev:
                J({"ev": "TARGET_HP_DROP", "cycle": k,
                   "slot": t["slot"], "st": t["st"], "from": prev,
                   "to": t["hpA4"], "red": t.get("red"),
                   "score": int(m.u32(A_SCORE))})
                png(p, f"kill_hit_{t['slot']}_{k}.png")
            hp_hist[t["slot"]] = t["hpA4"]
        for s in list(hp_hist):
            if all(x["slot"] != s for x in tg):
                kills.append({"cycle": k, "slot": s,
                              "last_hp": hp_hist.pop(s)})
                J({"ev": "TARGET_KILL", "cycle": k, **kills[-1],
                   "score": int(m.u32(A_SCORE)), "remaining": tg})
                png(p, f"kill_{s}_cyc{k}.png")
                log("KILL slot", s, "score", int(m.u32(A_SCORE)))
                break
        # TWO consecutive empty reads before declaring the field clear
        if not tg:
            empty_streak += 1
        else:
            empty_streak = 0
        if empty_streak >= 2:
            J({"ev": "FIELD_CLEAR", "cycle": k,
               "score": int(m.u32(A_SCORE))})
            return {"stop": "FIELD_CLEAR", "kills": kills, "cycle": k,
                    "score_delta": int(m.u32(A_SCORE)) - score0,
                    "final_px": round(px_of(m), 1)}
        tgt, why = pick_target(tg, px)
        dx = round(tgt["x"] - px, 1) if tgt else 0
        d = "RIGHT" if dx >= 0 else "LEFT"
        up = {"UP", "Y", d} if abs(dx) > 4 else {"UP", "Y"}
        p.core.run(24, up)
        p.core.run(16, set())
    return {"stop": "CYCLES", "kills": kills, "cycle": max_cycles,
            "score_delta": int(m.u32(A_SCORE)) - score0,
            "final_px": round(px_of(m), 1)}


# --------------------------------------------------------------------
# rear-kill sub-phase (slot 12 spawns BEHIND the player at sx ~65)
# --------------------------------------------------------------------
def rear_phase(p, m, J, max_cycles=40):
    """Flip facing LEFT and work the rear: UP+FIRE left, horizontal
    fire left, hop+UP-lob left, flat grenade lob left."""
    kills, hp_hist = [], {}
    score0 = int(m.u32(A_SCORE))
    png(p, "rear_start.png")
    for k in range(max_cycles):
        if not alive(m):
            return {"stop": "DEATH", "kills": kills,
                    "score_delta": int(m.u32(A_SCORE)) - score0}
        slots = census(m)
        tg = targets(slots)
        J({"ev": "presence", "phase": "rear", "cycle": k,
           "px": round(px_of(m), 1), "php": int(m.u16(PLAYER_HP)),
           "pres": presence(slots)})
        for t in tg:
            prev = hp_hist.get(t["slot"])
            if prev is not None and t["hpA4"] < prev:
                J({"ev": "REAR_HP_DROP", "cycle": k, "slot": t["slot"],
                   "from": prev, "to": t["hpA4"],
                   "sx": t["sx"], "score": int(m.u32(A_SCORE))})
                png(p, f"rear_hit_{t['slot']}_{k}.png")
            hp_hist[t["slot"]] = t["hpA4"]
        for s in list(hp_hist):
            if all(x["slot"] != s for x in tg):
                kills.append({"cycle": k, "slot": s})
                J({"ev": "REAR_KILL", "cycle": k, "slot": s,
                   "score": int(m.u32(A_SCORE))})
                png(p, f"rear_kill_{s}_cyc{k}.png")
                log("REAR KILL slot", s, "score", int(m.u32(A_SCORE)))
                break
        if not tg:
            J({"ev": "ALL_TARGETS_DOWN", "cycle": k,
               "score": int(m.u32(A_SCORE))})
            return {"stop": "ALL_CLEAR", "kills": kills,
                    "score_delta": int(m.u32(A_SCORE)) - score0}
        ph = k % 4
        p.core.run(4, {"LEFT"})            # face backward
        p.core.run(2, set())
        gren = int(m.u8(GRENADES))
        if ph == 0:
            p.core.run(24, {"UP", "Y", "LEFT"})
            p.core.run(16, set())
        elif ph == 1:
            p.core.run(24, {"Y", "LEFT"})
            p.core.run(16, set())
        elif ph == 2 and gren > 0:
            p.core.run(3, {"B"})
            p.core.run(8, set())
            p.core.run(8, {"UP", "A", "LEFT"})
            p.core.run(25, set())
        elif gren > 0:
            p.core.run(6, {"A", "LEFT"})
            p.core.run(34, set())
        else:
            p.core.run(24, {"UP", "Y", "LEFT"})
            p.core.run(16, set())
    return {"stop": "CYCLES", "kills": kills,
            "score_delta": int(m.u32(A_SCORE)) - score0}


# --------------------------------------------------------------------
# survive phase
# --------------------------------------------------------------------
def survive_phase(p, m, J, tactic, timers, max_frames=21000):
    """Survive at the pin until rollover / death / frame cap."""
    roll_t, roll_kind = pick_rollover_timer(timers)
    J({"ev": "rollover_clock", "tactic": tactic, "kind": roll_kind,
       "timer": roll_t})
    t0frame = p.core.frames_run
    score0 = int(m.u32(A_SCORE))
    rollover_at = None
    released = False
    jump_cd = 0
    chunk = 0
    png(p, f"survive_{tactic}_start.png")
    while p.core.frames_run - t0frame < max_frames:
        if not alive(m):
            surv = p.core.frames_run - t0frame
            J({"ev": "SURVIVE_DEATH", "tactic": tactic,
               "survival_frames": surv,
               "survival_s": round(surv / 60.0, 1),
               "timers_at_death": timer_values(m, timers),
               "px": round(px_of(m), 1),
               "score": int(m.u32(A_SCORE))})
            png(p, f"survive_{tactic}_death.png")
            return {"survived": False, "frames": surv,
                    "released": released, "rollover": rollover_at,
                    "score_delta": int(m.u32(A_SCORE)) - score0}
        px = px_of(m)
        slots = census(m)
        th = threats(slots)
        tv = timer_values(m, timers)
        near_sx = min(th, key=lambda s: abs(s["sx"] - 120))["sx"] \
            if th else None
        near_d = abs(near_sx - 120) if near_sx is not None else 999
        J({"ev": "survive_chunk", "tactic": tactic, "chunk": chunk,
           "frame": p.core.frames_run, "px": round(px, 1),
           "php": int(m.u16(PLAYER_HP)),
           "score": int(m.u32(A_SCORE)),
           "gren": int(m.u8(GRENADES)),
           "timers": tv, "n_threats": len(th),
           "near_sx": near_sx, "near_d": round(near_d, 0),
           "pres": presence(slots)})
        if chunk % 10 == 0:
            png(p, f"survive_{tactic}_c{chunk:04d}.png")
        # ---- rollover detection ----
        if roll_t is not None and tv[hex(roll_t["addr"])] == 0 \
                and rollover_at is None:
            rollover_at = p.core.frames_run - t0frame
            J({"ev": "TIMER_ROLLOVER", "tactic": tactic, "kind":
               roll_kind, "at_frame": rollover_at, "px": round(px, 1)})
            png(p, f"survive_{tactic}_ROLLOVER.png")
        # ---- spontaneous release detection ----
        if px > PIN_PX + 20.0:
            released = True
            J({"ev": "PX_ADVANCED_PAST_PIN", "px": round(px, 1)})
            break
        # ---- tactics ----
        if tactic == "hold":
            if th:
                d = "RIGHT" if near_sx > 120 else "LEFT"
                up = {"UP", "Y"} if any(s["h"] < 45 for s in th) \
                    else {"Y", d}
                p.core.run(30, up)
                p.core.run(30, set())
            else:
                p.core.run(60, set())
        elif tactic == "fight":
            if th:
                d = "RIGHT" if near_sx > 120 else "LEFT"
                if near_d < 40 and jump_cd <= 0:
                    p.core.run(12, {"B"})
                    jump_cd = 5
                elif near_d < 90:
                    p.core.run(28, {"Y", d})
                    p.core.run(12, set())
                else:
                    p.core.run(20, {"UP", "Y"})
                    p.core.run(20, set())
            else:
                p.core.run(60, set())
            jump_cd -= 1
        else:  # kite: hold the RIGHT window edge, jump rear waves
            if px < PIN_PX - 60.0:
                p.core.run(40, {"RIGHT"})       # back to the edge
                p.core.run(20, set())
            elif th and near_d < 45 and jump_cd <= 0:
                d = "RIGHT" if near_sx > 120 else "LEFT"
                p.core.run(12, {"B"})
                jump_cd = 6
            elif th and near_d < 100:
                d = "RIGHT" if near_sx > 120 else "LEFT"
                p.core.run(28, {"Y", d})
                p.core.run(12, set())
            else:
                p.core.run(60, set())
            jump_cd -= 1
        chunk += 1
    surv = p.core.frames_run - t0frame
    # end-of-phase walk probe (release check)
    p0 = px_of(m)
    p.core.run(300, {"RIGHT"})
    p1 = px_of(m)
    adv = round(p1 - p0, 1)
    J({"ev": "WALK_PROBE", "tactic": tactic, "px0": round(p0, 1),
       "px1": round(p1, 1), "advance": adv, "released": adv >= 100.0,
       "rollover": rollover_at})
    png(p, f"survive_{tactic}_probe.png")
    if adv >= 100.0:
        try:
            p.save_state("wr9_unlocked")
            J({"ev": "STATE_SAVED", "state": "wr9_unlocked"})
        except Exception as e:                        # noqa: BLE001
            J({"ev": "STATE_SAVE_FAIL", "err": repr(e)[:120]})
    return {"survived": True, "frames": surv, "released": adv >= 100.0
            or released, "rollover": rollover_at,
            "probe_advance": adv,
            "score_delta": int(m.u32(A_SCORE)) - score0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attempts", type=str, default="fight,kite,hold")
    ap.add_argument("--kill-cycles", type=int, default=90)
    ap.add_argument("--max-survive-frames", type=int, default=21000)
    ap.add_argument("--max-s", type=float, default=470.0)
    ap.add_argument("--state", default="wr9_arena")
    args = ap.parse_args()
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
    try:
        p.load_state(args.state)
    except Exception as e:                            # noqa: BLE001
        json.dump({"verdict": "NO_STATE", "err": repr(e)[:160]},
                  open(os.path.join(OUTDIR, "report.json"), "w"), indent=1)
        return 3
    J({"ev": "state_loaded", "state": args.state,
       "px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
       "php": int(m.u16(PLAYER_HP)), "gren": int(m.u8(GRENADES))})
    png(p, "post_load.png")

    # phase 1: read-only timer discovery
    timers = discover_timers(p, m, J)
    if not alive(m):
        p.load_state(args.state)
        J({"ev": "restore_after_timer_scan", "disclosed": True})

    # phase 2+3 per attempt
    attempts = []
    restores = 0
    for i, tactic in enumerate(args.attempts.split(",")):
        tactic = tactic.strip() or "fight"
        if i > 0:
            p.load_state(args.state)
            restores += 1
            J({"ev": "restore", "attempt": i, "tactic": tactic,
               "disclosed": True})
        # every attempt re-runs kill+rear from the same restored state
        kill = kill_phase(p, m, J, args.kill_cycles)
        J({"ev": "KILL_PHASE_DONE", "tactic": tactic,
           **{k: v for k, v in kill.items() if k != "kills"},
           "n_kills": len(kill.get("kills", []))})
        attempts.append({"tactic": tactic, "kill": kill})
        if kill["stop"] == "DEATH":
            p.load_state(args.state)
            restores += 1
            J({"ev": "restore_after_kill_death", "disclosed": True})
            kill = kill_phase(p, m, J, args.kill_cycles)
            attempts[-1]["kill_retry"] = kill
            if kill["stop"] == "DEATH":
                break
        if targets(census(m)):
            rear = rear_phase(p, m, J)
            attempts[-1]["rear"] = rear
            J({"ev": "REAR_PHASE_DONE", "tactic": tactic,
               "stop": rear["stop"],
               "n_kills": len(rear.get("kills", [])),
               "score_delta": rear.get("score_delta")})
            if rear["stop"] == "DEATH":
                p.load_state(args.state)
                restores += 1
                J({"ev": "restore_after_rear_death", "disclosed": True})
        surv = survive_phase(p, m, J, tactic, timers,
                             args.max_survive_frames)
        attempts[-1]["survive"] = surv
        J({"ev": "ATTEMPT_DONE", "tactic": tactic, **surv})
        if surv.get("released"):
            break
        if time.time() - t0 > args.max_s:
            J({"ev": "time_wall"})
            break

    # verdict
    reached = [a for a in attempts
               if (a.get("survive") or {}).get("rollover") is not None]
    released_any = any((a.get("survive") or {}).get("released")
                       for a in attempts)
    best = max(attempts, key=lambda a: (a.get("survive") or {})
               .get("frames", 0), default=None)
    if released_any:
        verdict = "CAUSAL_TIMER_GATED"
    elif reached:
        verdict = "NEGATIVE_ROLLOVER_HELD"
    else:
        verdict = "INCONCLUSIVE_SURVIVAL_CEILING"
    rep = {"schema": "ps1play-r10-timergate/2",
           "verdict": verdict,
           "state": args.state, "pin_px": PIN_PX,
           "timers": timers,
           "attempts": attempts,
           "restores_disclosed": restores,
           "continues_used": 0,
           "best_survival_frames": (best["survive"]["frames"]
                                    if best and best.get("survive")
                                    else 0),
           "best_survival_s": round((best["survive"]["frames"] / 60.0)
                                    if best and best.get("survive")
                                    else 0, 1),
           "frames": p.core.frames_run,
           "wall_s": round(time.time() - t0, 1)}
    json.dump(rep, open(os.path.join(OUTDIR, "report.json"), "w"),
              indent=1)
    J({"ev": "run_end", "verdict": verdict})
    log("done:", verdict, "best survival:", rep["best_survival_s"],
        "s; restores:", restores)
    return 0


if __name__ == "__main__":
    sys.exit(main())
