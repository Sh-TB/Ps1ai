#!/usr/bin/env python3
"""msx_r10_rear.py — Round 10 (Task 16-a): slot-12 rear-spawner experiment.

Evidence chain so far (round 9 + round-10 cap/timergate):
  - px-2212 pin: forward duo (slots 10/11) kill-causal, +500 each;
  - FIELD_CLEAR (2 empty reads) fires while slot 12 (sx ~65 LEFT, hp
    300, st 0xA0D0) is respawn-pending -> rear_phase never ran;
  - post-clear survival caps at ~19 s (best 1,140 f) -> the 300 s
    rollover (18,000 f) is unreachable while the rear spawner lives.

This run is the discriminator:
  R1  respawn-aware rear aggression — left-half targets first, ALL
      CLEAR only after ~600 f of zero armored presence; any slot-12
      HP drop proves rear REACHABILITY even without a kill.
  R2  on ALL_CLEAR -> survive_phase(fight) up to 21,000 f: rollover +
      camera-release detection (wr9_unlocked savestate on release).

Honest verdicts; evidence -> scratch/round10_msx/rear/. ONE beetle
boot per process; savestate restores disclosed; no RAM writes.
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
tg.OUTDIR = os.path.join(tg.SCRATCH, "rear")        # route its png() here
from msx_r10_timergate import (                     # noqa: E402
    A_SCORE, GRENADES, PLAYER_HP, CHOPPER_ST, CORPSE_ST,
    census, presence, threats, with_red, pick_target,
    discover_timers, survive_phase, alive, px_of, png, log)
from ps1play.telemetry import JsonlTrace            # noqa: E402
from issue4_controller import boot                  # noqa: E402
from mission import ensure_mission                  # noqa: E402

OUTDIR = tg.OUTDIR
STATE = "wr9_arena"


def rear_clear_phase(p, m, J, max_cycles=140, clean_cycles=6):
    """Left-first aggression; ALL_CLEAR needs clean_cycles*~100 f of
    zero armored presence (respawn-pending aware)."""
    kills, hp_hist, dmg = [], {}, {}
    score0 = int(m.u32(A_SCORE))
    last_armored = 0
    png(p, "rear_start.png")
    for k in range(max_cycles):
        if not alive(m):
            J({"ev": "rear_death", "cycle": k})
            png(p, "rear_death.png")
            return {"stop": "DEATH", "kills": kills, "dmg": dmg, "cycle": k,
                    "score_delta": int(m.u32(A_SCORE)) - score0}
        px = px_of(m)
        slots = census(m)
        armored = [s for s in slots
                   if s["st"] in CHOPPER_ST and s["hpA4"] > 0]
        J({"ev": "presence", "phase": "rear", "cycle": k,
           "px": round(px, 1), "php": int(m.u16(PLAYER_HP)),
           "gren": int(m.u8(GRENADES)),
           "pres": presence(slots)})
        for t in armored:
            prev = hp_hist.get(t["slot"])
            if prev is not None and t["hpA4"] < prev:
                dmg.setdefault(t["slot"], []).append(
                    {"cycle": k, "from": prev, "to": t["hpA4"]})
                J({"ev": "REAR_HP_DROP", "cycle": k, "slot": t["slot"],
                   "sx": t["sx"], "from": prev, "to": t["hpA4"],
                   "score": int(m.u32(A_SCORE))})
                png(p, f"rear_hit_{t['slot']}_{k}.png")
                log("HP DROP slot", t["slot"], prev, "->", t["hpA4"])
            hp_hist[t["slot"]] = t["hpA4"]
        for s in list(hp_hist):
            if all(x["slot"] != s for x in armored):
                kills.append({"cycle": k, "slot": s,
                              "last_hp": hp_hist.pop(s)})
                J({"ev": "SLOT_KILL", "cycle": k, **kills[-1],
                   "score": int(m.u32(A_SCORE))})
                png(p, f"kill_{s}_cyc{k}.png")
                log("KILL slot", s, "score", int(m.u32(A_SCORE)))
        if not armored:
            if k - last_armored >= clean_cycles:
                J({"ev": "ALL_CLEAR", "cycle": k,
                   "clean_for": clean_cycles,
                   "score": int(m.u32(A_SCORE))})
                png(p, "all_clear.png")
                return {"stop": "ALL_CLEAR", "kills": kills, "dmg": dmg,
                        "cycle": k,
                        "score_delta": int(m.u32(A_SCORE)) - score0,
                        "final_px": round(px_of(m), 1)}
        else:
            last_armored = k
        # target: leftmost visible armored, else any armored; empty
        # armored (respawn-pending, clean window not yet reached) ->
        # neutral settle chunk (the round-10 crash fix)
        if not armored:
            p.core.run(40, set())
            continue
        tgr = with_red(p, m, armored)
        left = [t for t in tgr if 0 < t["sx"] <= 140]
        tgt, _why = pick_target(left if left else tgr, px)
        if tgt is None:
            pool = left if left else tgr
            tgt = min(pool, key=lambda t: abs(t["sx"] - 120))
        d = "LEFT" if tgt["sx"] <= 140 else "RIGHT"
        gren = int(m.u8(GRENADES))
        ph = k % 4
        p.core.run(4, {d})                       # face the target side
        p.core.run(2, set())
        if ph == 0 or gren <= 0:
            p.core.run(24, {"UP", "Y", d})
            p.core.run(16, set())
        elif ph == 1:
            p.core.run(24, {"Y", d})
            p.core.run(16, set())
        elif ph == 2:
            p.core.run(3, {"B"})                 # draw grenade
            p.core.run(8, set())
            p.core.run(8, {"UP", "A", d})        # arc lob
            p.core.run(25, set())
        else:
            p.core.run(6, {"A", d})              # flat lob
            p.core.run(34, set())
    return {"stop": "CYCLES", "kills": kills, "dmg": dmg,
            "cycle": max_cycles,
            "score_delta": int(m.u32(A_SCORE)) - score0,
            "final_px": round(px_of(m), 1)}


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
    J({"ev": "state_loaded", "state": STATE,
       "px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
       "php": int(m.u16(PLAYER_HP)), "gren": int(m.u8(GRENADES))})
    png(p, "post_load.png")

    timers = discover_timers(p, m, J)
    if not alive(m):
        p.load_state(STATE)
        J({"ev": "restore_after_timer_scan", "disclosed": True})

    # R1: respawn-aware rear aggression (retry once on death)
    restores = 0
    rear = rear_clear_phase(p, m, J)
    J({"ev": "REAR_DONE", "stop": rear["stop"],
       "n_kills": len(rear["kills"]),
       "dmg_slots": {str(k): len(v) for k, v in rear["dmg"].items()},
       "score_delta": rear["score_delta"]})
    if rear["stop"] == "DEATH":
        p.load_state(STATE)
        restores += 1
        J({"ev": "restore_after_rear_death", "disclosed": True})
        rear = rear_clear_phase(p, m, J)
        J({"ev": "REAR_DONE_RETRY", "stop": rear["stop"],
           "n_kills": len(rear["kills"]),
           "dmg_slots": {str(k): len(v) for k, v in rear["dmg"].items()},
           "score_delta": rear["score_delta"]})

    # R2: only meaningful after ALL_CLEAR (front duo + rear dead)
    surv = None
    if rear["stop"] == "ALL_CLEAR":
        surv = survive_phase(p, m, J, "fight", timers, max_frames=21000)
        J({"ev": "SURVIVE_DONE", **surv})
    else:
        surv = survive_phase(p, m, J, "fight", timers, max_frames=3000)
        J({"ev": "SURVIVE_DONE_PARTIAL", **surv})

    # verdict
    s12 = rear["dmg"].get(12, [])
    k12 = [k for k in rear["kills"] if k["slot"] == 12]
    if rear["stop"] == "ALL_CLEAR" and surv and surv.get("released"):
        verdict = "CAUSAL_ENCOUNTER_GATED_RELEASED"
    elif rear["stop"] == "ALL_CLEAR" and surv and \
            surv.get("rollover") is not None:
        verdict = "ALL_CLEAR_ROLLOVER_HELD"
    elif rear["stop"] == "ALL_CLEAR":
        verdict = "ALL_CLEAR_SURVIVAL_SHORT"
    elif k12:
        verdict = "REAR_KILLED_NO_FULL_CLEAR"
    elif s12:
        verdict = "REAR_REACHABLE_NOT_KILLED"
    else:
        verdict = "REAR_UNREACHABLE"
    rep = {"schema": "ps1play-r10-rear/1", "verdict": verdict,
           "state": STATE, "rear": rear, "survive": surv,
           "restores_disclosed": restores, "continues_used": 0,
           "slot12_dmg_events": len(s12), "slot12_killed": bool(k12),
           "frames": p.core.frames_run,
           "wall_s": round(time.time() - t0, 1)}
    json.dump(rep, open(os.path.join(OUTDIR, "report.json"), "w"),
              indent=1)
    J({"ev": "run_end", "verdict": verdict})
    log("done:", verdict, "slot12 dmg:", len(s12),
        "kills:", [k["slot"] for k in rear["kills"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
