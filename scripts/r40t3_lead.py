#!/usr/bin/env python3
"""r40t3_lead.py — R40 Task 3 (BOOT 3 of the disclosed cap 3, ledger
amended 2->3 BEFORE the run with the boot-2 negative as the reason).

The v3.1 treatment: queue priority (v3, boot-2) + the ARRIVAL-BAND
LEAD GATE (v3.1). Boot-2's honest negative localized the failure:
the takeover fixed WHO gets the mode (48 takeovers, aa_kill 76->84)
but the connect geometry stayed wrong — the v2.2 gate throws at the
chopper's CURRENT position while the census/frame evidence shows it
patrols at ~1.5 px/f and the lob crosses its altitude in ~12-28f.
v3.1 gates the throw on dx_arr = dx + ch_v * AA_LEAD_T (the chopper's
PREDICTED position at arrival; parked hovers reduce to v2.2 exactly).

Hypotheses:
  H-A  the arrival gate turns the boot-2 scatter (0/12, release dx
       5.6-54.7 both signs) into in-band-at-arrival throws: >= 2
       verified hp_a4 drops on the chopper per 300-chunk run.
  H-B  with 3 connects from 300 the chopper dies (hp_a4 300 -> 0)
       and the D7 section releases (the mission-end chain).

Success oracles: verified hp_a4 drops (the ThrowLog); CHOPPER_DEAD;
section release; the mission-end latch / banner predicate. +0x8E is
NEVER in any oracle. Checkpoint-restored diagnostics inside boot 3 —
NOT fresh-boot completion claims.
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
RUNS = 2                                          # the treatment-pair
CHUNKS = c1.CHUNKS                                # 300 x15f, matched


def log(*a):
    print("[r40-t3]", *a, file=sys.stderr, flush=True)


def main():
    n = c1.amend_ledger(
        "BOOT3: the v3.1 lead-gate treatment pair from r38_ckpt "
        "(queue priority + the arrival-band gate; the boot-2 "
        "current-position scatter is the disclosed reason)",
        script="r40t3_lead.py")
    if n > 3:
        raise SystemExit("BOOT CAP EXCEEDED")
    tr_path = os.path.join(SCRATCH, "r40_boot3.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START",
       "commit": os.popen("git -C %s rev-parse HEAD"
                          % _REPO).read().strip(),
       "policy": "R40 v3.1: queue_priority takeover + arrival-band "
                 "lead gate (dx_arr = dx + ch_v*20, band [10,35])",
       "ts": time.strftime("%FT%TZ", time.gmtime())})

    p = boot_to_demo()
    m = p.mem
    p.load_state(CKPT)
    if not t1.alive(m):
        raise SystemExit("r38_ckpt not alive after restore")

    results = []
    continues = {}
    for r in range(RUNS):
        p.load_state(CKPT)
        if not t1.alive(m):
            raise SystemExit("r38_ckpt not alive on re-restore")
        tlog = t1.ThrowLog(J, f"trialL{r + 1}")
        res = c1.run_census_arm(p, m, J, f"trialL{r + 1}", CHUNKS,
                                tlog,
                                lambda: combat.CombatPolicy(
                                    queue_priority=True),
                                continues=continues)
        res["hp_drops"] = tlog.hits
        res["throws"] = len(tlog.throws)
        res["continues"] = continues.get(f"trialL{r + 1}", 0)
        results.append(res)
        if r and results[0]["pol_stats"] != results[1]["pol_stats"]:
            log("WARNING: trialL1/L2 pol_stats differ - not "
                "deterministic under v3.1")

    base_rep = json.load(open(os.path.join(SCRATCH,
                                           "r40_boot1_report.json")))
    base = base_rep["base"]
    comp = {
        "census_base_boot1": {
            "policy": "legacy v2.2 (queue_priority=False)",
            "throws": base["throws"],
            "connects": base["pol_stats"].get("aa_connect", 0),
            "engage": base["pol_stats"].get("engage", 0),
            "aa_kill": base["pol_stats"].get("aa_kill", 0),
            "outcome": base["outcome"], "end_chunk": base["end_chunk"],
            "score_final": base["score_final"]},
        "treatment_v31": [
            {"tag": r["arm"], "policy": "R40 v3.1 (priority+lead)",
             "throws": r["throws"], "hp_drops": r["hp_drops"],
             "connects": r["pol_stats"].get("aa_connect", 0),
             "kill_connects": r["pol_stats"].get("aa_kill_connect", 0),
             "misses": r["pol_stats"].get("aa_miss", 0),
             "bails": r["pol_stats"].get("aa_bail", 0),
             "takeovers": r["pol_stats"].get("aa_priority_takeover", 0),
             "engage": r["pol_stats"].get("engage", 0),
             "aa_kill": r["pol_stats"].get("aa_kill", 0),
             "outcome": r["outcome"], "end_chunk": r["end_chunk"],
             "deaths": r["deaths"], "continues": r.get("continues", 0),
             "score_final": r["score_final"]}
            for r in results]}
    J({"ev": "COMPARISON", **comp})

    with open(os.path.join(SCRATCH, "r40_boot3_report.json"),
              "w") as f:
        json.dump({"schema": "ps1play.r40-boot3/1",
                   "generated": time.strftime("%FT%TZ", time.gmtime()),
                   "commit": os.popen("git -C %s rev-parse HEAD"
                                      % _REPO).read().strip(),
                   "checkpoint": CKPT, "runs": results,
                   "comparison": comp}, f, indent=1, default=str)
    jf.close()
    log("report -> scratch/r40/r40_boot3_report.json")
    for r in results:
        log(f"{r['arm']}: {r['outcome']} c={r['end_chunk']} "
            f"throws={r['throws']} connects="
            f"{r['pol_stats'].get('aa_connect', 0)} "
            f"kill={r['pol_stats'].get('aa_kill_connect', 0)} "
            f"score={r['score_final']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
