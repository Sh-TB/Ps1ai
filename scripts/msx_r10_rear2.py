#!/usr/bin/env python3
"""msx_r10_rear2.py — Round 10 (Task 16-a): surgical slot-12 turn-lob.

Round-10 rear v1 lesson: the rear phase WALKED the player (direction
held through attack windows), drifted px 2212 -> 2061, and the trio
went respawn-pending before any rear fire connected (0 dmg events).

This run is surgical — ZERO walking after the initial turn:
  - one 2 f LEFT tap to flip facing,
  - then only stationary grenade arms: flat lob (A+LEFT) / arc lob
    (B, then UP+A+LEFT) alternating,
  - census every cycle on slots 10/11/12 (st/hpA4/sx), HP-drop events,
    score +500 kill detection,
  - on slot-12 kill: front-duo kill_phase (proven) + 3,000 f wave-watch
    (do waves stop when the spawner is dead? -> the discriminator).

Honest verdicts; evidence -> scratch/round10_msx/rear2/. ONE beetle
boot per process; no RAM writes; restores disclosed.
"""
import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import msx_r10_timergate as tg                      # noqa: E402
tg.OUTDIR = os.path.join(tg.SCRATCH, "rear2")       # route its png() here
from msx_r10_timergate import (                     # noqa: E402
    A_SCORE, GRENADES, PLAYER_HP, CHOPPER_ST,
    census, presence, alive, px_of, png, log, kill_phase)
from ps1play.telemetry import JsonlTrace            # noqa: E402
from issue4_controller import boot                  # noqa: E402
from mission import ensure_mission                  # noqa: E402

OUTDIR = tg.OUTDIR
STATE = "wr9_arena"
ARMORED_SLOTS = (10, 11, 12)


def slot_view(slots):
    return {s["slot"]: {"st": s["st"], "hp": s["hpA4"], "sx": s["sx"]}
            for s in slots if s["slot"] in ARMORED_SLOTS
            and (s["st"] or s["hpA4"])}


def surgical_rear(p, m, J, max_cycles=14):
    kills, dmg = [], {}
    score0 = int(m.u32(A_SCORE))
    png(p, "rear2_start.png")
    turned = False
    for k in range(max_cycles):
        if not alive(m):
            J({"ev": "rear2_death", "cycle": k})
            png(p, "rear2_death.png")
            return {"stop": "DEATH", "kills": kills, "dmg": dmg,
                    "cycle": k,
                    "score_delta": int(m.u32(A_SCORE)) - score0}
        slots = census(m)
        sv = slot_view(slots)
        J({"ev": "rear2_census", "cycle": k, "px": round(px_of(m), 1),
           "php": int(m.u16(PLAYER_HP)), "gren": int(m.u8(GRENADES)),
           "slots": sv, "pres": presence(slots),
           "score": int(m.u32(A_SCORE))})
        # hp drops + kills (hp disappearance while score jumps = kill)
        for s12_slot, info in sv.items():
            prev = dmg.get(s12_slot, []).pop() \
                if isinstance(dmg.get(s12_slot), list) and dmg[s12_slot] \
                else None
        for s_slot, info in sv.items():
            hist = dmg.setdefault(s_slot, [])
            if hist and info["hp"] < hist[-1]["hp"]:
                J({"ev": "REAR2_HP_DROP", "cycle": k, "slot": s_slot,
                   "from": hist[-1]["hp"], "to": info["hp"],
                   "score": int(m.u32(A_SCORE))})
                png(p, f"rear2_hit_{s_slot}_c{k}.png")
                log("HP DROP slot", s_slot, hist[-1]["hp"], "->",
                    info["hp"])
                hist.append(info)
            elif not hist:
                hist.append(info)
        armed = [s for s in sv.values() if s["st"] in CHOPPER_ST
                 and s["hp"] > 0]
        if not armed:
            J({"ev": "REAR2_ARMED_EMPTY", "cycle": k,
               "score": int(m.u32(A_SCORE))})
            png(p, "rear2_armed_empty.png")
            return {"stop": "ARMED_EMPTY", "kills": kills, "dmg": dmg,
                    "cycle": k,
                    "score_delta": int(m.u32(A_SCORE)) - score0,
                    "final_px": round(px_of(m), 1)}
        # facing + lob (stationary)
        if not turned:
            p.core.run(2, {"LEFT"})            # flip facing only
            p.core.run(1, set())
            turned = True
        gren = int(m.u8(GRENADES))
        if gren > 0 and k % 2 == 0:
            p.core.run(6, {"A", "LEFT"})       # flat lob, no walk
            p.core.run(38, set())
        elif gren > 0:
            p.core.run(3, {"B"})               # hop draw
            p.core.run(6, set())
            p.core.run(8, {"UP", "A", "LEFT"})  # arc lob mid-air
            p.core.run(30, set())
        else:
            p.core.run(8, {"UP", "Y", "LEFT"})  # last resort (drifts)
            p.core.run(20, set())
    return {"stop": "CYCLES", "kills": kills, "dmg": dmg,
            "cycle": max_cycles,
            "score_delta": int(m.u32(A_SCORE)) - score0,
            "final_px": round(px_of(m), 1)}


