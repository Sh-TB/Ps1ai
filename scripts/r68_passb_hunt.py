#!/usr/bin/env python3
"""r68_passb_hunt.py — R68 boot 3: the stage-2 pass-B hunt (the
capsule lever's third +500 attempt).

THE R68 METHOD LINE verbatim: "experiment-track: ONE restore-only
boot replaying the R66 pass-B tap sequence VERBATIM (the corridor
gate as committed in r66t1, not the r67 amendment-G variant) for the
third +500 attempt; the zero-overlap test re-runs on any new
capture".

What "VERBATIM" means here, mechanically:
  * the runner IS r66t1_payframe_destarve.py's do_stage2(only="b")
    — the R66 pass-B code path itself (the de-starve arm armed, the
    R52 pay-frame union-net telemetry, TAP_FRAMES=3 + TAIL=20,
    CONNECT_GOAL=4 KILL_GOAL=1 — the R66 stop rule);
  * the corridor gate is r66t1's corridor_occupants_r66 /
    pick_target_r66 AS COMMITTED (combat.CORPSE_ST = {0x4BE4,
    0x5CC8} — combat.py is untouched, so the amendment-G 0x5B0C
    exclusion is NOT applied — the exact R66 tap-order posture);
  * the frontiers are the R68-rebuilt r66_frontier_a/b (boot 2; the
    byte-exact 6-for-6 rebuild precedent — the tap replay assumes
    the R66 posture; the px values are cross-checked against the
    R66/R67 records and any divergence is disclosed).

The +500 counter: scratch/r68/pay500_counter.json — updated
ATOMICALLY by the post-pass analysis (r68_analysis_correct.py) when
a verified +500 lands (the R52 ledger-counting rule; the r67t1
in-process update is the R67 variant, the post-hoc update is
disclosed here).

Evidence: data/games/SLUS-01212/truck_evidence/r68/
          r68_boot3_s2b_report.json + r68_boot3_s2b.jsonl
"""
from __future__ import annotations

import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import r66t1_payframe_destarve as r66t1            # noqa: E402

EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r68")
SCRATCH = os.path.join(_REPO, "scratch", "r68")
r66t1.EVID = EVID
r66t1.SCRATCH = SCRATCH
r66t1.PNGDIR = os.path.join(SCRATCH, "pngs")
import r47t1_singletap_taps as R47T                # noqa: E402
R47T.PNGDIR = r66t1.PNGDIR

LEDGER = os.path.join(SCRATCH, "boots_used.json")
COUNTER = os.path.join(SCRATCH, "pay500_counter.json")


def log(*a):
    print("[r68-hunt]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason):
    with open(LEDGER) as f:
        led = json.load(f)
    if int(led.get("count", 0)) + 1 > int(led.get("cap", 0)):
        raise SystemExit("BOOT CAP EXCEEDED (r68 ledger)")
    led["count"] = int(led.get("count", 0)) + 1
    led["log"].append({"n": led["count"],
                       "ts": time.strftime("%FT%TZ", time.gmtime()),
                       "script": "r68_passb_hunt.py",
                       "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']}/{led['cap']} ({reason})")
    return led["count"]


def bump_counter(dscores):
    """Atomic +500 counter update (the R52 ledger-counting rule)."""
    os.makedirs(SCRATCH, exist_ok=True)
    if not os.path.exists(COUNTER):
        with open(COUNTER, "w") as f:
            json.dump({"pay500": 0, "log": []}, f, indent=1)
    with open(COUNTER) as f:
        c = json.load(f)
    n500 = sum(1 for d in dscores if d == 500)
    if n500:
        c["pay500"] = int(c.get("pay500", 0)) + n500
        c.setdefault("log", []).append({
            "ts": time.strftime("%FT%TZ", time.gmtime()),
            "source": "r68_passb_hunt.py post-pass analysis",
            "n500": n500})
        tmp = COUNTER + ".tmp"
        with open(tmp, "w") as f:
            json.dump(c, f, indent=1)
        os.replace(tmp, COUNTER)
    log(f"pay500 counter: {c.get('pay500')} (+{n500} this pass)")
    return c


def main():
    n = amend_ledger(
        "BOOT stage-2 pass B (the INSTRUMENTED PAY-FRAME DE-STARVE "
        "hunt, restore-only): the R66 pass-B tap sequence VERBATIM "
        "(the corridor gate as committed in r66t1 — combat.CORPSE_ST "
        "{0x4BE4,0x5CC8}, the amendment-G exclusion NOT applied — "
        "the trajectory-sensitivity lesson) on the R68-rebuilt "
        "frontier_b for the THIRD +500 attempt.  Goals CONNECT=4 "
        "KILL=1 (the R66 stop rule).  The +500 counter updates "
        "post-pass (disclosed).")
    tag = time.strftime("r68_s2b_%H%M%S")
    stem = f"r68_boot{n}_s2b"
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    tr_path = os.path.join(EVID, f"{stem}.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START",
       "commit": os.popen("git -C %s rev-parse HEAD"
                          % _REPO).read().strip(),
       "stage": "2b",
       "gate_disclosure":
           "the R66 gate VERBATIM (combat.CORPSE_ST = "
           "{0x4BE4, 0x5CC8} — the amendment-G 0x5B0C exclusion "
           "NOT applied; combat.py untouched this round)",
       "frontier_expectation":
           "the R68-rebuilt frontier_b expected byte-identical to "
           "the R66 original (the 6-for-6 precedent); the restore "
           "px cross-checked against the R66/R67 records",
       "lineage": "TAINTED frontier postures (restore-only taps)",
       "oracle": "walker words + verified score gains + alive "
                 "0x0EE518; never +0x8E (the union net = disclosed "
                 "exploratory telemetry)",
       "ts": time.strftime("%FT%TZ", time.gmtime())})
    try:
        rc = r66t1.do_stage2(J, tag, stem, only="b")
    finally:
        jf.close()
    # ---- the post-pass +500 scan (the atomic counter update) -------
    dscores = []
    try:
        with open(tr_path) as f:
            for line in f:
                ev = json.loads(line)
                if ev.get("ev") != "TAP":
                    continue
                dscores.append(ev.get("score_delta"))
    except Exception as e:                                  # noqa: BLE001
        log("counter scan failed:", repr(e)[:120])
    bump_counter(dscores)
    log(f"report -> {EVID}/{stem}_report.json")
    return rc


if __name__ == "__main__":
    sys.exit(main())
