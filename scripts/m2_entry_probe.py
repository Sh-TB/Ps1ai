#!/usr/bin/env python3
"""m2_entry_probe.py — Issue #5 session 5: what follows the MISSION 1
banner under no-input vs START (Mission 2 entry question).

Context (session-3 evidence): START on the banner went
START -> NOW LOADING -> SNK title (an attract/exit path).  Session-4
left Mission 2 entry as the open follow-up.  This probe OBSERVES,
with real inputs only:

  phase W  after the banner PASS: 900f no-input, snapshot+PNG every
           150f — does the banner auto-advance?
  phase S  one START tap + 300f, x3 — the characterized flow.

Every screen change is recorded honestly as OBSERVED; no claim of
Mission 2 gameplay is made unless the walking player is proven
(flags 0xFF + px advancing under RIGHT).
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

from ps1play import labconfig
from issue4_controller import boot
import ps1play.agent.combat as combat
from e2e_policy_trial import (snap, alive, png, px_of, run_once,
                              EVID, PLAYER_X)


def log(*a):
    print("[m2]", *a, file=sys.stderr, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=2600)
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    tag = f"m2probe_{time.strftime('%H%M%S')}"
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    J({"ev": "boot", "firmware": fw, **snap(m)})
    rec = run_once(p, m, J, tag, args.chunks, control=False)
    J({"ev": "e2e_result", **{k: rec[k] for k in
                              ("outcome", "end_chunk", "deaths")}})
    log("e2e:", rec["outcome"], "c=", rec["end_chunk"])
    if rec["outcome"] != "MISSION_BANNER":
        log("no banner — probe aborted")
        return 1

    # ---------- phase W: no-input watch ----------
    prev_px = px_of(m)
    phase_events = []
    for w in range(6):
        p.core.run(150, set())
        s = snap(m)
        ev = {"ev": "W", "step": w, **s, "px_moved":
              round(px_of(m) - prev_px, 1)}
        J(ev)
        phase_events.append(ev)
        png(p, f"W{w}", tag)
        prev_px = px_of(m)
        log(f"W{w}: px={s['px']} sec={s['sec']} flags={s['flags']} "
            f"score={s['score']}")

    # ---------- phase S: START taps ----------
    for k in range(3):
        p.core.run(12, {"START"})
        p.core.run(300, set())
        s = snap(m)
        J({"ev": "S", "tap": k + 1, **s})
        png(p, f"S{k + 1}", tag)
        log(f"S{k + 1}: px={s['px']} sec={s['sec']} "
            f"flags={s['flags']} score={s['score']}")
        if s["flags"] == 0xFF and s["px"] > 60.0:
            # gameplay-looking again: probe RIGHT ownership
            p0 = px_of(m)
            p.core.run(90, {"RIGHT"})
            s2 = snap(m)
            moved = round(px_of(m) - p0, 1)
            J({"ev": "RIGHT_PROBE", "moved_px": moved, **s2})
            png(p, f"S{k + 1}_right", tag)
            log(f"RIGHT probe: moved {moved}px flags={s2['flags']}")
            if moved > 8.0 and s2["flags"] == 0xFF:
                J({"ev": "M2_GAMEPLAY_CANDIDATE", **s2})
                log("M2 gameplay candidate — px advancing")
                break

    rep = {"schema": "issue5/m2-entry-probe/1",
           "tag": tag, "e2e": {k: rec[k] for k in
                               ("outcome", "end_chunk", "deaths")},
           "wall_s": round(time.time() - t0, 1),
           "frames": p.core.frames_run}
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    J({"ev": "done", **rep})
    jf.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
