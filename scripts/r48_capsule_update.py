#!/usr/bin/env python3
"""r48_capsule_update.py — R48 round close-out: append the round
events to BOTH capsules (the 60% track to msx, the 40% track to
buzzybee) and replace next_experiment (R49 in each).  Events are
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
        "what": "R48 the FRAME-EXACT TAP PROTOCOL executed (the "
                "capsule lever: per-frame score telemetry COMPOSED "
                "with the single-bullet taps).  NO sandbox rollback "
                "this round: the R47 frontiers r47_frontier_a/b "
                "SURVIVED on disk (verified pre-boot) - cap 1 "
                "disclosed pre-run (the core+rom load ONLY, both "
                "passes restore-only).  Boot 1 ran clean and "
                "DETERMINISTICALLY (11 taps, the same tap/dscore/"
                "corpse tables twice across two boots) but its "
                "RECORDING was corpse-blind: mini_census is built "
                "on scan_entities which SKIPS corpse-st and hp==0 "
                "slots (the union_post lesson applied to per-frame "
                "telemetry), so no death was ever dated at frame "
                "granularity and the per-event decision degraded.  "
                "cap amended 1->2 DISCLOSED (the r47 boot-2 defect "
                "precedent): boot 2 = the same protocol + DIRECT "
                "per-frame table reads (slots 1..39, five words, "
                "unconditional), 29s wall.  Two background launches "
                "died silently inside boot_to_demo before any core "
                "load - refunded per the R45 precedent; the round "
                "ran FOREGROUND per the learned protocol.",
        "status": "VERIFIED",
        "provenance": {
            "source": "r48t1_frame_exact_taps.py (boots 1-2) + "
                      "scratch/r48/boots_used.json (cap 2, the "
                      "recording-defect amendment disclosed "
                      "same-entry)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r48/ "
                        "(r48_boot1.jsonl + r48_boot2.jsonl + "
                        "r48_boot2_report.json)"}})
    ev.append({
        "what": "R48 CORRECTED VERDICT - TWO PAY CLASSES, measured "
                "FRAME-EXACT (r48_analysis_correct.py, offline, "
                "authoritative):  (1) DEATH-INITIATION-LOCKED "
                "payments n=3 - the flat +100 lands EXACTLY on the "
                "0x515c entry frame (the kill registration: dying "
                "state), corpse 0x4BE4 follows 1-4f later (taps "
                "2/3/5; identities x 1284.2/1351.2/1293.2, the "
                "x~1275 cluster = 4 of the dated deaths);  (2) a "
                "SURVIVING-CONNECT payment n=1 - the +500 lands at "
                "tap-1 f_rel 2 where the ONLY measurable event is "
                "slot-20's hit-reaction state change (st 0x42bc) "
                "while slot 20 SURVIVES the connect (its death "
                "initiation is 23f later at tap 2) - the R47 "
                "'ZERO surviving-hit payment' reading is FALSIFIED "
                "at frame granularity and the R45 '+500 attribution "
                "unresolved' is RESOLVED (the slot-20 connect "
                "payment, deterministic across R45/R48).  BOTH pure "
                "models falsified: payments land at the connect/"
                "kill-registration frame, the corpse state lags "
                "1-14f (the dying animation), so tap-granularity "
                "dating (R47) conflated the classes - R47's '+600 = "
                "6 x +100 uniform' was that conflation, and this "
                "session's ledger is +800 (+500 + 100x3) with 16 "
                "dated deaths of which the ZERO-INPUT control walk "
                "shows 4 NATURAL deaths paying 0 (churn baseline "
                "frame-exact for the first time).  The 1-2px/frame "
                "+0x8E screen-x drift is camera churn (the R45 "
                "lesson, now frame-quantified: chips need >= 3px).",
        "status": "VERIFIED",
        "provenance": {
            "source": "r48_analysis_correct.py (offline, no boot; "
                      "the 0x515c-entry frame match is exact in 3/4 "
                      "payments, the +500 matches the only state "
                      "change at its frame)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r48/ "
                        "r48_frame_exact_events.json"}})
    c["next_experiment"] = {
        "id": "R49",
        "budget": "cap 1 disclosed pre-run (restore-only from the "
                  "SAVED r47_frontier_a/b while they survive; the "
                  "boot is the core+rom load only)",
        "hypothesis": "the TWO PAY CLASSES are CLASS-KEYED: the "
                      "+100 death-registration payment is the "
                      "soldier-class kill reward (0x515c entry, "
                      "already 3/3 frame-exact), while the +500 "
                      "surviving-connect payment keys on a "
                      "DIFFERENT target class (slot 20's 0x42bc "
                      "hit-reaction) - aimed taps DEDICATED to "
                      "0x42bc-class targets that are then left "
                      "alive (no follow-up kill) should reproduce "
                      "+500-class payments with the target "
                      "surviving to walk end, and taps dedicated "
                      "to 0x4054/0x5b0c soldiers should yield "
                      "+100-class only; the payment magnitude "
                      "reads off the class, not off kill vs hit",
        "method": "boot -> restore r47_frontier_a -> the direct-read "
                  "telemetry VERBATIM (the R48 recording) -> taps "
                  "GROUPED by target class: >= 3 dedicated 0x42bc "
                  "connects (no kill follow-up) vs >= 3 soldier "
                  "kills -> the frame-exact event table per group "
                  "-> the class-keyed magnitude table; the burning "
                  "states stay excluded AS TARGETS, RECORDED",
        "m2_gate_note": "the INTERACTIVE M2 entry remains gated on a "
                        "clean (deaths=0, no-restart) deep resolve "
                        "posture - unchanged"}
    json.dump(c, open(MSX, "w"), indent=1, ensure_ascii=False)
    print("msx capsule:", len(c["events"]), "events, next =",
          c["next_experiment"]["id"])

    # ---------------- the 40% track: buzzybee ------------------------
    c2 = json.load(open(BEE))
    ev2 = c2["events"]
    ev2.append({
        "what": "R48 the COMMITTED-SEEK round - the FIRST FULL "
                "ORACLE LINE PASS (honest and complete): the "
                "environment verified internet-first sha-verified "
                "BEFORE any boot (0 boots: upstream EXE 9b0bfc08... "
                "byte-identical, committed wrap output 042b94bb... "
                "byte-identical); the r47b gs1 checkpoint SURVIVED "
                "on disk (verified pre-boot, READ-ONLY) - cap 1 = "
                "the core+rom load ONLY; 9 offline policy checks "
                "passed BEFORE the boot (the R46 precedent: the "
                "committed hold does not flip across frames, the "
                "committed seek does not re-pick while the flower "
                "is alive, the tier switch fires at t_enter_min, "
                "every committed reuse passes the guarantee "
                "filter).  Arm A (bot_policy5 verbatim @1700): "
                "1601 / 0 hits / 6 passes / caused 1 - the 6th "
                "independent policy5 reproduction, score EXACTLY "
                "the R47 A1700 line (cross-boot determinism "
                "confirmed).  Arm B (bot_policy8 = the tiered GM "
                "8/12 planner + the flower-proximity hold "
                "COMMITTED through the pickup window + the "
                "committed flower seek): 1601 / 0 HITS / 6 "
                "passes / 6-of-6 dodges / caused 2 - the oracle "
                "line score >= 1550 AND hits 0 AND caused >= 2 is "
                "TRUE for the first time in seven rounds on this "
                "axis.  THE MECHANISM CONFIRMED BY NAME: "
                "commitment was the caused bottleneck - the "
                "decisive pickup attributes seek_dur 134 (>= the "
                "20f window) in flower mode because the seek is "
                "no longer reset by re-picks; the pre-danger "
                "flower-prox holds accumulate seek through the "
                "hold.  No margin floor needed (B took no hits; "
                "GM8 stays safe at this checkpoint, the R45-B "
                "evidence replicated).  Honest notes: the score "
                "axis is structurally tied (score = f - 99, the "
                "R46/R47 mechanism - both arms 1601 at 1700f); "
                "the caused gain is the ONLY delta, which is "
                "exactly what the capsule hypothesis predicted.",
        "status": "VERIFIED",
        "provenance": {
            "source": "r48b_committed_seek.py (offline checks + "
                      "restore-only arms) + scratch/r48b/"
                      "boots_used.json (cap 1)",
            "evidence": "scratch/r48b/ (metrics_r48b.json + "
                        "frames_A1700.jsonl + frames_B1700.jsonl + "
                        "boot_log_r48b.json)"}})
    c2["next_experiment"] = {
        "id": "R49",
        "budget": "0-1 boots (restore-only from the r48b-eligible "
                  "r47b gs1 checkpoint while it survives)",
        "hypothesis": "the caused >= 2 pass REPLICATES (bot_policy8 "
                      "is not a one-checkpoint fluke): the same "
                      "restore-only protocol at CAP_F 1800 (the "
                      "R47 clause) reaches caused >= 2 AGAIN with "
                      "hits 0 and score >= 1701 predicted by "
                      "score = f - 99; the pass-density vs "
                      "commitment table decides whether the "
                      "commitment mechanism scales with wasp "
                      "density (the 8th/9th wasp passes)",
        "method": "arm A = bot_policy5 verbatim @1800 (the control "
                  "line, protocol parity); arm B = bot_policy8 "
                  "@1800 (the committed seek verbatim); the "
                  "oracle line (score >= 1550 AND hits 0 AND "
                  "caused >= 2) evaluated on B; if B takes a hit "
                  "the margin floor files (the R45-B revert "
                  "protocol); offline checks BEFORE any boot "
                  "(the R48 precedent)",
        "m2_gate_note": "the score-superiority line stays within "
                        "the dodge axis; no scoring-policy changes"}
    json.dump(c2, open(BEE, "w"), indent=1, ensure_ascii=False)
    print("buzzybee capsule:", len(c2["events"]), "events, next =",
          c2["next_experiment"]["id"])


if __name__ == "__main__":
    main()
