#!/usr/bin/env python3
"""msx_r11_wave_stop.py — Round 11 / Segment 4 (Issue #7 arena).

The round-10 open discriminator: do respawn waves STOP when the rear
spawner (slot 12) stays DEAD, or do they continue?

Protocol (ONE beetle boot, savestate `wr9_arena`, px 2212 pin):
  1. slot 12 FIRST — the proven rear2 surgical recipe (2 f LEFT flip +
     stationary grenade lobs).  Slot-12 kill = hpA4 drop to 0/gone with
     score delta >= 400 (the round-10 +500/kill causal signature).
  2. then the front duo — the PROVEN YB arm (kill_phase).
  3. then a 3,000 f NO-INPUT watch with census every 300 f: any armed
     CHOPPER_ST sighting (hpA4 > 0) = a respawn wave.
Baseline: the round-10 timergate/rollover/rear2 traces (front cleared,
slot 12 alive or respawn-pending) are parsed by the same wave counter
(msx_r11_lib.count_waves) for an apples-to-apples comparison.

No RAM writes, no continues (none exist past px 2212); a savestate
restore after death is a DISCLOSED retry.  Verdict: WAVES_STOP /
WAVES_CONTINUE / INCONCLUSIVE with numbers.
Evidence: scratch/round11_msx/wave_stop/.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import msx_r10_timergate as tg                          # noqa: E402
tg.OUTDIR = "/home/z/my-project/ps1ai/scratch/round11_msx/wave_stop"
from msx_r10_timergate import (                         # noqa: E402
    A_SCORE, GRENADES, PLAYER_HP, CHOPPER_ST,
    census, alive, px_of, png, kill_phase)
from msx_r11_lib import count_waves                     # noqa: E402
from ps1play.telemetry import JsonlTrace                # noqa: E402
from issue4_controller import boot                      # noqa: E402
from mission import ensure_mission                      # noqa: E402

OUTDIR = tg.OUTDIR
STATE = "wr9_arena"
R10 = "/home/z/my-project/ps1ai/scratch/round10_msx"


def log(*a):
    print("[r11-ws]", *a, file=sys.stderr, flush=True)


def surgical_rear12(p, m, J, max_cycles=14):
    """rear2 recipe, tracked per-slot so slot-12's death is verifiable."""
    dmg = {}
    score0 = int(m.u32(A_SCORE))
    png(p, "ws_rear2_start.png")
    turned = False
    for k in range(max_cycles):
        if not alive(m):
            J({"ev": "ws_rear2_death", "cycle": k})
            return {"stop": "DEATH", "dmg": dmg,
                    "score_delta": int(m.u32(A_SCORE)) - score0}
        slots = census(m)
        sv = {s["slot"]: s for s in slots
              if s["slot"] in (10, 11, 12) and (s["st"] or s["hpA4"])}
        J({"ev": "ws_rear2_census", "cycle": k,
           "px": round(px_of(m), 1), "php": int(m.u16(PLAYER_HP)),
           "gren": int(m.u8(GRENADES)),
           "slots": {k2: {"st": v["st"], "hp": v["hpA4"], "sx": v["sx"]}
                     for k2, v in sv.items()},
           "score": int(m.u32(A_SCORE))})
        armed = [s for s in sv.values() if s["st"] in CHOPPER_ST
                 and s["hpA4"] > 0]
        for s_slot, s in sv.items():
            hist = dmg.setdefault(s_slot, [])
            if hist and s["hpA4"] < hist[-1]["hpA4"]:
                J({"ev": "WS_HP_DROP", "cycle": k, "slot": s_slot,
                   "from": hist[-1]["hpA4"], "to": s["hpA4"],
                   "score": int(m.u32(A_SCORE))})
                hist.append(s)
            elif not hist:
                hist.append(s)
        if not armed:
            J({"ev": "WS_ARMED_EMPTY", "cycle": k,
               "score": int(m.u32(A_SCORE))})
            return {"stop": "ARMED_EMPTY", "dmg": dmg,
                    "score_delta": int(m.u32(A_SCORE)) - score0,
                    "final_px": round(px_of(m), 1)}
        if not turned:
            p.core.run(2, {"LEFT"})
            p.core.run(1, set())
            turned = True
        gren = int(m.u8(GRENADES))
        if gren > 0 and k % 2 == 0:
            p.core.run(6, {"A", "LEFT"})
            p.core.run(38, set())
        elif gren > 0:
            p.core.run(3, {"B"})
            p.core.run(6, set())
            p.core.run(8, {"UP", "A", "LEFT"})
            p.core.run(30, set())
        else:
            p.core.run(8, {"UP", "Y", "LEFT"})
            p.core.run(20, set())
    return {"stop": "CYCLES", "dmg": dmg,
            "score_delta": int(m.u32(A_SCORE)) - score0,
            "final_px": round(px_of(m), 1)}


