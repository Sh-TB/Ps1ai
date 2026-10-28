#!/usr/bin/env python3
"""r39t2_treatment.py — R39 Task 5+6 (BOOT 2 of the disclosed cap 2).

Treatment verification: the R39 positioning/atomic-delivery sub-rule
(ps1play/agent/combat.py aa_kill v2) from the SAME checkpoint
(r38_ckpt) under the SAME protocol as the Boot-1 BASE arm.

Hypotheses (from Boot-1 evidence):
  H-A  the atomic delivery + geometry gate raises the connect rate
       well above the R38/BASE ~1/10 (target: >= 3 verified hp_a4
       drops = the chopper killed from 300).
  H-B  once the chopper (the last observed pending-queue entity)
       dies, the D7 section releases: the walker leaves the pin
       family and the mission-end chain runs (0xC / banner).

Success oracles (Task 2/6): verified hp_a4 drops on the correctly
identified chopper; CHOPPER_DEAD; section release transitions; the
mission-end latch / MISSION 1 banner predicate. +0x8E is NEVER in any
oracle. All runs are checkpoint-restored diagnostics inside boot 2
(labeled as such) — NOT fresh-boot completion claims.
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

import r39t1_baseline as t1                               # noqa: E402
import ps1play.agent.combat as combat                     # noqa: E402
from issue4_controller import boot_to_demo                # noqa: E402

SCRATCH = t1.SCRATCH
CKPT = t1.CKPT
RUNS = 2
CHUNKS = 300                     # matched to the Boot-1 BASE protocol


def log(*a):
    print("[r39-t2]", *a, file=sys.stderr, flush=True)


def main():
    n = t1.amend_ledger("BOOT2: treatment trial - the R39 aa_kill v2 "
                        "sub-rule x2 runs from r38_ckpt (same "
                        "protocol as the Boot-1 BASE arm)",
                        script="r39t2_treatment.py")
    if n > 6:
        raise SystemExit("BOOT CAP EXCEEDED")
    tr_path = os.path.join(SCRATCH, "r39_boot2.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START", "commit": os.popen(
        "git -C %s rev-parse HEAD" % _REPO).read().strip(),
       "policy": "aa_kill v2 (atomic delivery + geometry gate + "
                 "grounded start + positioning walk)",
       "ts": time.strftime("%FT%TZ", time.gmtime())})

    p = boot_to_demo()
    m = p.mem
    p.load_state(CKPT)
    if not t1.alive(m):
        raise SystemExit("r38_ckpt not alive after restore")

    results = []
    continues = {}
    for r in range(RUNS):
        # R38 protocol: restore the pristine checkpoint before EVERY
        # run (the trialT2 harness bug: run 2 inherited run 1's end
        # state and died instantly)
        p.load_state(CKPT)
        if not t1.alive(m):
            raise SystemExit("r38_ckpt not alive on re-restore")
        tlog = t1.ThrowLog(J, f"trialT{r + 1}")
        res = t1.run_policy_arm(p, m, J, f"trialT{r + 1}", CHUNKS,
                                tlog, anchor_state=CKPT,
                                continues=continues)
        res["hp_drops"] = tlog.hits
        res["throws"] = len(tlog.throws)
        res["continues"] = continues.get(f"trialT{r + 1}", 0)
        results.append(res)
        # determinism check between runs
        if r and results[0]["pol_stats"] != results[1]["pol_stats"]:
            log("WARNING: trialT1/T2 pol_stats differ - the trial is "
                "not deterministic under the treatment")

    # ---- treatment vs baseline comparison ----
    base_rep = json.load(open(os.path.join(SCRATCH,
                                           "r39_boot1_report.json")))
    base = base_rep["base"]
    comp = {
        "baseline_BASE_boot1": {
            "throws": 11, "connects": base["pol_stats"].get(
                "aa_connect", 0),
            "outcome": base["outcome"],
            "end_chunk": base["end_chunk"],
            "score_final": base["score_final"]},
        "treatment": [
            {"tag": r["arm"], "throws": r["throws"],
             "hp_drops": r["hp_drops"],
             "connects": r["pol_stats"].get("aa_connect", 0),
             "kill_connects": r["pol_stats"].get("aa_kill_connect", 0),
             "misses": r["pol_stats"].get("aa_miss", 0),
             "bails": r["pol_stats"].get("aa_bail", 0),
             "outcome": r["outcome"], "end_chunk": r["end_chunk"],
             "deaths": r["deaths"], "continues": r.get("continues", 0),
             "score_final": r["score_final"],
             "chopper_dead": r["pol_stats"].get("aa_kill_connect", 0)
             > 0}
            for r in results]}
    J({"ev": "COMPARISON", **comp})

    with open(os.path.join(SCRATCH, "r39_boot2_report.json"), "w") as f:
        json.dump({"schema": "ps1play.r39-boot2/1",
                   "generated": time.strftime("%FT%TZ", time.gmtime()),
                   "commit": os.popen("git -C %s rev-parse HEAD"
                                      % _REPO).read().strip(),
                   "checkpoint": CKPT, "runs": results,
                   "comparison": comp}, f, indent=1, default=str)
    jf.close()
    log("report -> scratch/r39/r39_boot2_report.json")
    for r in results:
        log(f"{r['arm']}: {r['outcome']} c={r['end_chunk']} "
            f"throws={r['throws']} connects="
            f"{r['pol_stats'].get('aa_connect', 0)} "
            f"score={r['score_final']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
