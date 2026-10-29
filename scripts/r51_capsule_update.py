#!/usr/bin/env python3
"""r51_capsule_update.py — R51 round close-out: append the round
events to BOTH capsules (the 60% track to msx, the 40% track to
buzzybee) and replace next_experiment (R52 in each).  Events are
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
        "what": "R51 the WOUND-ACCUMULATOR HUNT executed (the "
                "capsule lever verbatim: the extended wide-net u16 "
                "0x60..0x88 + 0xA8..0xE0 read as the UNION with the "
                "R48 bounded net = 0x60..0xE0 even, 65 offsets, the "
                "read_words widening DISCLOSED PRE-RUN; the corridor "
                "gate with the invulnerability predicate; CONNECT "
                "x3 no-follow-up, KILL x2, PIERCE x1; the "
                "invulnerability census at every tap).  NO sandbox "
                "rollback (the R47 frontiers survived, verified "
                "pre-boot).  THREE disclosed defect amendments, "
                "zero unaccounted boots: boot 1 clean 29s wall but "
                "the tap loop STARVED (the +60px beyond-margin put "
                "every candidate inside its own corridor - a gate "
                "predicate defect, ZERO bullets, ZERO protocol "
                "taps; the partial jsonl preserved) -> cap amended "
                "1->2 DISCLOSED PRE-BOOT-2 (the r47/r50 defect "
                "precedent); boot 2 ALSO starved (29s wall, zero "
                "bullets - the beyond-margin still applied to "
                "MORTAL targets) -> cap amended 2->3 DISCLOSED with "
                "an OFFLINE GATE DRY-RUN (r51_gate_dryrun.py) "
                "PROVING taps flow on the boot-2 census BEFORE "
                "boot 3 was spent (CONNECT/KILL admitted on both "
                "frontiers); boot 3 clean 30s wall, ledger 3/3.  "
                "GATE LESSON (the R50 gate-physics rule applied "
                "twice): the bullet is ABSORBED by a mortal target "
                "- the corridor extends BEYOND only for a "
                "TRANSPARENT target.  Group shortfall honest: "
                "connects 1/3 counted (b-tap2 slot20 st_pre 0x3f48 "
                "PAID +1000 but was not counted - no 0x42bc entry, "
                "already mid-recovery), kills 0/2 (the census "
                "thinned), PIERCE 2/2.",
        "status": "VERIFIED",
        "provenance": {
            "source": "r51t1_wound_hunt.py (boots 1-3, the defect "
                      "amendments disclosed same-entry, the dry-run "
                      "gate-proof before boot 3) + "
                      "scratch/r51/boots_used.json",
            "evidence": "data/games/SLUS-01212/truck_evidence/r51/ "
                        "(r51_boot1.jsonl + r51_boot2.jsonl partials "
                        "+ r51_boot3.jsonl + r51_boot3_report.json)"}})
    ev.append({
        "what": "R51 CORRECTED VERDICT (r51_analysis_correct.py, "
                "offline, authoritative - the R49/R50 v2 global-"
                "frame matcher + the wound-word hunt + the R50 "
                "bounded-net cross-join):  (1) THE PIERCING "
                "REPLICATED n=2 IN ONE ROUND: both PIERCE taps "
                "(aimed at the 0xab94-state slot30) paid +100 with "
                "the transparent target NEVER reacting (no 0x42bc, "
                "no registration on the transparent slot); pass-a's "
                "+100 co-lands lag-0 on slot18's 0x515c registration "
                "at x 1357.2 BEHIND the transparent target (class "
                "KILL_REG, holder_invul=30 at the pay frame) - the "
                "R50 discovery is now frame-exact replicated and "
                "the invulnerability predicate is MEASURED: the "
                "bullet passes 0xab94 and kills the first vulnerable "
                "mortal behind;  (2) THE CONTROLS NEVER PAY (4 "
                "control windows, 0 payments - the movement-"
                "inclusive churn baseline replicated a fourth "
                "round);  (3) THE CONNECT MAGNITUDE: two MORE "
                "+1000 connects (st_pre 0x42bc AND st_pre 0x3f48, "
                "both slot20 recoveries) - the table is now +500 x3 "
                "vs +1000 x5 across R48-R51; the 0x42bc-entry state "
                "alone is NOT the discriminator (the same entry "
                "state paid +500 in R48/R49 and +1000 in R50/R51); "
                "(4) THE WOUND-WORD HUNT IS NEGATIVE AT TAP-WINDOW "
                "GRANULARITY: the union-net delta intersection "
                "across the two +1000 events holds 100+ candidate "
                "words (the pre/post window contains walk/animation "
                "churn) and the bounded-net cross-join against "
                "R50's +500/+1000 events shows NO separating word "
                "(the R50 +500 shares 5 candidate words, the +1000s "
                "share 51) - the accumulator hunt needs the FRAME-"
                "EXACT union-net read (per-frame 0x60..0xE0 in the "
                "flight window, the word state AT the pay frame) = "
                "the R52 lever;  (5) the invul census: 4 dwell "
                "entries (0xab94/0xae7c), the 0xae7c class "
                "registered twice more with ZERO co-landing "
                "payments (the exonerated status holds).  Session "
                "ledger +2200 (a: +1100 = 1000+100, b: +1100 = "
                "1000+100), deterministic across both frontiers.",
        "status": "VERIFIED",
        "provenance": {
            "source": "r51_analysis_correct.py (offline, no boot) + "
                      "r51_gate_dryrun.py (offline, the boot-3 gate "
                      "proof)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r51/ "
                        "r51_wound_table.json"}})
    c["next_experiment"] = {
        "id": "R52",
        "budget": "cap 1 disclosed pre-run (restore-only from the "
                  "SAVED r47_frontier_a/b while they survive; the "
                  "boot is the core+rom load only)",
        "hypothesis": "the connect +500-vs-+1000 discriminator is "
                      "visible only AT the pay frame: a per-frame "
                      "u16 read of the union net (0x60..0xE0 even) "
                      "in the tap+flight window on dedicated "
                      "connects exposes the word whose PAY-FRAME "
                      "state (not the window delta) separates the "
                      "+500 class from the +1000 class; the "
                      "wound-accumulator must hold the accumulated "
                      "wound AT the registration frame; SECONDARY: "
                      "the piercing class grows to n>=3 with a "
                      "dedicated transparent-target tap when the "
                      "census offers one",
        "method": "boot -> restore r47_frontier_a -> the R48 direct-"
                  "read telemetry verbatim + PER-FRAME union-net "
                  "reads (the flight window at 0x60..0xE0, slots "
                  "1..39) -> dedicated 1-bullet CONNECT taps until "
                  "n>=3 paid events across both magnitudes -> the "
                  "pay-frame word table + the discriminator test "
                  "(any word whose pay-frame value separates +500 "
                  "from +1000 with zero overlap) -> the magnitude "
                  "model refined to payment = f(wound_state)",
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
        "what": "R51 the dominance recipe SCALES to CAP_F 2200 (the "
                "fourth extension, the capsule lever verbatim): "
                "arm A (bot_policy5 verbatim @2200) 2102 / 0 hits / "
                "8 passes / caused 1 = the 9th independent policy5 "
                "reproduction with the score = f - 99 prediction "
                "EXACT (2201 - 99 = 2102) - AND THE 8TH PASS "
                "FINALLY ARRIVED (6 @1500 -> 7 @1700 -> 7 @1800 -> "
                "7 @2000 -> 8 @2200; the capsule's density watch "
                "paid off); arm B (bot_policy8 verbatim @2200) "
                "2101 / 0 HITS / 8-of-8 / caused 2 = the FOURTH "
                "caused-replication, the FULL ORACLE (score >= "
                "1550 AND hits 0 AND caused >= 2) TRUE for the "
                "FOURTH consecutive round, the score = f - 99 "
                "prediction EXACT (2200 - 99 = 2101).  HONEST "
                "NOTES: (1) the score tie is RESTORED (A 2102 vs "
                "B 2101 - the R50 +2 B-edge did NOT replicate, the "
                "positioning side-effect label holds); (2) no "
                "margin floor (B took 0 hits, GM 8 safe a FIFTH "
                "time); (3) the commitment mechanism visible again "
                "(the decisive pickup seek_dur 134 in flower mode "
                "- the R48/R49 signature - plus one seek_dur 8).  "
                "Environment re-verified internet-first sha-"
                "verified 0 boots (9b0bfc08/042b94bb); the r47b gs1 "
                "checkpoint SURVIVED (READ-ONLY restore); cap 1 "
                "disclosed pre-run, boot 1 = the core+rom load "
                "only; 9 offline policy checks passed BEFORE the "
                "boot; 12.8s wall.",
        "status": "VERIFIED",
        "provenance": {
            "source": "r51b_capf2200.py (boot 1) + "
                      "scratch/r51b/boots_used.json (cap 1, no "
                      "amendments) + offline_checks 9/9 pre-boot",
            "evidence": "scratch/r51b/metrics_r51b.json + "
                        "frames_A2200.jsonl + frames_B2200.jsonl"}})
    b["next_experiment"] = {
        "id": "R52",
        "budget": "0-1 boots (restore-only from the r47b gs1 "
                  "checkpoint while it survives)",
        "hypothesis": "the linear score mechanism and the caused "
                      "mechanism hold at CAP_F 2400 (the fifth "
                      "extension): arm B (bot_policy8 verbatim "
                      "@2400) holds hits 0 AND caused >= 2 (the "
                      "FIFTH caused-replication) with score >= "
                      "2301 predicted by score = f - 99; the "
                      "wasp-density watch continues (8 @2200 -> ? "
                      "@2400); arm A = policy5 verbatim @2400 (the "
                      "10th reproduction check)",
        "method": "offline checks BEFORE any boot -> boot 1 "
                  "core+rom load -> restore the r47b gs1 checkpoint "
                  "-> arm A2400 -> arm B2400 -> arm B2 (tier 12/12) "
                  "only on a B hit -> the oracle line on B + the "
                  "score = f - 99 prediction at 2400 + the pass-"
                  "density vs commitment table (the 9th pass watch)",
        "m2_gate_note": "the score-superiority line stays within "
                        "the dodge axis; no scoring-policy changes"}
    b.setdefault("meta", {})["updated"] = now
    json.dump(b, open(BEE, "w"), indent=1, ensure_ascii=False)
    print("buzzybee capsule: +1 event (now %d), next = %s"
          % (len(ev), b["next_experiment"]["id"]))
    return 0


if __name__ == "__main__":
    main()
