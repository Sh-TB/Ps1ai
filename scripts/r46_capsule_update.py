#!/usr/bin/env python3
"""r46_capsule_update.py — R46 round close-out: append the round
events to BOTH capsules (the 60% track to msx, the 40% track to
buzzybee) and replace next_experiment (R47 in each)."""
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
        "what": "R46 the ONE-HIT replication round executed (cap 1/1 "
                "DISCLOSED PRE-RUN, restore-only: the SAVED r45 "
                "frontiers were verified on disk BEFORE the boot - "
                "the R45 rollback watch): restore r45_frontier_b "
                "(px 1254.8; ground census 2 - the 13-entity R45 "
                "census was mostly airborne shells) -> zero-input "
                "control tap -> ground-only aimed taps (the R45 "
                "protocol note applied: kind=='enemy' only) -> "
                "restore r45_frontier_a in the same boot -> 34 taps "
                "total, 31s wall.  The in-runner kill table printed "
                "verdict REFUTED - WITHDRAWN the same round by the "
                "offline corrected analysis (corrected-filings "
                "precedent): the verdict counted position churn "
                "(0x8c/0x94/0x8e/0x96 move in the ZERO-INPUT control "
                "tap) as HP chip and ignored the attribution "
                "evidence.",
        "status": "VERIFIED",
        "provenance": {
            "source": "r46t1_onehit_replication.py + "
                      "r46_analysis_correct.py (offline, no boot)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r46/ "
                        "(r46_boot1.jsonl + r46_boot1_report.json + "
                        "corrected_kill_table.json); scratch/r46/ "
                        "boots_used.json entry 1 outcome_corrected"}})
    ev.append({
        "what": "R46 CORRECTED VERDICT - the slot-20 soft-soldier "
                "one-hit SIGNATURE replicates 3/3 deterministically: "
                "the soldier died with the flat +100 at the death "
                "tap in ALL THREE readouts (R45-a tap2, R46-b tap2, "
                "R46-a tap2 - two rounds, three boots) with NO "
                "0x9E/0xA4 movement while alive (0x8E = screen-x "
                "re-confirmed; the wide net shows no decrementing "
                "word anywhere).  BUT the CLASS-WIDE one-hit reading "
                "is UNPROVEN: the >= 3 distinct-kill bar was NOT met "
                "- the frontier worlds hold ~2 ground soldiers each, "
                "and the second soldier died with dscore 0 (R45 tap "
                "11 killed TWO entities - ground 18 + ground 26 - "
                "with +0 = the environmental-kill signature, likely "
                "falling-shell ground bursts crediting nothing); "
                "score events include +100 with NO tracked death "
                "(R45 taps 3/9) and deaths with NO score - score-to-"
                "death attribution stays the open problem.  Harness "
                "lessons (measured, disclosed): (1) the wreck/fire "
                "filter (0xA44C only) missed the evolved burning "
                "states 0xa264/0xa414 - a landed shell burns on the "
                "ground and 12/16 frontier_b taps were wasted on it "
                "(dscore 0 x12); (2) the ground-only census filter "
                "over-pruned: it discarded the air-corpse evidence "
                "that attributes the first-tap +500/+1000 events "
                "(R45's full census shows slots 33+23 entering the "
                "0x4be4 corpse state exactly at the +500 tap); (3) "
                "the st word is a STATE HANDLER, not identity - the "
                "same soldier reads 0x4054/0x42bc/0x5b0c/0x6730 "
                "across taps, so class labels must use the pre-death "
                "row; (4) churn is not chip: any verdict that treats "
                "wide-net movement as damage without the zero-input "
                "control baseline is invalid.",
        "status": "VERIFIED",
        "provenance": {
            "source": "r46_analysis_correct.py (the corrected kill "
                      "table over r45+r46 jsonl)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r46/"
                        "corrected_kill_table.json"}})
    c["next_experiment"] = {
        "id": "R47",
        "budget": "cap 1 disclosed pre-run (restore-only from the "
                  "SAVED r45_frontier_a/b while they survive; the "
                  "boot is the core+rom load only)",
        "hypothesis": "the score system is PER-HIT, not per-kill: a "
                      "single-bullet tap protocol (TAP_FRAMES ~3 = "
                      "about one bullet per tap) from the frontier "
                      "postures yields score deltas of exactly +100 "
                      "per bullet CONNECT on a ground soldier "
                      "(surviving hits included), which would "
                      "reclassify the R45/R46 'one-hit' reading as "
                      "PER-HIT SCORING (the soldier dies at the "
                      "first connect because it is one-hit AND every "
                      "connect pays +100 - the two models agree at "
                      "the death tap and diverge on surviving hits); "
                      "if instead connects score 0 and only the "
                      "death pays +100, the one-hit reading stands; "
                      "the +500/+1000 first-tap events become "
                      "attributable (multi-connect bursts)",
        "method": "boot -> restore r45_frontier_a -> FULL-kind "
                  "census per tap (air included - the R46 ground-"
                  "only filter discarded the attribution evidence) "
                  "-> single-bullet taps (3f Y) at the nearest "
                  "ground enemy with per-tap corpse/score/word "
                  "tables -> restore r45_frontier_b if the census "
                  "thins -> the per-connect score table decides "
                  "per-hit vs per-kill; the burning-ground states "
                  "(0xa264/0xa414 and the landed-shell family) are "
                  "excluded as unkillable scenery",
        "m2_gate_note": "the INTERACTIVE M2 entry remains gated on a "
                        "clean (deaths=0, no-restart) deep resolve "
                        "posture - unchanged"}
    json.dump(c, open(MSX, "w"), indent=1, ensure_ascii=False)
    print("msx capsule: +2 events,", len(c["events"]), "total; "
          "next_experiment =", c["next_experiment"]["id"])

    # ---------------- the 40% track: buzzybee -----------------------
    c = json.load(open(BEE))
    ev = c["events"]
    ev.append({
        "what": "R46 the per-frame score telemetry (the capsule "
                "lever, executed restore-only): boot = the core+rom "
                "load only (ledger cap amended 1->2 DISCLOSED: boot "
                "1 was killed by the operator shell timeout at "
                "f~268/1500 - the runner was healthy, the wall was "
                "underestimated; the re-run added a one-boot timing "
                "probe that measured 407 fps across raw/loop/"
                "telemetry 60f variants - the slowness never "
                "reproduced and the probe world was discarded by a "
                "clean re-restore).  ONE bot_policy5 arm, 1500f, "
                "the R45-B arm-A protocol verbatim from the "
                "preserved r45b gs1 checkpoint (READ-ONLY).  "
                "MECHANISM DECIDED - PER_FRAME_TIME: every score "
                "delta is +1 (n=1401 climb frames = the whole gain, "
                "jumps = []); the only non-climb window is a 32f "
                "ready phase at the start; the 6 wasp passes and "
                "the flower pickups (+997 hp x2, 1 caused) contribute "
                "ZERO score directly.  The 1401 invariant across "
                "four policy families = survival time, not reward "
                "structure - and NOT a policy deficit.  "
                "DETERMINISM: the 3rd independent reproduction of "
                "the exact policy5 line (score 1401 / hp 5666 / 6 "
                "passes / 0 hits - R43-B arm B, R45-B arm A, R46-T) "
                "= cross-process restore determinism re-confirmed.  "
                "The R47 lever follows from the mechanism: score is "
                "TIME, so >= 1550 = survive the climb past 1550 "
                "frames - the CAP_F extension, not a new policy.",
        "status": "VERIFIED",
        "provenance": {
            "source": "r46b_score_telemetry.py (the per-frame "
                      "0x8005883C telemetry arm + the one-boot "
                      "timing probe)",
            "evidence": "scratch/r46b/ (boots_used.json cap 2 with "
                        "the timeout-kill amendment + frames_T.jsonl "
                        "with per-frame sc + metrics_r46b.json + "
                        "boot_log_r46b.json); report "
                        "docs/issue6_r46b_report.md"}})
    c["next_experiment"] = {
        "id": "R47",
        "budget": "0-1 boots (restore-only from the r45b gs1 "
                  "checkpoint while it survives)",
        "hypothesis": "the climb continues past f1500: bot_policy5 "
                      "verbatim at CAP_F 1700 (extend to 1800 only "
                      "if 1700 finishes with 0 hits) reaches score "
                      ">= 1550 with hits == 0 (the mechanism "
                      "predicts ~1550 climb-frames at ~f1582 after "
                      "the 32f ready phase); the REAL risk is not "
                      "scoring but late-game wasp density vs the "
                      "guarantee planner - the first hit past the "
                      "R45-B frontier would be the finding",
        "method": "restore-only, 1 boot max: the R45-B run_arm "
                  "verbatim (protocol parity: same checkpoint, "
                  "same kw, the pass/pickup/attribution machinery "
                  "unchanged) at CAP_F 1700 -> the oracle line "
                  "(score >= 1550 AND hits 0 AND caused >= 2) -> "
                  "the pass-table comparison vs the 1500f runs "
                  "(passes 7-8 density, min_sep trend) -> decide "
                  "whether the dominance recipe scales with time "
                  "or the wasp spawn schedule breaks it",
        "m2_gate_note": "the score-superiority line stays within "
                        "the dodge axis; no policy changes"}
    json.dump(c, open(BEE, "w"), indent=1, ensure_ascii=False)
    print("buzzybee capsule: +1 event,", len(c["events"]), "total; "
          "next_experiment =", c["next_experiment"]["id"])


if __name__ == "__main__":
    main()