def no_input_watch(p, m, J, frames=3000, sample=300):
    """STRICT no-input watch; census every `sample` f."""
    t0f = p.core.frames_run
    sightings = []
    chunk = 0
    png(p, "ws_watch_start.png")
    while p.core.frames_run - t0f < frames:
        if not alive(m):
            J({"ev": "WS_DEATH", "watch_f": p.core.frames_run - t0f,
               "waves_seen": sum(1 for s in sightings if s["armed"])})
            png(p, "ws_watch_death.png")
            return {"survived": False,
                    "frames": p.core.frames_run - t0f,
                    "sightings": sightings}
        p.core.run(sample, set())
        f = p.core.frames_run
        slots = census(m)
        armed = [s for s in slots if s["st"] in CHOPPER_ST
                 and s["hpA4"] > 0]
        sightings.append({"frame": f, "armed": bool(armed),
                          "n_armed": len(armed),
                          "slots": [s["slot"] for s in armed],
                          "px": round(px_of(m), 1),
                          "php": int(m.u16(PLAYER_HP)),
                          "score": int(m.u32(A_SCORE))})
        J({"ev": "ws_watch", "chunk": chunk, "frame": f,
           "armed": bool(armed), "n_armed": len(armed),
           "slots": [s["slot"] for s in armed],
           "px": round(px_of(m), 1), "php": int(m.u16(PLAYER_HP)),
           "score": int(m.u32(A_SCORE))})
        if chunk % 2 == 0:
            png(p, f"ws_watch_c{chunk:03d}.png")
        chunk += 1
    return {"survived": True, "frames": frames, "sightings": sightings}


