#!/usr/bin/env python3
"""r40_capsule_update.py — R40 Task 6: reconcile the MSX knowledge
capsule against the R40 live evidence and append the new events.

Rules honored (R38 schema + the provenance discipline):
 - every new event carries provenance (evidence path + boot source)
   and the honest status label;
 - the chopper kill promotion is keyed on the verified identity
   (st 0xAA94/0xABDC, airborne, hp_a4) — the +0x8E rule untouched
   (never HP; not in any oracle);
 - the falsified hypotheses are recorded as CONTRADICTED, not silently
   dropped (the chopper-last-queue-entity release hypothesis; the
   boot-2 current-position throw geometry);
 - no claim is promoted beyond its evidence.
"""
import json
import os
import sys

_REPO = "/home/z/my-project/ps1ai"
CAPSULE = os.path.join(_REPO, "data", "knowledge", "msx", "capsule.json")

R40_EVID = ("data/games/SLUS-01212/truck_evidence/r40/"
            "r40_boot_reports.json + scratch/r40/r40_boot[1-7].jsonl "
            "(R40 boots 1-7 actual, ledger "
            "scratch/r40/boots_used.json cap 10 / 7 actual boots, "
            "every cap amendment disclosed pre-run incl. the boot-7 "
            "filing-bug series)")

NEW_EVENTS = [
    {
        "what": "R40 boot-1 census (the legacy v2.2 behavior via the "
                "queue_priority=False A/B flag, reproduction gate "
                "PASS: engage 118 / aa_kill 76 / throws 13 / connects "
                "1 / score 5701 = the R39 boot-6 pair exactly): WHO "
                "steals the mode at the pin is the TRUCK WRECK "
                "complex, not soldiers - 0xA44C-family states "
                "(0xA45C the wreck fire/smoke state + 0x9E88 + "
                "0xA44C) took 75/81 engage-at-pin chunks (0xA45C "
                "alone 67) and armor_hold held 37 more chunks on the "
                "wreck's stale row. The soldier family was ABSENT in "
                "all 81 chunks (fam=0) - the R38 queue discipline "
                "never blocked the aa campaign at this pin; the "
                "chopper was visible in 79/81 engage chunks.",
        "status": "OBSERVED",
        "provenance": {"evidence": R40_EVID,
                       "source": "R40 boot 1 (CENSUS-BASE, legacy "
                                 "flag)"}},
    {
        "what": "R40 boot-2 CONTRADICTED the current-position throw "
                "geometry: the queue-priority-only treatment (v3: "
                "the chopper outranks engage/armor_hold in the pin "
                "context, 48 takeovers, aa_kill 76->84) scattered "
                "the throws (12, release dx 5.6-54.7 both signs) and "
                "connected 0/12 (vs the legacy 1/13) - throwing at "
                "the chopper's CURRENT position while it patrols at "
                "~1.5 px/f is the wrong gate; the deterministic "
                "trajectory shifted (score 3900 vs 5701, the c71 "
                "+300 kill pack skipped).",
        "status": "CONTRADICTED",
        "provenance": {"evidence": R40_EVID,
                       "source": "R40 boot 2 (trialQ1/Q2 pair)"}},
    {
        "what": "R40 arrival-band model + lead gate (v3.1): the ONLY "
                "moving-chopper connect (boot-1 c270: release dx "
                "-51.7, chopper CLOSING) plus the R39 frame capture "
                "(patrol ~1.5 px/f, parked at 1132.3) give dx_arr = "
                "dx + v*T with the lob time-to-altitude T in "
                "[11.1, 27.8]f; AA_LEAD_T=20 shipped. Parked hovers "
                "reduce to the v2.2 release band exactly (the five "
                "verified parked connects are unaffected). Boot-3: "
                "15 throws (legacy 13), the FIRST early connect "
                "(c99->c100 300->200; the legacy never connected "
                "before c270), 11/15 throws in-arrival-band, ch_v "
                "estimator tracking -1.52..1.56.",
        "status": "OBSERVED",
        "provenance": {"evidence": R40_EVID,
                       "source": "R40 boot 3 (trialL1/L2 pair) + "
                                 "boot-1 c270 + the R39 frame "
                                 "capture"}},
    {
        "what": "R40 MILESTONE - the chopper KILLED IN-POLICY, "
                "deterministic across 4 boots: the patient 1200-chunk "
                "campaign (the window-size hypothesis: each run is "
                "CKPT-independent so 3 connects must land in ONE run; "
                "300 chunks = ~15 throws = ~1 connect) landed 3 "
                "verified hp_a4 connects (c100 300->200, c387 "
                "200->100, vanish kill-connect at c421, the verified "
                "-100 pattern) = hp_a4 300->0, kill score +1200 to "
                "6901, 0 deaths in the kill window. Boots 4/5/6/7 "
                "all resolved at c421 with identical score - the "
                "kill is a deterministic property of the v3.1 policy "
                "(queue priority + arrival lead gate).",
        "status": "VERIFIED",
        "provenance": {"evidence": R40_EVID,
                       "source": "R40 boots 4-7 (PATIENT/WATCH/STAND/"
                                 "NODES), commits post-2e28581"}},
    {
        "what": "R40 CONTRADICTED the chopper-last-queue-entity "
                "release hypothesis: with the chopper dead the D7 "
                "section did NOT release - 745-780 post-kill chunks "
                "of hold with NOTHING in the engage window (near="
                "None 741/779), no 0xC. The boot-5 full-table watch: "
                "NO killable entity remains (the chopper row "
                "persists as an a4=0 wreck shell; 0xA45C = the "
                "truck-wreck fire state a4=0; the persistent rows "
                "are scenery/signed-transient markers; one a4=30 "
                "faller at the resolve). The release blocker is in "
                "the section-VM queue state, not a visible entity: "
                "walker [0xB, 0x1] (F1: the release flips flags "
                "0x1->0x8), the progress word accumulating pending "
                "bits 0x80000000 -> 0xFFF... -> 0xFFFFFFFF (F1: the "
                "release flips it to 0xFFF38B4A), the node list "
                "POINTER at 0x800EB5F8 = 0x80084dcc (the list body "
                "unread - the R41 lever).",
        "status": "CONTRADICTED",
        "provenance": {"evidence": R40_EVID,
                       "source": "R40 boots 4-7 + the session-3 F1/F6 "
                                 "address map"}},
    {
        "what": "R40 the wave-zone stand falsified as the post-kill "
                "release path: walking LEFT from the aa anchor hit a "
                "HARD MAP BARRIER at px 1021.8 (no entity there - a "
                "geometry/state wall) 5.8 px short of the verified "
                "992-1016 stand zone; the walker re-latched [0xB,0x1] "
                "within ~2 chunks of the walk. The session-3/4 "
                "release ran standing at 992-1016 from the LEFT-side "
                "wave clear (the player was already there before the "
                "walker state engaged) - the post-kill approach from "
                "the RIGHT cannot reach it. Also: the boot-7 queue "
                "sweep resolved the 0xA45C identity question (the "
                "wreck fire state, a4=0, not a killable) and found "
                "RIGHT-side soldier-family rows (slots 13/16 at "
                "1285-1310, one flipping to 0x41FC) past the "
                "barrier.",
        "status": "OBSERVED",
        "provenance": {"evidence": R40_EVID,
                       "source": "R40 boots 6-7 (STAND/NODES)"}},
]

