#!/usr/bin/env python3
"""r47_capsule_update.py — R47 round close-out: append the round
events to BOTH capsules (the 60% track to msx, the 40% track to
buzzybee) and replace next_experiment (R48 in each).  Events are
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
        "what": "R47 the SINGLE-BULLET TAP PROTOCOL executed (the "
                "R45 two-stage FOREGROUND protocol, cap disclosed "
                "pre-run).  SANDBOX ROLLBACK DISCLOSED: the R45 "
                "frontiers (r45_frontier_a/b) were LOST to the "
                "sandbox filesystem reset - the capsule contingency "
                "applied verbatim (a rebuild boot, disclosed); "
                "issue5_m1_start (Oct 20) survived.  Stage 1 (boot "
                "1): the tainted frontier rebuild DETERMINISTIC "
                "ACROSS ROUNDS - r47_frontier_a px 1224.9 census 13 "
                "+ r47_frontier_b px 1254.8, 6 deaths/6 "
                "continue-rescues counted and disclosed, TAINTED "
                "lineage - the SAME postures as R45's rebuild "
                "(1224.9/1254.8, restore score 6702) = the 4th "
                "independent reproduction of the rebuild trajectory. "
                "Stage 2 (boot 2->3): boot 2 crashed AFTER the "
                "control tap (a harness defect: the post-tap entity "
                "scan can DROP a slot that died inside the 3f tap; "
                "the per-tap delta build hit a missing key) - "
                "REFUNDED + cap amended 2->3 DISCLOSED (the r46b "
                "precedent); two gate-blocked no-boot attempts also "
                "refunded (the R45 refund precedent).  Boot 3 "
                "clean: 12 FULL-kind taps (1 control + 11 "
                "single-bullet 3f Y) from r47_frontier_a, 28s wall.",
        "status": "VERIFIED",
        "provenance": {
            "source": "r47t1_singletap_taps.py (stages 1-2) + "
                      "scratch/r47/boots_used.json (3 entries, 2 "
                      "refunds, same-entry outcome corrections)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r47/ "
                        "(r47_boot1_s1_report.json + "
                        "r47_boot3_s2_report.json + 2 jsonl)"}})
    ev.append({
        "what": "R47 CORRECTED VERDICT - PER-KILL (kill-locked) "
                "scoring: the cumulative score ledger moved +600 "
                "(6702 -> 7302) while ALL 12 per-tap window deltas "
                "read 0 - the 3f tap window ends before the bullet "
                "ARRIVES (flight ~8-15f at dx ~+50; the R45/R46 24f "
                "bursts masked this by containing the flight).  The "
                "+600 is EXACTLY 6 dated corpse transitions x +100 "
                "(uniform=True; deaths in read-windows 2/2/4/5/7/10 "
                "= slots 19,13,23,27,33,34; three deaths cluster at "
                "x ~1275 = where the bullets converge; st 0x515c "
                "respawned at the SAME x 1274.5 with h 91->90).  "
                "ZERO surviving-hit payment observed: 11 single "
                "bullets, 6 deaths, no +100 that is not a corpse; "
                "the soft soldier slot20 NEVER died AND never paid. "
                "The R45 '+100-no-death' confound (taps 3/9) is "
                "EXPLAINED: R45 recorded corpses only inside the "
                "x-window (out-of-window/out-of-scan kills "
                "invisible); the R47 full-kind tables close it.  "
                "The per-hit alternative survives only in the "
                "unfalsifiable corner (every no-death bullet missed "
                "AND every connect killed).  Harness lessons: (1) "
                "the tap window must contain the bullet FLIGHT; "
                "(2) per-tap score deltas are INVALID for "
                "delayed-pay weapons - the cumulative ledger + "
                "corpse dating is the readout; (3) the entity scan "
                "can drop a slot inside the tap (union_post "
                "direct-table re-reads, fixed in-round).",
        "status": "VERIFIED",
        "provenance": {
            "source": "r47_analysis_correct.py (offline, no boot; "
                      "the control-baseline + corpse-dating rules)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r47/"
                        "corrected_score_table.json"}})
    c["next_experiment"] = {
        "id": "R48",
        "budget": "cap 1 disclosed pre-run (restore-only from the "
                  "SAVED r47_frontier_a/b while they survive; the "
                  "boot is the core+rom load only)",
        "hypothesis": "per-event score attribution is DECIDED by "
                      "composing the r46b per-frame score telemetry "
                      "with the single-bullet tap protocol: the "
                      "exact frame of each +100 event lands at (a) "
                      "the bullet-impact frame on a corpse-to-be "
                      "(per-KILL, locked to the death moment) or "
                      "(b) a connect frame with the target "
                      "surviving (per-HIT); the identity of each "
                      "paying entity (the x~1275 cluster: falling-"
                      "shell mid-air shoots vs ground soldiers) is "
                      "read off the same frames",
        "method": "boot -> restore r47_frontier_a -> per-frame "
                  "0x8005883C-style score reads around each "
                  "single-bullet tap (TAP_FRAMES 3, then a 20f "
                  "readout tail covering the flight window; "
                  "FULL-kind census per read) -> the frame-exact "
                  "event table decides (a) vs (b) per event -> "
                  "restore r47_frontier_b if the census thins; the "
                  "burning-ground states stay excluded AS TARGETS, "
                  "RECORDED",
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
        "what": "R47 the CAP_F extension arm executed (restore-only "
                "arms, boot 1 = the core+rom load AND the gs1 "
                "checkpoint rebuild, cap 1 DISCLOSED PRE-RUN; the "
                "sandbox rollback lost scratch/r45b/"
                "state_r45b_gs1.bin - the environment was rebuilt "
                "INTERNET-FIRST sha-verified BEFORE the boot "
                "(upstream EXE 9b0bfc08... byte-identical "
                "re-fetched from the manifest URL, committed "
                "wrap-script output 042b94bb... byte-identical - "
                "the R45-B precedent, 0 boots).  bot_policy5 "
                "verbatim (the R45-B run_arm, protocol parity, "
                "only the frame cap changed): arm A1700 = score "
                "1601 / 0 hits / 6 passes / caused 1 / hp 5066 / "
                "86 flaps; arm A1800 (the capsule clause: extend "
                "only if A finished 0 hits) = score 1701 / 0 hits "
                "/ 7 passes / caused 1 / hp 5766 / 90 flaps.  "
                "MECHANISM CONFIRMED + EXTENDED: score = "
                "survival_frames - 99 (the same constant overhead "
                "as the 1500f runs: 1401/1601/1701 = the 4th and "
                "5th independent policy5 reproductions) - the "
                "climb scales LINEARLY past f1500 and the ORACLE "
                "score axis (>= 1550) is CROSSED with 0 hits.  THE "
                "DOMINANCE RECIPE SCALES WITH TIME: 6->7 passes, "
                "0 hits at both caps - the wasp spawn schedule "
                "continues at stable density and the guarantee "
                "planner holds.  HONEST NEGATIVE on the full "
                "oracle line: caused >= 2 NOT met (caused 1 for "
                "the THIRD consecutive round - the pickups keep "
                "landing opportunistically: mode=dodge with "
                "seek_dur 0, or seek_dur 8 < the window), so "
                "CAPF_GOAL = false.",
        "status": "VERIFIED",
        "provenance": {
            "source": "r47b_capf_extension.py (arm A1700 + arm "
                      "A1800, the run_arm verbatim with the "
                      "module-global cap override)",
            "evidence": "scratch/r47b/ (boots_used.json cap 1 + "
                        "metrics_r47b.json + boot_log_r47b.json + "
                        "frames_A1700/frames_A1800 jsonl)"}})
    c["next_experiment"] = {
        "id": "R48",
        "budget": "0-1 boots (restore-only from the r47b gs1 "
                  "checkpoint while it survives)",
        "hypothesis": "the caused>=2 clause closes with the "
                      "R45-B tier evidence: the GM8 pre-danger "
                      "tier is SAFE (453 dodge frames, zero hits, "
                      "measured R45-B) and widens the candidate "
                      "set exactly when flowers are reachable - "
                      "bot_policy8 = the tiered-margin planner "
                      "(GM 8 pre-danger / GM 12 in-window) with "
                      "the flower-proximity hold COMMITTED through "
                      "the pickup window (seek held until pickup "
                      "or the window opens, not re-planned away) "
                      "at CAP_F 1700 reaches caused >= 2 with "
                      "hits 0 and score >= 1550 (score = f - 99 "
                      "predicts 1601 at 1700f)",
        "method": "restore-only, 1 boot max: arm A = bot_policy5 "
                  "verbatim at 1700 (the R47 control line, "
                  "protocol parity) vs arm B = bot_policy8 (the "
                  "tiered planner + the committed seek) at 1700 "
                  "-> the oracle line (score >= 1550 AND hits 0 "
                  "AND caused >= 2) -> if B takes a hit, the "
                  "margin floor files (GM8 rejected at this "
                  "checkpoint, the R45-B revert protocol); the "
                  "pass-table + seek-duration tables vs the R47 "
                  "arms decide whether commitment or reach was "
                  "the caused bottleneck",
        "m2_gate_note": "the score-superiority line stays within "
                        "the dodge axis; no scoring-policy changes"}
    json.dump(c, open(BEE, "w"), indent=1, ensure_ascii=False)
    print("buzzybee capsule: +1 event,", len(c["events"]), "total; "
          "next_experiment =", c["next_experiment"]["id"])


if __name__ == "__main__":
    main()
