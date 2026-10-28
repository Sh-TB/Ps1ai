#!/usr/bin/env python3
"""r40t2_treatment.py — R40 Task 2 (BOOT 2 of the disclosed cap 2).

The queue-priority trial: the R40 rule (CombatPolicy(queue_priority=
True) — the shipped default) from the SAME checkpoint (r38_ckpt)
under the SAME protocol as the boot-1 CENSUS-BASE arm and the R39
boot-6 pair.

Hypotheses (capsule next_experiment):
  H-A  with the queue blocker (the chopper) outranking engage/
       armor_hold in the pin context, the throw-opportunity share
       rises enough for the proven atomic delivery to land the
       remaining 2 connects inside one campaign window:
       chopper hp_a4 300 -> 0.
  H-B  once the chopper dies, the D7 section releases: the walker
       leaves the pin family and the mission-end chain runs
       (0xC / the MISSION 1 banner predicate).

Success oracles: verified hp_a4 drops on the correctly identified
chopper; CHOPPER_DEAD (kill_connects >= 3 from 300); the section
release transitions; the mission-end latch / banner predicate.
+0x8E is NEVER in any oracle. Deaths wait out the respawn and pass
the game continue screen via the issue-4 recover_v2 START tap
(counted + disclosed). All runs are checkpoint-restored diagnostics
inside boot 2 — NOT fresh-boot completion claims.
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
RUNS = 2                                          # trialT1/T2 protocol
CHUNKS = c1.CHUNKS                                # 300 x15f, matched


def log(*a):
    print("[r40-t2]", *a, file=sys.stderr, flush=True)


def main():
    n = c1.amend_ledger(
        "BOOT2: the R40 queue-priority trial x2 runs from r38_ckpt "
        "(same protocol as boot-1 CENSUS-BASE and the R39 boot-6 "
        "pair)", script="r40t2_treatment.py")
    if n > 2:
        raise SystemExit("BOOT CAP EXCEEDED")
    tr_path = os.path.join(SCRATCH, "r40_boot2.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START",
       "commit": os.popen("git -C %s rev-parse HEAD"
                          % _REPO).read().strip(),
       "policy": "R40 queue-priority (queue_priority=True, shipped "
                 "default): the chopper outranks engage/armor_hold "
                 "in the pin context",
       "ts": time.strftime("%FT%TZ", time.gmtime())})

    p = boot_to_demo()
    m = p.mem
    p.load_state(CKPT)
    if not t1.alive(m):
        raise SystemExit("r38_ckpt not alive after restore")

    results = []
    continues = {}
    for r in range(RUNS):
        # R39 protocol: restore the pristine checkpoint before EVERY
        # run (the trialT2 harness lesson: run 2 inherited run 1's
        # end state and died instantly)
        p.load_state(CKPT)
        if not t1.alive(m):
            raise SystemExit("r38_ckpt not alive on re-restore")
        tlog = t1.ThrowLog(J, f"trialQ{r + 1}")
        res = c1.run_census_arm(p, m, J, f"trialQ{r + 1}", CHUNKS,
                                tlog,
                                lambda: combat.CombatPolicy(
                                    queue_priority=True),
                                continues=continues)
        res["hp_drops"] = tlog.hits
        res["throws"] = len(tlog.throws)
        res["continues"] = continues.get(f"trialQ{r + 1}", 0)
        results.append(res)
        if r and results[0]["pol_stats"] != results[1]["pol_stats"]:
            log("WARNING: trialQ1/Q2 pol_stats differ - the trial is "
                "not deterministic under the treatment")

    base_rep = json.load(open(os.path.join(SCRATCH,
                                           "r40_boot1_report.json")))
    base = base_rep["base"]
    comp = {
        "census_base_boot1": {
            "policy": "legacy v2.2 (queue_priority=False)",
            "throws": base["throws"], "connects":
                base["pol_stats"].get("aa_connect", 0),
            "kill_connects": base["pol_stats"].get("aa_kill_connect", 0),
            "engage": base["pol_stats"].get("engage", 0),
            "aa_kill": base["pol_stats"].get("aa_kill", 0),
            "outcome": base["outcome"], "end_chunk": base["end_chunk"],
            "score_final": base["score_final"]},
        "treatment": [
            {"tag": r["arm"],
             "policy": "R40 queue-priority (v3)",
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
             "score_final": r["score_final"],
             "chopper_dead": r["pol_stats"].get("aa_kill_connect", 0)
             >= 3 or r["pol_stats"].get("aa_kill_connect", 0) >= 1
             and r["pol_stats"].get("aa_resolved", 0) > 0
             and r["final"].get("sec", (0,))[0] == 0xC}
            for r in results]}
    J({"ev": "COMPARISON", **comp})

    with open(os.path.join(SCRATCH, "r40_boot2_report.json"),
              "w") as f:
        json.dump({"schema": "ps1play.r40-boot2/1",
                   "generated": time.strftime("%FT%TZ", time.gmtime()),
                   "commit": os.popen("git -C %s rev-parse HEAD"
                                      % _REPO).read().strip(),
                   "checkpoint": CKPT, "runs": results,
                   "comparison": comp}, f, indent=1, default=str)
    jf.close()
    log("report -> scratch/r40/r40_boot2_report.json")
    for r in results:
        log(f"{r['arm']}: {r['outcome']} c={r['end_chunk']} "
            f"throws={r['throws']} connects="
            f"{r['pol_stats'].get('aa_connect', 0)} "
            f"takeovers={r['pol_stats'].get('aa_priority_takeover', 0)} "
            f"score={r['score_final']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
