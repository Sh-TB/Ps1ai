#!/usr/bin/env python3
"""r38t3_aa_trial.py — R38 phase AA-TRIAL (boot 3; ledger cap amended
3->4 BEFORE the run, disclosed).

Matched live trial of the PATCHED shipped policy (the R38 aa_kill
rule) against the PRE-PATCH baseline recorded in trialA1/A2 (same
checkpoint r38_ckpt, same 15f micro-chunk budget, deterministic core).

Hypothesis (from trialA1 evidence): the truck died but the chopper
(slot 4, st 0xAA94/0xABDC, hp_a4 300) kept the pending-entity queue
non-empty -> pin cycled forever -> mission-timer restart at c268.
With the session-3 J1 hop+lob wired in, the chopper should die
(aa_connect >= 2, hp_a4 300 -> 0), the queue should clear, and the
run should reach the (0,8)->(0xC,9) pre-banner path or the 0xC
MISSION 1 banner BEFORE the timer restart.

Success oracle: score events + walker 0xC / pre-banner + banner PNG.
+0x8E never in the oracle.
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

import r38t2_trials as t2                                # noqa: E402
from issue4_controller import boot_to_demo               # noqa: E402

SCRATCH = t2.SCRATCH
COMMIT_EVID = t2.COMMIT_EVID


def log(*a):
    print("[r38-aa]", *a, file=sys.stderr, flush=True)


def main():
    runs_n = 2
    chunks = 480
    # ---- ledger amendment BEFORE boot (disclosed) ----
    with open(t2.LEDGER) as f:
        led = json.load(f)
    if led.get("cap", 3) < 4:
        led["cap"] = 4
        led.setdefault("amendments", []).append(
            {"ts": time.strftime("%FT%TZ", time.gmtime()),
             "change": "cap 3->4",
             "reason": "R38 aa-kill live matched trial needs boot 3; "
                       "amended BEFORE the run per the boot-cap "
                       "convention"})
        with open(t2.LEDGER, "w") as f:
            json.dump(led, f, indent=1)
        log("ledger cap amended 3->4 (disclosed, pre-run)")
    n = t2.amend_ledger("AA-TRIAL: boot_to_demo -> patched policy x2 "
                        "from r38_ckpt")
    with open(t2.LEDGER) as f:
        cap = json.load(f).get("cap", 4)
    if n > cap:
        raise SystemExit("BOOT CAP EXCEEDED")
    p = boot_to_demo()
    m = p.mem
    p.load_state(t2.CKPT)
    if not t2.alive(m):
        raise SystemExit("r38_ckpt not alive after restore")

    jf = open(os.path.join(SCRATCH, "aa_trials.jsonl"), "w")
    results = [t2.run_trial(p, m, f"trialAA{r + 1}", "policy",
                            chunks, jf) for r in range(runs_n)]
    jf.close()

    base = json.load(open(os.path.join(SCRATCH, "trial_report.json")))
    baseA = [r for r in base["runs"] if r["arm"] == "policy"]
    rep = {"schema": "ps1play.r38-aa-trial/1",
           "generated": time.strftime("%FT%TZ", time.gmtime()),
           "commit_head": os.popen(
               "git -C %s rev-parse HEAD" % _REPO).read().strip(),
           "checkpoint": t2.CKPT,
           "policy_change": "aa_kill mode (J1 hop+UP-lob recipe) in "
                            "ps1play/agent/combat.py",
           "baseline": [{"tag": r["tag"], "outcome": r["outcome"],
                         "end_chunk": r["end_chunk"],
                         "score_final": r["score_final"],
                         "deaths": r["deaths"]} for r in baseA],
           "treatment": results,
           "oracle": "score events + walker 0xC / pre-banner (0,8)->"
                     "(0xC,9) + banner PNG; +0x8E excluded (R38 rule)"}
    out = os.path.join(SCRATCH, "aa_trial_report.json")
    with open(out, "w") as f:
        json.dump(rep, f, indent=1)
    with open(os.path.join(COMMIT_EVID, "r38_aa_trial_report.json"),
              "w") as f:
        json.dump({"schema": rep["schema"], "generated": rep["generated"],
                   "commit_head": rep["commit_head"],
                   "checkpoint": rep["checkpoint"],
                   "policy_change": rep["policy_change"],
                   "baseline": rep["baseline"],
                   "treatment": [
                       {k: r[k] for k in ("tag", "outcome", "end_chunk",
                                          "deaths", "score_final",
                                          "truck_a4_min",
                                          "pol_stats")}
                       for r in results]}, f, indent=1)
    log("report ->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
