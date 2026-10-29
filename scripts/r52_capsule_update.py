#!/usr/bin/env python3
"""r52_capsule_update.py — R52 round close-out: append the round
events to BOTH capsules (the 60% track to msx, the 40% track to
buzzybee) and replace next_experiment (R53 in each).  Events are
provenance-complete ({source, evidence} non-empty) per the schema."""
from __future__ import annotations

import json
import time

MSX = ("/home/z/my-project/ps1ai/data/knowledge/msx/capsule.json")
BEE = ("/home/z/my-project/ps1ai/data/knowledge/buzzybee/capsule.json")


def main():
    now = time.strftime("%FT%TZ", time.gmtime())

    # ---------------- the 60% track: msx ----------------------------
    c = json.load(open(MSX))
    ev = c["events"]
    ev.append({
        "what": "R52 the PAY-FRAME UNION-NET WOUND HUNT armed and "
                "executed under the THIRD sandbox rollback (the R45/"
                "R47 contingency verbatim): the scratch/ reset lost "
                "the r47_frontier_a/b states + the r47b gs1 "
                "checkpoint (never committed - no-game-bytes); "
                "issue5_m1_start SURVIVED (verified pre-run).  "
                "Stage 1 rebuilt the frontiers DETERMINISTICALLY for "
                "the 5th time (r52_frontier_a px 1224.9 census 13 / "
                "r52_frontier_b px 1254.8 census 14 - the SAME "
                "postures as R45/R47, 6 deaths / 6 continue-rescues "
                "counted, TAINTED lineage).  Boot ledger 4/4 with "
                "THREE disclosed amendments, every one a ZERO-TAP "
                "runner-code defect: boot 2 crashed at the first "
                "CONNECT pick (the hunt rows dropped the R48 direct "
                "key the R50 helpers read; partial jsonl preserved) "
                "-> cap 2->3 DISCLOSED; boot 3 crashed in the "
                "CONTROL walk (a missing import - same defect "
                "family) -> cap 3->4 DISCLOSED with the OFFLINE "
                "CONTRACT DRY-RUN (r52_dryrun.py, the r51_gate_"
                "dryrun precedent) passing ALL 11 checks BEFORE "
                "boot 4 was spent; two phantom ledger entries "
                "(cap-check crashes after increment, no core load) "
                "REFUNDED disclosed and the cap gate moved BEFORE "
                "the increment (the phantom class eliminated); "
                "boot 4 clean.  THE R52 LEVER PROVEN: frame_walk_"
                "hunt records the union-net u16 states (0x60..0xE0, "
                "65 offsets) for every live slot EVERY frame of the "
                "tap+flight window.  CAPTURES: two MORE +1000 "
                "connects (st_pre 0x42bc path [0x42bc,0x17f8,0x4008,"
                "0x3f48,0x5b0c] pay f_rel 3; st_pre 0x3f48 path "
                "[0x3f48,0x5b0c] pay f_rel 4 - the R51 +1000 family "
                "REPLICATED under pay-frame telemetry; the "
                "magnitude table now +500 x3 vs +1000 x7 across "
                "R48-R52); PIERCE replicated n=2 (total n=4; the "
                "0xab94 target NEVER reacted, +100 paid, no corpse "
                "in-window - the victim is beyond); controls 6 "
                "windows dscore 0 (the movement-inclusive baseline, "
                "5th round).  ANALYSIS (r52_analysis_correct.py): "
                "the two +1000 pay-frame word vectors DIFFER in 123 "
                "slot/offsets (the candidate pool for the "
                "discriminator); the wound-shape batch holds 546 "
                "raw candidates incl. slot12 +0xa0 257->2 with 4f "
                "recovery (the closest accumulator signature; the "
                "camera-churn families 0x8c/0x94 and the 1-tick "
                "countdowns dominate the rest).  HONEST SHORTFALL: "
                "the +500 class was NOT captured (the corridor gate "
                "starved - 11 skips per frontier - and the wall "
                "guard ended both passes before a +500 connect or "
                "a KILL landed), so the +500-vs-+1000 pay-frame "
                "discriminator stays PENDING.",
        "status": "OBSERVED",
        "provenance": {
            "source": "r52t1_payframe_wound.py (boots 1-4) + "
                      "scratch/r52/boots_used.json (cap 4: three "
                      "disclosed zero-tap defect amendments + two "
                      "refunded phantom entries) + r52_dryrun.py "
                      "(11 contract checks pre-boot-4)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r52/ "
                        "(r52_boot1_s1 + r52_boot4_s2 jsonl + "
                        "reports + r52_wound_table.json; boots 2-3 "
                        "preserved as defect partials)"}})
    ev.append({
        "what": "R52 offline verdict recorded: the pay-frame "
                "telemetry path is the R53 discriminator lever - "
                "the +500 capture under the SAME telemetry is the "
                "single missing piece; the 123-word candidate pool "
                "and the 546-shape batch are committed in "
                "r52_wound_table.json for the cross-round "
                "intersection test.",
        "status": "OBSERVED",
        "provenance": {
            "source": "r52_analysis_correct.py (offline, no boot)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r52/"
                        "r52_wound_table.json"}})
    c["next_experiment"] = {
        "id": "R53",
        "budget": "1-2 boots (restore-only from the r52 frontiers "
                  "while they survive on disk; a rebuild boot only "
                  "if lost, disclosed)",
        "hypothesis": "the +500 connect class is capturable under "
                      "the pay-frame telemetry from the r52 "
                      "frontiers (the R50/R51/R52 +1000s all came "
                      "from st_pre 0x42bc/0x3f48/0x2b74 targets "
                      "mid-wound-recovery; a FRESH 0x4054 soft "
                      "target connect paid +500 in R48 - target "
                      "freshness is the discriminator candidate); "
                      "any word whose pay-frame value separates "
                      "+500 from +1000 with ZERO overlap refines "
                      "the model to payment = f(wound_state); the "
                      "slot12 +0xa0 shape (257->2, rec 4) is the "
                      "named accumulator candidate to test first",
        "method": "gate diagnostics FIRST (per-skip blocking-"
                  "occupant dump - the R52 starvation is "
                  "undiagnosed) -> restore r52_frontier_a/b -> "
                  "CONNECT taps with the freshness spread (fresh "
                  "0x4054 + the wound-state family) until BOTH "
                  "magnitudes land under pay-frame telemetry -> "
                  "the zero-overlap discriminator test on the "
                  "pay-frame word state -> the KILL contrast if "
                  "the budget allows",
        "m2_gate_note": "the INTERACTIVE M2 entry remains gated on "
                        "a clean (deaths=0, no-restart) deep "
                        "resolve posture - unchanged"}
    c.setdefault("meta", {})["updated"] = now
    json.dump(c, open(MSX, "w"), indent=1, ensure_ascii=False)
    print("msx capsule: +2 events (now %d), next = %s"
          % (len(ev), c["next_experiment"]["id"]))

    # ---------------- the 40% track: buzzybee -----------------------
    b = json.load(open(BEE))
    ev = b["events"]
    ev.append({
        "what": "R52 the dominance recipe SCALES to CAP_F 2400 (the "
                "fifth extension, the capsule lever verbatim) under "
                "the THIRD sandbox rollback: the r47b gs1 "
                "checkpoint LOST (never committed) -> boot 1 = the "
                "core+rom load AND the gs1 checkpoint REBUILD (the "
                "r45b/r42b pattern verbatim, DISCLOSED pre-run; "
                "settle 900f -> START -> gs1 -> serialize).  "
                "Environment re-verified internet-first sha-"
                "verified 0 boots (upstream EXE 9b0bfc08 byte-"
                "identical, committed wrap-script output 042b94bb "
                "byte-identical; the disc rebuilt by r30t0_"
                "buzzybee_asset.py after the rollback).  9 offline "
                "policy checks passed BEFORE the boot.  RESULTS: "
                "arm A (policy5 verbatim @2400) 2301 / 1 hit / 9 "
                "passes / caused 1 = the 10th reproduction with "
                "score = f - 99 EXACT (2400 - 99 = 2301) - the "
                "prediction holds across the SIXTH cap; THE 9TH "
                "PASS ARRIVED (6 @1500 -> 7 @1700 -> 7 @1800 -> 7 "
                "@2000 -> 8 @2200 -> 9 @2400); arm B (bot_policy8 "
                "verbatim @2400) 2301 / 1 HIT / 8-of-8 / caused 2 "
                "(the FIFTH caused-replication TRUE) -> the FULL "
                "ORACLE FALSE FOR THE FIRST TIME IN FIVE ROUNDS "
                "(hits_zero broke); arm B2 (tier 12/12, the "
                "revert protocol) ALSO 1 hit + caused 3 - the "
                "margin floor is FILED (GM 8 AND GM 12 both hit "
                "at this checkpoint).  THE MECHANISM: both hits "
                "land at f_since_pass_start = 112 on the same "
                "deterministic wasp wave (e=[32,31,3]; A from "
                "above, B/B2 below; 'planned': false - a reflex "
                "dodge cannot clear it) - the wave is "
                "pass-boundary-locked, not margin-locked.  HONEST "
                "NOTES: (1) the five-round hits-zero streak "
                "(R47-R51) is BROKEN; (2) the score = f - 99 law "
                "survives; (3) the commitment signature visible "
                "again (seek_dur 134 + 8 + 4).",
        "status": "OBSERVED",
        "provenance": {
            "source": "r52b_capf2400.py (boot 1 incl. the "
                      "disclosed gs1 rebuild) + "
                      "scratch/r52b/boots_used.json (cap 1)",
            "evidence": "scratch/r52b/metrics_r52b.json + "
                        "frames_A2400.jsonl + frames_B2400.jsonl + "
                        "frames_B2400_r.jsonl"}})
    b["next_experiment"] = {
        "id": "R53",
        "budget": "0-1 boots (restore-only from the r52b gs1 "
                  "checkpoint while it survives)",
        "hypothesis": "the pass-boundary wave (f_since_pass_start "
                      "112, e=[32,31,3]) is DODGEABLE BY PLAN: a "
                      "wave-phase predictor in bot_policy8 that "
                      "pre-positions the bee BEFORE the wave frame "
                      "(the R45-B pre-position lever returns with a "
                      "wave-phase input) holds hits 0 AND caused "
                      ">= 2 @2400 (the sixth caused-replication) "
                      "with score >= 2301 predicted; if the wave "
                      "is phase-locked to the pass counter rather "
                      "than the planner, the hit recurs at the "
                      "same relative frame in ALL arms - the "
                      "control experiment decides",
        "method": "offline checks BEFORE any boot -> boot 1 "
                  "core+rom load (restore-only arms from the r52b "
                  "gs1 checkpoint) -> arm A2400 (the 11th "
                  "reproduction) -> arm B2400 + the wave-phase "
                  "pre-position -> arm B2 (tier 12/12) only on a B "
                  "hit -> the wave-phase table (the hit frame "
                  "relative to the pass boundary across arms) -> "
                  "the oracle line",
        "m2_gate_note": "the score-superiority line stays within "
                        "the dodge axis; no scoring-policy changes"}
    b.setdefault("meta", {})["updated"] = now
    json.dump(b, open(BEE, "w"), indent=1, ensure_ascii=False)
    print("buzzybee capsule: +1 event (now %d), next = %s"
          % (len(ev), b["next_experiment"]["id"]))
    return 0


if __name__ == "__main__":
    main()
