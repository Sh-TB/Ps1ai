#!/usr/bin/env python3
"""r43_capsule_update.py — R43 close-out: append the R43 events to the
MSX knowledge capsule and replace next_experiment with the R44 lever.

Honesty rules honored: every event carries provenance; the primary
negative (the INTERACTIVE M2 entry NOT claimable this round) is
recorded, not smoothed over; the boot-4 village-stall hypothesis is
REVISED by boot-5's evidence; the harness lessons (stale-stat gate,
silent restart hole) are recorded as reusable guards; +0x8E never in
any oracle.
"""
import json
import os

_REPO = "/home/z/my-project/ps1ai"
CAPSULE = os.path.join(_REPO, "data", "knowledge", "msx", "capsule.json")

EVID = ("data/games/SLUS-01212/truck_evidence/r43/ "
        "(boots_used.json cap 7/7 + r43_boot2_leak_report + "
        "r43_boot5/6_s1/7_s2 reports+jsonl; scratch/r43/pngs local-only)")

NEW_EVENTS = [
    {
        "what": "R43 premise staleness (disclosed): r38_ckpt AND "
                "r42_postkill are ABSENT from emu/ws/states/ (a "
                "filesystem rollback — only Oct-20 states survived; the "
                "same class as the documented mspsx_lic rollback). The "
                "round rebuilt from the surviving session-5 anchor "
                "issue5_m1_start (M1 start px~26). Ledger cap 7/7 with "
                "corrected filings disclosed: entries 1+2 = real boots "
                "aborted at rebuild c3 by the r42t1 deep-posture guard "
                "(px<700) copied verbatim onto a px~26 start anchor; "
                "entry 3 = filed-but-died (external kill pre-boot); "
                "entry 4 = real boot killed mid-campaign.",
        "status": "OBSERVED",
        "provenance": {"evidence": EVID,
                       "source": "R43 ledger entries 1-4 (corrected-"
                                 "filings precedent, R40)"}},
    {
        "what": "R43 boot-5 ROOT CAUSE + capability revision: (a) the "
                "r42t1 resolve gate (aa_resolved>=1) is STALE-STAT-"
                "UNSAFE across mission restarts — after 2 deaths the "
                "mission restarted (px back to ~24) and the gate fired "
                "on the policy's surviving stat, saving a RESTART "
                "posture (RESOLVED at c167, px=24.5, flags=75, score "
                "4501) as the postkill; r42t1 itself was safe only "
                "because its rebuild never died (deaths=0). (b) The "
                "boot-4 'village stall' hypothesis is REVISED: the "
                "current (queue_priority) policy PASSED the village "
                "from-start TWICE (boot-5 rebuild c0-167 + the boot-5 "
                "latch replay 4501->9403) — boot 4 was in the silent "
                "aa campaign, not stalled.",
        "status": "VERIFIED",
        "provenance": {"evidence": "r43_boot5.jsonl (RESOLVED event) + "
                                 "r43_boot5_report.json",
                       "source": "R43 boot 5 (foreground, per-chunk "
                                 "stderr trail)"}},
    {
        "what": "R43 boots 6+7 (two-stage split, the cross-process "
                "savestate restore is the R42-proven pattern): the "
                "depth-conditional gate (aa_resolved>=1 AND px>700) "
                "saved r43_postkill at c172 with px=992.0, flags=0x4B "
                "(the R41 RELEASE_SIGNATURE), score 4501 — but that "
                "posture is POST-RESTART + CHECKPOINT-RESPAWN (the "
                "c164 chopper resolve was followed by a silent "
                "timer-expiry-style mission restart px 1150->25 that "
                "the shallow-anchor guard could not see, then the "
                "checkpoint reload back to 992). Stage 2 from it: 900 "
                "latch chunks, 8 deaths (all continue-rescued, counted "
                "+ disclosed), score 4501->13704, px pushed to 1378 "
                "(PAST the 1285-1310 soldier wave — new territory) but "
                "held at the 1272 clamp; mission_end NEVER latched "
                "(0 latches); the R41 partial-F1 gap (flags partial, "
                "prog 0xffffffff unmoved) + re-armed section-VM nodes "
                "persist across restarts. THE PRIMARY NEGATIVE: the "
                "INTERACTIVE M2 entry is NOT claimable from a "
                "post-restart posture this round; the clean (deaths=0) "
                "R42-style resolve posture remains the requirement.",
        "status": "OBSERVED",
        "provenance": {"evidence": "r43_boot6_s1_report.json + "
                                 "r43_boot7_s2_report.json + jsonl",
                       "source": "R43 boots 6-7 (stage 1 + stage 2)"}},
    {
        "what": "R43 harness lessons (reusable guards, both rooted in "
                "measured failures): (1) policy stats (aa_resolved) "
                "survive deaths/restarts — ANY stat-gated save needs a "
                "world-depth condition; (2) the rebuild restart-leak "
                "guard must be DYNAMIC (max_px>700 then px<700 = "
                "leak), not phase-open-state — the shallow-anchor "
                "rebuild ran the deep phase with the guard permanently "
                "off and the c164->c165 restart (px 1150->25, no death "
                "event — the timer-expiry path reads as alive-at-25) "
                "went undetected; (3) frontier postures must be SAVED "
                "(the px-1378 posture of boot 7 was lost to exit "
                "without a save).",
        "status": "OBSERVED",
        "provenance": {"evidence": EVID,
                       "source": "R43 boots 5-7 (the guard/lesson "
                                 "chain)"}},
]

