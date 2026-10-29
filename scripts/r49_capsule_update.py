#!/usr/bin/env python3
"""r49_capsule_update.py — R49 round close-out: append the round
events to BOTH capsules (the 60% track to msx, the 40% track to
buzzybee) and replace next_experiment (R50 in each).  Events are
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
        "what": "R49 the CLASS-KEYED tap protocol executed (the "
                "capsule lever verbatim: the R48 direct-read "
                "telemetry + taps GROUPED by target class - CONNECT "
                "taps = ONE bullet on a fresh soft target then the "
                "slot is NEVER fired at again, vs KILL taps on "
                "fresh soldiers).  NO sandbox rollback: the R47 "
                "frontiers r47_frontier_a/b SURVIVED on disk "
                "(verified pre-boot); cap 1 disclosed pre-run (the "
                "core+rom load ONLY, both passes restore-only), "
                "boot 1 clean 29s wall, ledger 1/1 spent, no "
                "amendments.  GROUP SHORTFALL recorded honestly: "
                "CONNECT group 2/4 (a-tap1 + b-tap1 both on the "
                "frontier-frozen slot20 mid-0x42bc; 6 connect taps "
                "missed - no 0x42bc entry), KILL group 0/3 (the "
                "census thinned: the spawner zone x~1277-1351 "
                "churns cycling entities - 0xaec8 spawn -> walk -> "
                "0x515c -> 0x4be4 - and the aimed fresh soldiers "
                "ONE-HIT-registered instead of connecting: slots "
                "22/18 died to the single bullet with the full "
                "0x515c->0x4be4 chain).  The two no-follow-up "
                "connect targets did NOT survive to walk end "
                "(slot20 died of the wound 1-3 taps later, dated "
                "frame-exact) - but the connect payment itself "
                "landed while the target was ALIVE in 0x42bc.",
        "status": "VERIFIED",
        "provenance": {
            "source": "r49t1_class_keyed.py (boot 1) + "
                      "scratch/r49/boots_used.json (cap 1, no "
                      "amendments)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r49/ "
                        "(r49_boot1.jsonl + r49_boot1_report.json)"}})
    ev.append({
        "what": "R49 CORRECTED VERDICT (r49_analysis_correct.py v2, "
                "offline, authoritative - GLOBAL-frame per-slot "
                "matcher, the v1 target-slot-only check was blind "
                "to concurrent entity cycles):  (1) the "
                "SURVIVING-CONNECT +500 REPLICATED (a-tap1: the "
                "+500 lands with slot20 in 0x42bc at the pay frame "
                "and ZERO registrations within the flight lag "
                "window [-2,+6]; slot20 then RECOVERS to 0x5b0c "
                "and walks on - n=2 across R48/R49);  (2) the "
                "+100 kill payments replicated n=4, and ALL FOUR "
                "co-land EXACTLY (lag 0) on a 0x515c registration - "
                "BUT none of the four victims is the AIMED target: "
                "all four are CYCLING ZONE ENTITIES registered in "
                "the bullet corridor (slot33-re@1284.2, slot23@"
                "1351.2, slot10-re@1293.2, slot9@1343.8) = the "
                "payment model is REFINED to PLAYER-BULLET-VICTIM-"
                "LOCKED: only the bullet's actual victim pays; the "
                "11 zone/wound registrations (slot22, slot18, "
                "slot20's wound death, slot33's zone death, ...) "
                "all paid 0, and the ZERO-INPUT control walks show "
                "0 jumps again (the churn baseline);  (3) "
                "UNRESOLVED RESIDUAL n=1: the IDENTICAL connect "
                "context paid +1000 once (b-tap1) - the +500 extra "
                "co-lands 2-4 rows AFTER slot33's zone registration/"
                "corpse (outside the lag window); candidates: the "
                "0xae7c-class kill paying +500 / connect magnitude "
                "non-determinism / a hidden second pay event.  The "
                "STRONG class-keyed form (the magnitude reads off "
                "the class deterministically) is FALSIFIED by the "
                "+500-vs-+1000 identical-context pair; the WEAK "
                "form (connect +500 / bullet-victim kill +100) "
                "stands on unconfounded n=1 + n=4.  Session ledger "
                "+1900 across 11 aimed taps (a: +800, b: +1100).",
        "status": "VERIFIED",
        "provenance": {
            "source": "r49_analysis_correct.py (offline, no boot) "
                      "over the r49_boot1.jsonl global-frame "
                      "sequence",
            "evidence": "data/games/SLUS-01212/truck_evidence/r49/ "
                        "r49_class_keyed_table.json"}})
    c["next_experiment"] = {
        "id": "R50",
        "budget": "cap 1 disclosed pre-run (restore-only from the "
                  "SAVED r47_frontier_a/b while they survive; the "
                  "boot is the core+rom load only)",
        "hypothesis": "the payment model is PLAYER-BULLET-VICTIM-"
                      "LOCKED with per-class magnitudes (+100 the "
                      "soft-soldier kill reward, +500 the 0x42bc "
                      "surviving-connect) - a CONTROLLED-CORRIDOR "
                      "tap protocol (fire ONLY when the census "
                      "shows the aimed target as the ONLY mortal "
                      "entity in the bullet corridor, i.e. no "
                      "cycling zone entity between player and "
                      "target; prefer targets dx > 100 beyond the "
                      "x~1277-1351 spawner cluster) yields n >= 3 "
                      "clean per-class payments with ZERO "
                      "co-landing ambiguity and settles the "
                      "magnitude table; the movement-only control "
                      "(walk 3f + 20f idle, no Y) tests whether "
                      "the corridor churn alone can pay; the "
                      "0xae7c-class census (slot33's class) dates "
                      "its kills to settle the +1000 residual",
        "method": "boot -> restore r47_frontier_a -> the R48/R49 "
                  "direct-read telemetry verbatim -> the corridor "
                  "census gate before EVERY tap (skip the tap and "
                  "re-census when the corridor is occupied) -> "
                  "CONNECT group (no follow-up) AND KILL group "
                  "until n >= 3 clean each or the census thins -> "
                  "r49-style offline global-frame analysis -> the "
                  "magnitude table",
        "m2_gate_note": "the INTERACTIVE M2 entry remains gated on "
                        "a clean (deaths=0, no-restart) deep "
                        "resolve posture - unchanged"}
    c.setdefault("meta", {})["updated"] = now
    json.dump(c, open(MSX, "w"), indent=1, ensure_ascii=False)
    print("msx capsule: +%d events (now %d), next = %s"
          % (2, len(ev), c["next_experiment"]["id"]))

    # ---------------- the 40% track: buzzybee -----------------------
    b = json.load(open(BEE))
    ev = b["events"]
    ev.append({
        "what": "R49 the caused >= 2 pass REPLICATED at CAP_F 1800 "
                "(the capsule lever verbatim): arm A (bot_policy5 "
                "verbatim @1800) 1701 / 0 hits / 7 passes / caused "
                "1 = the 7th independent policy5 reproduction and "
                "EXACTLY the R47 A1800 control line (cross-boot "
                "determinism held); arm B (bot_policy8 verbatim "
                "@1800) 1701 / 0 HITS / 7-of-7 / caused 2 - the "
                "FULL ORACLE (score >= 1550 AND hits 0 AND caused "
                ">= 2) TRUE for the SECOND consecutive round = "
                "bot_policy8 is NOT a one-cap fluke.  The score = "
                "f - 99 prediction EXACT (1800 - 99 = 1701, both "
                "arms).  The commitment mechanism CONFIRMED as the "
                "caused bottleneck again: the decisive pickup "
                "attributes seek_dur 134 (>= the 20f window) in "
                "flower mode (the R48 signature replicated) plus "
                "one seek_dur 8 opportunistic; no margin floor "
                "needed (B took 0 hits, the R45-B revert never "
                "fired).  Pass-density table: 7 passes at 1800f "
                "(the 8th did not arrive before cap) - density "
                "stable, the planner held.  Honest note: the "
                "score axis is STRUCTURALLY TIED (score = f - 99 "
                "- both arms 1701); the caused gain is the ONLY "
                "delta, exactly as the capsule predicted.  "
                "Environment re-verified internet-first sha-"
                "verified 0 boots (9b0bfc08/042b94bb); the r47b "
                "gs1 checkpoint SURVIVED on disk (READ-ONLY "
                "restore); cap 1 disclosed pre-run, boot 1 = the "
                "core+rom load only; 9 offline policy checks "
                "passed BEFORE the boot (the R48 precedent); 10.7s "
                "wall.",
        "status": "VERIFIED",
        "provenance": {
            "source": "r49b_capf1800_replication.py (boot 1) + "
                      "scratch/r49b/boots_used.json (cap 1, no "
                      "amendments) + offline_checks 9/9 pre-boot",
            "evidence": "scratch/r49b/metrics_r49b.json + "
                        "frames_A1800.jsonl + frames_B1800.jsonl"}})
    b["next_experiment"] = {
        "id": "R50",
        "budget": "0-1 boots (restore-only from the r47b gs1 "
                  "checkpoint while it survives)",
        "hypothesis": "the dominance recipe SCALES to CAP_F 2000 "
                      "(the third extension): arm B (bot_policy8 "
                      "verbatim @2000) holds hits 0 AND caused "
                      ">= 2 (the third caused-replication) with "
                      "score >= 1901 predicted by score = f - 99; "
                      "the REAL RISK is late-game wasp density vs "
                      "the guarantee planner (the pass count grows "
                      "7 -> ~8-9; a hit at GM8 files the margin "
                      "floor per the R45-B revert protocol); arm A "
                      "= policy5 verbatim @2000 (the control line "
                      "and the 8th reproduction check)",
        "method": "offline checks BEFORE any boot (the R48/R49 "
                  "precedent) -> boot 1 core+rom load -> restore "
                  "the r47b gs1 checkpoint -> arm A2000 -> arm "
                  "B2000 -> arm B2 (tier 12/12) only on a B hit -> "
                  "the oracle line (score >= 1550 AND hits 0 AND "
                  "caused >= 2) evaluated on B + the score = f - 99 "
                  "prediction check at 2000 + the pass-density vs "
                  "commitment table (the 8th/9th passes)",
        "m2_gate_note": "the score-superiority line stays within "
                        "the dodge axis; no scoring-policy changes"}
    b.setdefault("meta", {})["updated"] = now
    json.dump(b, open(BEE, "w"), indent=1, ensure_ascii=False)
    print("buzzybee capsule: +%d events (now %d), next = %s"
          % (1, len(ev), b["next_experiment"]["id"]))
    return 0


if __name__ == "__main__":
    main()
