#!/usr/bin/env python3
"""r42_capsule_update.py — R42 close-out: append the R42 events to the
MSX knowledge capsule and replace next_experiment with the R43 lever.

Honesty rules honored: every event carries provenance; the attract/demo
label is kept EXPLICIT (the post-tally chain is demo-shaped, NOT a
verified interactive M2 entry); the banner-predicate miss is recorded,
not smoothed over; no claim promoted beyond its evidence; +0x8E never
in any oracle.
"""
import json
import os

_REPO = "/home/z/my-project/ps1ai"
CAPSULE = os.path.join(_REPO, "data", "knowledge", "msx", "capsule.json")

EVID = ("data/games/SLUS-01212/truck_evidence/r42/ "
        "(r42_boot[1,2]_report.json + r42_boot[1,2].jsonl + "
        "boots_used.json cap 2/2; scratch/r42/pngs local-only)")

NEW_EVENTS = [
    {
        "what": "R42 boot-1 NEGATIVE + gate lesson: the aa_resolved "
                "resolve gate was PREMATURE - from that posture "
                "(r42_postkill saved c441, px 1357, score 6101) "
                "24000f of HARD zero input produced NO banner and NO "
                "restart: the end sequence is NOT an idle timer, and "
                "the attract/demo control took the world over (px "
                "moved 1357->540->993, score climbed 6101->13610 with "
                "ZERO inputs). The resolved posture the R42 method "
                "means is the mission_end LATCH posture, not the "
                "aa-resolve posture.",
        "status": "OBSERVED",
        "provenance": {"evidence": EVID,
                       "source": "R42 boot 1 (rebuild + hard hold from "
                                 "the aa-resolve posture)"}},
    {
        "what": "R42 boot-2 CORE RESULT (the capsule hypothesis "
                "CONFIRMED on its core claim): from r42_postkill the "
                "shipped policy latched mission_end at latch-c24 "
                "(px 1562, score 7701), then the HARD zero-input hold "
                "ran 1600 chunks (24000f): prebanner (0,8) at hold-c11 "
                "-> tally teardown 349 chunks -> the world FLOWED "
                "through M2-load-shaped signatures (score-0 world at "
                "px 120 -> teardown at score 7800 = the session-6/7 "
                "M1->M2 loading score -> M2-spawn-shaped world px "
                "74.0/php 74/sec (11,1) vs the recorded spawn 74.6/76.4 "
                "php 74/76 -> teardown at score 10930 = the session-7 "
                "train-ride fade score -> further demo scenes) and the "
                "2-chunk-persistent restart classifier NEVER fired. "
                "The R41 restart leak was a HARNESS INPUT LEAK, not a "
                "game-state blocker; the D7 blocker is CLOSED as "
                "bypassed-by-mission-end.",
        "status": "CONFIRMED",
        "provenance": {"evidence": EVID,
                       "source": "R42 boot 2 (r42_postkill -> policy "
                                 "latch -> hard hold)"}},
    {
        "what": "R42 honest labels: (a) the banner predicate (0xC x4 "
                "persist) NEVER fired under the zero-input hold - the "
                "(0,8) prebanner flows straight into the tally "
                "teardown; the session-5/6 banner (0xC at px 26.4) is "
                "the input-alive variant of the same end sequence. "
                "(b) The post-tally chain is the ATTRACT/DEMO pipeline "
                "(milestone scores 7800/10930 match the recorded "
                "transitions; world windows ~112 chunks) - the "
                "M2-load signature is ATTRACT-LABELED, NOT a verified "
                "INTERACTIVE M2 entry; the interactive entry remains "
                "the session-6 ONE START-tap accept path.",
        "status": "OBSERVED",
        "provenance": {"evidence": EVID,
                       "source": "R42 boot 2 hold chain + boot 1 "
                                 "attract takeover"}},
]

R43_NEXT = {
    "budget": "1 boot (restore r42_postkill; cap 2/2 used in R42 - the "
              "next round owns its own ledger)",
    "hypothesis": "R43: the INTERACTIVE M2 entry is claimable from the "
                  "mission_end latch - restore r42_postkill, run the "
                  "shipped policy to the latch, then at the "
                  "teardown/tally accept with the session-6 recipe (ONE "
                  "disclosed START tap, then the endzone RIGHT walk "
                  "through the MSX-logo transition): if the score "
                  "continues the runner's own tally (7701 -> 7800) and "
                  "the M2 spawn (px ~74-76, php 74-76, gren 10) is "
                  "followed by RUNNER-controlled gameplay (inputs move "
                  "px), the M2 entry is INTERACTIVE-VERIFIED (vs the "
                  "R42 attract-labeled chain). Secondary (deferred from "
                  "the R42 capsule): name the 0x4054 soft-soldier HP "
                  "word - restore r42_postkill, aimed fire at slots "
                  "13/16 (x 1150-1450, corpse/wreck excluded), read "
                  "+0x8E/+0xA4/+0x9E per tap against verified score "
                  "gains.",
    "method": "boot 1: restore r42_postkill -> policy to the latch -> "
              "hard hold UNTIL the teardown -> ONE START tap -> the "
              "session-6 walk recipe -> classify M2 spawn + the first "
              "input-driven px delta = INTERACTIVE_M2_ENTRY; the demo "
              "discriminator is the input-delta, not the score alone. "
              "boot 2 (conditional): the 0x4054 HP-word readout. Oracle "
              "unchanged: the walker words + verified score gains; "
              "never +0x8E in any oracle.",
}


def main():
    with open(CAPSULE) as f:
        cap = json.load(f)
    cap.setdefault("events", []).extend(NEW_EVENTS)
    cap["next_experiment"] = R43_NEXT
    with open(CAPSULE, "w") as f:
        json.dump(cap, f, indent=1)
    print("capsule events:", len(cap["events"]))
    print("next_experiment replaced (R43)")


if __name__ == "__main__":
    main()
