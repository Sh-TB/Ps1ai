#!/usr/bin/env python3
"""r50_capsule_update.py — R50 round close-out: append the round
events to BOTH capsules (the 60% track to msx, the 40% track to
buzzybee) and replace next_experiment (R51 in each).  Events are
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
        "what": "R50 the CONTROLLED-CORRIDOR tap protocol executed "
                "(the capsule lever verbatim: fire ONLY when the "
                "aimed target is the ONLY mortal in the bullet "
                "corridor; 2 movement-only controls; CONNECT no-"
                "follow-up; KILL prefers the 0xae7c class - the "
                "in-round disclosed pre-run refinement).  NO sandbox "
                "rollback (the R47 frontiers survived, verified "
                "pre-boot); boot 1 CRASHED post-restore at the "
                "control-walk record (NameError post_sc - a runner "
                "defect, ZERO taps fired, the world untouched; the "
                "partial jsonl preserved) - cap amended 1->2 "
                "DISCLOSED PRE-BOOT-2 (the r47 boot-2 defect "
                "precedent); boot 2 clean 32s wall, ledger 2/2 "
                "spent, no further amendments.  The corridor gate "
                "was STRICT (11 gate skips per pass - the spawner "
                "zone keeps the lanes occupied) and re-derivation "
                "found 1 marginal violation (an approach-shift "
                "entry, disclosed).  GROUP RESULTS: connects 1+0 "
                "(the group goals unmet again - the zone churn "
                "thins the census), kills 0/3 as a PROTOCOL group "
                "- but the fired windows produced the cleanest "
                "payment data of the campaign (6 paid windows, "
                "every one corridor-cleared pre-fire).",
        "status": "VERIFIED",
        "provenance": {
            "source": "r50t1_controlled_corridor.py (boots 1-2, the "
                      "defect amendment disclosed same-entry) + "
                      "scratch/r50/boots_used.json",
            "evidence": "data/games/SLUS-01212/truck_evidence/r50/ "
                        "(r50_boot1.jsonl partial + r50_boot2.jsonl "
                        "+ r50_boot2_report.json)"}})
    ev.append({
        "what": "R50 CORRECTED VERDICT (r50_analysis_correct.py, "
                "offline, authoritative - the R49 v2 global-frame "
                "matcher + the corridor re-derivation + the 0xae7c "
                "census):  (1) THE CONTROLS NEVER PAY - zero-input "
                "AND movement-only windows (4 windows, 6+ natural "
                "corpses) paid 0 = the churn baseline is now "
                "movement-inclusive and the bullet-victim lock "
                "tightens (movement alone provokes nothing);  (2) "
                "THE KILL LANE IS CLEAN FOR THE FIRST TIME: the two "
                "+100 payments co-land EXACTLY (lag 0) on the "
                "registrations at x 1389.2 / 1349.8 and the "
                "corridor evidence makes the AIMED-OR-PIERCED "
                "victim unambiguous - n=6 across R48/R49/R50 for "
                "the +100 registration-locked kill class;  (3) THE "
                "PIERCING DISCOVERY: the fired CONNECT tap at the "
                "0xab94-state target (an invulnerable state - the "
                "bullet passes) killed the mortal BEHIND it "
                "(slot18 @1389.2, +100) - the corridor gate needs "
                "an invulnerability predicate (0xab94 joins the "
                "burning family as bullet-transparent);  (4) THE "
                "0xae7c CLASS IS EXONERATED: slot33 cycled 2 more "
                "times (32/27 frames in-state) with ZERO co-landing "
                "payments - the R49 +1000 residual is NOT the "
                "0xae7c kill reward;  (5) THE CONNECT MAGNITUDE "
                "STAYS UNSETTLED - now +500 x3 vs +1000 x3 across "
                "R48/R49/R50 (this round: +1000 on the 0x42bc "
                "pre-state recovery, +500 on a LEFT-side 0x2b74 "
                "recovery, +1000 on a 0x3f48 recovery), every "
                "payment landing mid-wound-recovery of a SURVIVING "
                "target, NO state/co-landing discriminator found; "
                "the strong class-keyed form stays FALSIFIED; the "
                "remaining candidates: an internal wound "
                "accumulator (a hidden HP word OUTSIDE the bounded "
                "0x88..0xA8 net), or a hit-geometry-dependent "
                "damage model.  Session ledger +2700 (a: +1600 = "
                "1000+100+500, b: +1100 = 1000+100).",
        "status": "VERIFIED",
        "provenance": {
            "source": "r50_analysis_correct.py (offline, no boot)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r50/ "
                        "r50_corridor_table.json"}})
    c["next_experiment"] = {
        "id": "R51",
        "budget": "cap 1 disclosed pre-run (restore-only from the "
                  "SAVED r47_frontier_a/b while they survive; the "
                  "boot is the core+rom load only)",
        "hypothesis": "the connect-class +500/+1000 non-determinism "
                      "is a WOUND-DEPTH accumulator: the payment "
                      "= 100 x the accumulated wound on the "
                      "surviving target, tracked by a hidden word "
                      "OUTSIDE the bounded R45 net (0x88..0xA8) - "
                      "the extended wide-net u16 0x60..0x88 + "
                      "0xA8..0xE0 on the connect targets across "
                      "dedicated 1-bullet connects should expose a "
                      "word whose delta co-moves with the payment "
                      "magnitude; SECONDARY: the invulnerability "
                      "predicate (0xab94 + the burning family) "
                      "closes the piercing hole in the corridor "
                      "gate - a bullet fired at an invulnerable-"
                      "state target passes through and kills the "
                      "first vulnerable mortal behind",
        "method": "boot -> restore r47_frontier_a -> the R48/R50 "
                  "direct-read telemetry verbatim + the corridor "
                  "gate with the invulnerability predicate -> "
                  "dedicated 1-bullet CONNECT taps on wounded "
                  "survivors with the EXTENDED wide-net word "
                  "capture (pre/post per tap) -> the wound-"
                  "accumulator hunt in the analysis (any word "
                  "whose delta correlates with the +500-vs-+1000 "
                  "magnitude) -> the magnitude table + the "
                  "invulnerability census",
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
        "what": "R50 the dominance recipe SCALES to CAP_F 2000 "
                "(the third extension, the capsule lever verbatim): "
                "arm A (bot_policy5 verbatim @2000) 1901 / 0 hits / "
                "7 passes / caused 1 = the 8th independent policy5 "
                "reproduction with the score = f - 99 prediction "
                "EXACT (2000 - 99 = 1901); arm B (bot_policy8 "
                "verbatim @2000) 1903 / 0 HITS / 7-of-7 / caused 2 "
                "= the THIRD caused-replication and the FULL "
                "ORACLE (score >= 1550 AND hits 0 AND caused >= 2) "
                "TRUE for the THIRD consecutive round.  HONEST "
                "NOTES: (1) the score axis BROKE ITS TIE by +2 "
                "frames for the first time (B survived 2002f vs "
                "A's 2000f - 1903 = 2002 - 99 exact, the linear "
                "mechanism holds; the committed-seek positioning "
                "shifted a landing frame - a positioning "
                "side-effect, not a mechanism change); (2) the "
                "8th/9th wasp passes never arrived (7 passes at "
                "2000f, density stable - the capsule's density "
                "risk did not materialize at this cap); (3) no "
                "margin floor needed (B took 0 hits, GM 8 safe a "
                "fourth time).  Environment re-verified internet-"
                "first sha-verified 0 boots (9b0bfc08/042b94bb); "
                "the r47b gs1 checkpoint SURVIVED (READ-ONLY "
                "restore); cap 1 disclosed pre-run, boot 1 = the "
                "core+rom load only; 9 offline policy checks "
                "passed BEFORE the boot; 11.6s wall.",
        "status": "VERIFIED",
        "provenance": {
            "source": "r50b_capf2000.py (boot 1) + "
                      "scratch/r50b/boots_used.json (cap 1, no "
                      "amendments) + offline_checks 9/9 pre-boot",
            "evidence": "scratch/r50b/metrics_r50b.json + "
                        "frames_A2000.jsonl + frames_B2000.jsonl"}})
    b["next_experiment"] = {
        "id": "R51",
        "budget": "0-1 boots (restore-only from the r47b gs1 "
                  "checkpoint while it survives)",
        "hypothesis": "the linear score mechanism and the caused "
                      "mechanism hold at CAP_F 2200 (the fourth "
                      "extension): arm B (bot_policy8 verbatim "
                      "@2200) holds hits 0 AND caused >= 2 (the "
                      "FOURTH caused-replication) with score >= "
                      "2101 predicted by score = f - 99; the "
                      "wasp-density risk re-opens with the cap "
                      "(the 8th pass should finally arrive: 6 @1500 "
                      "-> 7 @1700 -> 7 @1800 -> 7 @2000 -> ? @2200); "
                      "arm A = policy5 verbatim @2200 (the 9th "
                      "reproduction check)",
        "method": "offline checks BEFORE any boot -> boot 1 "
                  "core+rom load -> restore the r47b gs1 checkpoint "
                  "-> arm A2200 -> arm B2200 -> arm B2 (tier 12/12) "
                  "only on a B hit -> the oracle line on B + the "
                  "score = f - 99 prediction at 2200 + the pass-"
                  "density vs commitment table (the 8th pass watch)",
        "m2_gate_note": "the score-superiority line stays within "
                        "the dodge axis; no scoring-policy changes"}
    b.setdefault("meta", {})["updated"] = now
    json.dump(b, open(BEE, "w"), indent=1, ensure_ascii=False)
    print("buzzybee capsule: +1 event (now %d), next = %s"
          % (len(ev), b["next_experiment"]["id"]))
    return 0


if __name__ == "__main__":
    main()