NEXT = {
    "budget": "cap 4 disclosed pre-run (stage-1 rebuilds are death-"
              "sensitive; one spare)",
    "hypothesis": "R44: the end-of-mission chain fires ONLY from a "
                  "clean (deaths=0, no-restart) resolve posture — "
                  "rebuild from issue5_m1_start with the DYNAMIC "
                  "restart guard (max_px>700 then px<700 = honest "
                  "abort) and a deaths=0 validity requirement; save "
                  "r44_postkill at the depth-conditional gate AND "
                  "save frontier states whenever px>1200 (the boot-7 "
                  "loss); then the latch (900 bound) + the session-6 "
                  "accept ladder + the M2 input-delta discriminator "
                  "(INTERACTIVE iff dR>=30 and dR-dL>=60 at the spawn "
                  "fingerprint px 70-80/php 70-80/gren>=9/score<=200). "
                  "Fallback levers if deaths=0 proves unreachable: "
                  "(a) the deferred 0x4054 soft-soldier HP-word "
                  "readout (aimed fire at slots 13/16, x 1150-1450, "
                  "corpse/wreck excluded, +0x8E/+0xA4/+0x9E per tap "
                  "against verified score gains), (b) the px-1272 "
                  "clamp push past the wave zone (the boot-7 frontier "
                  "shows the zone is clearable to 1378).",
    "method": "stage 1: boot -> anchor rebuild (dynamic guard, "
              "frontier saves) -> r44_postkill; stage 2: boot -> "
              "restore -> latch -> accept chain -> discriminator. "
              "Oracle unchanged: walker words + verified score gains "
              "+ alive 0x0EE518; never +0x8E in any oracle; every "
              "accept input is a disclosed scripted probe.",
}


def _normalize_statuses(cap):
    """Vocabulary migration (the shipped-validator defect found at
    R43 close-out: HEAD's capsule carried 'CONFIRMED' at events[26] —
    the R42 update slipped it past; the suite flags it now)."""
    allowed = {"VERIFIED", "OBSERVED", "INFERRED", "UNKNOWN",
               "CONTRADICTED", "BLOCKED"}
    mapping = {"CONFIRMED": "VERIFIED", "FALSIFIED": "CONTRADICTED",
               "NEGATIVE": "CONTRADICTED", "POSITIVE": "VERIFIED"}
    fixed = 0
    for e in cap.get("events", []):
        st = e.get("status")
        if st not in allowed and st in mapping:
            e["status"] = mapping[st]
            fixed += 1
    return fixed


def main():
    with open(CAPSULE) as f:
        cap = json.load(f)
    fixed = _normalize_statuses(cap)
    cap.setdefault("events", []).extend(NEW_EVENTS)
    cap["next_experiment"] = NEXT
    cap.setdefault("meta", {})["last_updated"] = "R43"
    cap["meta"]["r43_reconciled"] = (
        "R43: the stale-stat gate lesson (world-depth condition on any "
        "stat-gated save), the dynamic restart guard requirement, the "
        "from-start village capability CONFIRMED for the current "
        "policy, the post-restart posture NEGATIVE for the end chain, "
        "next_experiment replaced (R44 = the clean-resolve chain with "
        "deaths=0 validity + frontier saves)")
    with open(CAPSULE, "w") as f:
        json.dump(cap, f, indent=1)
    print("capsule updated: +%d events (total %d), next_experiment "
          "replaced (R44)" % (len(NEW_EVENTS), len(cap["events"])))


if __name__ == "__main__":
    main()