def wave_watch(p, m, J, frames=3000):
    """After front clear: do waves still come with slot 12 dead?"""
    t0 = p.core.frames_run
    score0 = int(m.u32(A_SCORE))
    chunk = 0
    waves = 0
    while p.core.frames_run - t0 < frames:
        if not alive(m):
            J({"ev": "watch_death", "chunk": chunk})
            png(p, "watch_death.png")
            return {"survived": False, "frames": p.core.frames_run - t0,
                    "waves": waves}
        slots = census(m)
        armed = [s for s in slots if s["st"] in CHOPPER_ST
                 and s["hpA4"] > 0]
        if armed:
            waves += 1
        J({"ev": "watch_chunk", "chunk": chunk,
           "px": round(px_of(m), 1), "php": int(m.u16(PLAYER_HP)),
           "n_armed": len(armed), "score": int(m.u32(A_SCORE))})
        if chunk % 10 == 0:
            png(p, f"watch_c{chunk:04d}.png")
        p.core.run(50, set())
        chunk += 1
    return {"survived": True, "frames": frames, "waves": waves,
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

    rear = surgical_rear(p, m, J)
    J({"ev": "REAR2_DONE", "stop": rear["stop"],
       "dmg_slots": {str(k): len(v) for k, v in rear["dmg"].items()},
       "score_delta": rear["score_delta"]})

    kills12 = rear["score_delta"] >= 400 and any(
        12 in v for v in [rear["dmg"].get(12, [])])
    front = {"stop": "SKIPPED"}
    watch = None
    if rear["stop"] in ("ARMED_EMPTY", "CYCLES"):
        front = kill_phase(p, m, J, 40)
        J({"ev": "FRONT_DONE", "stop": front["stop"],
           "n_kills": len(front.get("kills", [])),
           "score_delta": front.get("score_delta")})
        if front["stop"] == "FIELD_CLEAR":
            watch = wave_watch(p, m, J, 3000)
            J({"ev": "WATCH_DONE", **watch})

    dmg12 = len(rear["dmg"].get(12, []))
    if dmg12 and rear["score_delta"] >= 400:
        verdict = "REAR_KILLED_CAUSAL"
    elif dmg12:
        verdict = "REAR_DAMAGE_CAUSAL"
    elif rear["score_delta"] >= 400:
        verdict = "REAR_KILL_NO_HPTRACE"
    else:
        verdict = "REAR_UNREACHABLE_TURNLOB"
    rep = {"schema": "ps1play-r10-rear2/1", "verdict": verdict,
           "state": STATE, "rear": rear, "front": front,
           "wave_watch": watch, "slot12_dmg_events": dmg12,
           "frames": p.core.frames_run,
           "wall_s": round(time.time() - t0, 1)}
    json.dump(rep, open(os.path.join(OUTDIR, "report.json"), "w"),
              indent=1)
    J({"ev": "run_end", "verdict": verdict})
    log("done:", verdict, "slot12 dmg events:", dmg12)
    return 0


if __name__ == "__main__":
    sys.exit(main())