NEXT = {
    "budget": "2-3 boots; the kill chain (v3.1, 1200 chunks) is "
              "deterministic and costs ~1 boot per confirmation",
    "hypothesis": "R41: the release blocker is a pending node in the "
                  "section-VM queue. Read the node list BODY at "
                  "0x80084dcc (the pointer at 0x800EB5F8; node fields "
                  "+0x5C/+0x8 per the session-3 F6 decode) plus the "
                  "runner id s16 @0x800EB588 and the gate u16 "
                  "@0x800EB5C6 in the post-kill watch, and correlate "
                  "each pending node with an entity identity or a "
                  "trigger. Candidates ranked by the R40 evidence: (a) "
                  "the RIGHT-side soldier-family wave (slots 13/16 at "
                  "1285-1310 in boot-6/7, one flipping to 0x41FC - "
                  "killable once the barrier at 1021.8 is understood, "
                  "or lob-reachable), (b) a non-entity node (a timer/"
                  "walk trigger), (c) the residual frozen 0x4054 "
                  "soldier from the session-3 F9 run (not present in "
                  "the boot-5/6/7 tables, but its TRUE HP word is "
                  "still unknown - soft soldiers do not use +0xA4). "
                  "The kill->release chain then completes the "
                  "mission-end sequence (F1: walker flags 0x1->0x8, "
                  "progress -> 0xFFF38B4A, then the 0xC banner).",
    "method": "boot 1: the patient kill + the node-list dumps at "
              "0x80084dcc (+0x0..+0x100) at resolve + every 10 chunks "
              "after; correlate pending nodes with the live entity "
              "table snapshots. boot 2: the discriminating trial "
              "(kill the named pending entity if it is the "
              "RIGHT-side wave - the lob geometry from the 1021.8 "
              "barrier reaches dx_arr in-band per the arrival model; "
              "or trigger the node if non-entity). Oracle unchanged: "
              "walker flags 0x1->0x8, the progress word -> 0xFFF38B4A, "
              "the 0xC banner predicate; never +0x8E.",
}


def main():
    with open(CAPSULE) as f:
        cap = json.load(f)
    evs = cap.setdefault("events", [])
    known = len(evs)
    for e in NEW_EVENTS:
        evs.append(e)
    cap["next_experiment"] = NEXT
    meta = cap.setdefault("meta", {})
    meta["last_updated"] = "R40"
    meta["last_commit_note"] = ("R40: the chopper killed in-policy "
                                "x4 deterministic; the release "
                                "blocker localized to the "
                                "section-VM queue (node list "
                                "@0x80084dcc unread)")
    with open(CAPSULE, "w") as f:
        json.dump(cap, f, indent=1)
    print(f"capsule: {known} -> {len(evs)} events; "
          f"next_experiment replaced (R41 node-list read)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
