#!/usr/bin/env python3
"""r40t4_patient.py — R40 Task 4 (BOOT 4 of the disclosed cap 4,
ledger amended 3->4 BEFORE the run).

The patient campaign: ONE 1200-chunk run of the shipped v3.1 policy
(queue priority + arrival-band lead gate) from r38_ckpt.

Why (the window-size hypothesis, disclosed in the ledger amendment):
  - each treatment run is CKPT-independent (the chopper hp resets to
    300) so the run itself must land 3 connects for the kill;
  - boot-3 measured the connect machinery working (the FIRST early
    connect c99->c100; 11/15 throws in-arrival-band) but the rate is
    ~1/15 throws with the bail cooldown suspending ~50% of chunks;
  - 300 chunks = ~15 throws = ~1 connect; 1200 chunks = ~45+ throws;
  - the pin holds indefinitely in-game (the pending queue re-arms;
    the release condition IS the queue clear), the rain-hop kept the
    player alive with 0 deaths across boots 1-3, and grenades had
    headroom (final 8) - waiting is free and safe.
Protocol deviation disclosed pre-run: RUNS=1 (the release predicate,
not the determinism pair, is the informative oracle here).

Success oracles: verified hp_a4 drops; CHOPPER_DEAD (hp_a4 300 -> 0);
the section release transitions; the mission-end latch / banner
predicate. +0x8E is NEVER in any oracle.
"""
from __future__ import annotations

import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _REPO + "/scripts")
        sys.path.insert(0, _REPO)

import r39t1_baseline as t1                       # noqa: E402
import ps1play.agent.combat as combat             # noqa: E402
import r40t1_census as c1                         # noqa: E402
from issue4_controller import boot_to_demo        # noqa: E402

SCRATCH = c1.SCRATCH
CKPT = c1.CKPT
RUNS = 1
CHUNKS = 1200                                     # the patient window


def log(*a):
    print("[r40-t4]", *a, file=sys.stderr, flush=True)


def main():
    n = c1.amend_ledger(
        "BOOT4: the patient 1200-chunk v3.1 run from r38_ckpt (the "
        "window-size hypothesis; RUNS=1 disclosed pre-run)",
        script="r40t4_patient.py")
    if n > 4:
        raise SystemExit("BOOT CAP EXCEEDED")
    tr_path = os.path.join(SCRATCH, "r40_boot4.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START",
       "commit": os.popen("git -C %s rev-parse HEAD"
                          % _REPO).read().strip(),
       "policy": "R40 v3.1 (queue priority + arrival-band lead gate)",
       "protocol": "1 run x 1200 chunks (the patient campaign)",
       "ts": time.strftime("%FT%TZ", time.gmtime())})

    p = boot_to_demo()
    m = p.mem
    p.load_state(CKPT)
    if not t1.alive(m):
        raise SystemExit("r38_ckpt not alive after restore")

    continues = {}
    tlog = t1.ThrowLog(J, "PATIENT")
    res = c1.run_census_arm(p, m, J, "PATIENT", CHUNKS, tlog,
                            lambda: combat.CombatPolicy(
                                queue_priority=True),
                            continues=continues)
    res["hp_drops"] = tlog.hits
    res["throws"] = len(tlog.throws)
    res["continues"] = continues.get("PATIENT", 0)

    comp = {
        "legacy_300": {"throws": 13, "connects": 1, "score": 5701},
        "v31_300": {"throws": 15, "connects": 1, "score": 4200},
        "v31_1200": {"throws": res["throws"], "hp_drops": res["hp_drops"],
                     "connects": res["pol_stats"].get("aa_connect", 0),
                     "kill_connects":
                         res["pol_stats"].get("aa_kill_connect", 0),
                     "bails": res["pol_stats"].get("aa_bail", 0),
                     "takeovers":
                         res["pol_stats"].get("aa_priority_takeover", 0),
                     "outcome": res["outcome"],
                     "end_chunk": res["end_chunk"],
                     "deaths": res["deaths"],
                     "continues": res.get("continues", 0),
                     "score_final": res["score_final"],
                     "final": res["final"]}}
    J({"ev": "COMPARISON", **comp})

    with open(os.path.join(SCRATCH, "r40_boot4_report.json"),
              "w") as f:
        json.dump({"schema": "ps1play.r40-boot4/1",
                   "generated": time.strftime("%FT%TZ", time.gmtime()),
                   "commit": os.popen("git -C %s rev-parse HEAD"
                                      % _REPO).read().strip(),
                   "checkpoint": CKPT, "runs": results_barrier(res),
                   "comparison": comp}, f, indent=1, default=str)
    jf.close()
    log("report -> scratch/r40/r40_boot4_report.json")
    log(f"PATIENT: {res['outcome']} c={res['end_chunk']} "
        f"throws={res['throws']} connects="
        f"{res['pol_stats'].get('aa_connect', 0)} "
        f"kill={res['pol_stats'].get('aa_kill_connect', 0)} "
        f"score={res['score_final']}")
    return 0


def results_barrier(res):
    return [{"arm": res["arm"], "outcome": res["outcome"],
             "end_chunk": res["end_chunk"], "throws": res["throws"],
             "pol_stats": res["pol_stats"],
             "score_final": res["score_final"],
             "final": res["final"]}]


if __name__ == "__main__":
    sys.exit(main())