def parse_baseline():
    """Round-10 wave counts via the same counter (offline, read-only)."""
    out = {}
    for name, path in (("timergate", os.path.join(R10, "timergate",
                                                  "trace.jsonl")),
                       ("rollover", os.path.join(R10, "rollover",
                                                 "trace.jsonl")),
                       ("rear2", os.path.join(R10, "rear2",
                                              "trace.jsonl"))):
        if not os.path.exists(path):
            out[name] = {"error": "missing trace"}
            continue
        clears = []          # frames where armed count went >0 -> 0
        sight = []
        armed_prev = 0
        for line in open(path):
            try:
                ev = json.loads(line)
            except Exception:                          # noqa: BLE001
                continue
            if ev.get("ev") not in ("presence", "survive_chunk",
                                    "watch_chunk"):
                continue
            pres = ev.get("pres")
            if pres is None and "n_armed" in ev:
                armed = [1] * int(ev["n_armed"] or 0)
            else:
                pres = pres or []
                armed = [p_ for p_ in pres
                         if p_.get("st") in CHOPPER_ST
                         and p_.get("hpA4", 0) > 0]
            f = ev.get("frame") or ev.get("cycle")
            sight.append({"frame": f, "armed": bool(armed)})
            if armed_prev > 0 and not armed:
                clears.append(f)
            armed_prev = len(armed)
        out[name] = {"n_samples": len(sight), "clears": clears,
                     **count_waves(sight)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch-frames", type=int, default=3000)
    ap.add_argument("--sample", type=int, default=300)
    ap.add_argument("--max-s", type=float, default=650.0)
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
        p.load_state(STATE)
    except Exception as e:                             # noqa: BLE001
        json.dump({"verdict": "NO_STATE", "err": repr(e)[:160]},
                  open(os.path.join(OUTDIR, "report.json"), "w"),
                  indent=1)
        return 3
    J({"ev": "state_loaded", "px": round(px_of(m), 1),
       "score": int(m.u32(A_SCORE)), "php": int(m.u16(PLAYER_HP)),
       "gren": int(m.u8(GRENADES))})
    png(p, "ws_post_load.png")

    # 1. slot 12 FIRST
    rear = surgical_rear12(p, m, J)
    dmg12 = len(rear["dmg"].get(12, []))
    killed12 = dmg12 > 0 and rear["score_delta"] >= 400
    J({"ev": "SLOT12_PHASE_DONE", "stop": rear["stop"],
       "dmg12_events": dmg12, "score_delta": rear["score_delta"],
       "slot12_killed": killed12})
    if rear["stop"] == "DEATH":
        p.load_state(STATE)
        restores = 1
        J({"ev": "restore_after_rear_death", "disclosed": True})
        rear = surgical_rear12(p, m, J)
        dmg12 = len(rear["dmg"].get(12, []))
        killed12 = dmg12 > 0 and rear["score_delta"] >= 400
    else:
        restores = 0

    # 2. front duo
    front = kill_phase(p, m, J, 50)
    J({"ev": "FRONT_DONE", "stop": front["stop"],
       "n_kills": len(front.get("kills", [])),
       "score_delta": front.get("score_delta")})
    if front["stop"] == "DEATH":
        p.load_state(STATE)
        restores += 1
        J({"ev": "restore_after_front_death", "disclosed": True})
        rear = surgical_rear12(p, m, J)
        front = kill_phase(p, m, J, 50)
        J({"ev": "RETRY_DONE", "rear_stop": rear["stop"],
           "front_stop": front["stop"]})

    # 3. no-input watch
    watch = no_input_watch(p, m, J, args.watch_frames, args.sample)
    waves = count_waves(watch["sightings"])
    J({"ev": "WATCH_DONE", "survived": watch["survived"],
       "n_waves": waves["n_waves"],
       "first_latency": waves["first_latency"]})

    baseline = parse_baseline()

    slot12_alive_after = any(
        s["slot"] == 12 and s["hpA4"] > 0
        for s in census(m))
    if not killed12:
        verdict = "INCONCLUSIVE_SLOT12_NOT_KILLED"
    elif watch["survived"] and waves["n_waves"] == 0:
        verdict = "WAVES_STOP"
    elif waves["n_waves"] > 0:
        verdict = "WAVES_CONTINUE"
    else:
        verdict = "INCONCLUSIVE_WATCH_DEATH"
    rep = {"schema": "ps1play-r11-wave-stop/1", "verdict": verdict,
           "state": STATE, "slot12_killed": killed12,
           "slot12_dmg_events": dmg12,
           "slot12_alive_after_watch": slot12_alive_after,
           "rear": rear, "front": {k: v for k, v in front.items()
                                   if k != "kills"},
           "front_n_kills": len(front.get("kills", [])),
           "watch": {k: v for k, v in watch.items()},
           "waves": waves, "restores_disclosed": restores,
           "round10_baseline": baseline,
           "frames": p.core.frames_run,
           "wall_s": round(time.time() - t0, 1)}
    json.dump(rep, open(os.path.join(OUTDIR, "report.json"), "w"),
              indent=1)
    J({"ev": "run_end", "verdict": verdict, "n_waves":
       waves["n_waves"]})
    log("done:", verdict, "waves:", waves["n_waves"],
        "first_latency:", waves["first_latency"],
        "baseline:", {k: v.get("n_waves") for k, v in
                      baseline.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
