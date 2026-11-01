#!/usr/bin/env python3
"""r66_capsule_update.py — R66 round close-out: append the round
events to the MSX capsule and replace next_experiment (R67).

R66 events (all provenance-complete):
  1. the corridor-gate starvation ROOT CAUSE (the GATE_DIAG dump).
  2. the corrected predicate + the +500 pay-frame capture.
  3. the pay-frame law + the accumulator-candidate resolution.
  4. the fourth runtime game (the product path) + the determinism.
"""
from __future__ import annotations

import json
import time

MSX = ("/home/z/my-project/ps1ai/data/knowledge/msx/capsule.json")


def main():
    now = time.strftime("%FT%TZ", time.gmtime())
    c = json.load(open(MSX))
    ev = c["events"]
    ev.append({
        "what":
            "R66 gate diagnostics FIRST (the R53 capsule lever): the "
            "per-skip GATE_DIAG dump on r66_frontier_a (13 skips, "
            "r66_boot3_s2a.jsonl) ROOT-CAUSED the R52 starvation - "
            "the R50/R51 corridor predicate counted non-absorbing, "
            "non-paying entities as blockers: the bullet-TRANSPARENT "
            "0xab94 wasp (slot30, 8 rejections; the n=4 piercing "
            "evidence) and in-flight projectile_air rows (0xbdf8/"
            "0x1be0/0x2950/0x9558/0xac64, the next-highest "
            "blockers); the player NEVER advanced (a single px value "
            "1255.2 across all skips).  A protocol-predicate defect "
            "in the MSX workstream, NOT an observer or runtime "
            "defect.",
        "status": "OBSERVED",
        "provenance": {
            "source": "scripts/r66t1_payframe_destarve.py pass A "
                      "(boot 3 of the disclosed R66 ledger)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r66/"
                        "r66_boot3_s2a.jsonl",
        },
    })
    ev.append({
        "what":
            "R66 the +500 capture AT THE PAY FRAME (the R48-R52 "
            "missing raw material): pass B (the corrected predicate "
            "- blockers must absorb the bullet or register the "
            "payment - plus the bounded forward advance) tap 6: "
            "slot16 st_pre 0x1e38 (a NON-wound-recovery state) "
            "dx +20.3, score 7702->8202 (+500) at tail f1 = the "
            "bullet-impact frame, victim still pre-hit; 0x5b0c death "
            "registration at tail f3; the slot12@0xa0 pulse (257->2, "
            "rec 4 - the R52 wound shape replicated) co-timed with "
            "the registration.  Two more +1000s banked (passA tap2 "
            "st_pre 0x42bc pay tail f3; passB tap2 st_pre 0x3f48 pay "
            "tail f4) - the magnitude table is now +500 x4 vs +1000 "
            "x7.  THE PAY-FRAME LAW: the accumulator pays on the "
            "internal damage event ~2 frames BEFORE the visible "
            "death registration (all three R66 captures).  The "
            "+500 class is NOT confined to surviving 0x42bc "
            "connects; freshness-spread SUPPORTED not proven; kills "
            "do not always pay (passB t15: 0xa718->0x515c with "
            "dscore=0).",
        "status": "OBSERVED",
        "provenance": {
            "source": "scripts/r66t1_payframe_destarve.py pass B "
                      "(boot 4) + scripts/r66_analysis_correct.py "
                      "(offline)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r66/"
                        "r66_boot4_s2b.jsonl + r66_analysis.json",
        },
    })
    ev.append({
        "what":
            "R66 the accumulator candidate RESOLVED as a witness, "
            "not a discriminator: slot12@0xa0 pulses 257/258/1/2 "
            "continuously (zone churn) and dips to 2 co-timed with "
            "EVERY kill registration (n=2 replicated); its instant "
            "pay-frame value is churn phase - one of the BANKED "
            "+1000 pay-frame vectors also shows 257, so the "
            "zero-overlap property fails on the wider set.  The "
            "target-slot pay-frame vectors DO separate this round "
            "(19 offsets, +500 n=1 vs +1000 n=4) but identity words "
            "dominate; the discriminator stays PENDING until n>=2 "
            "+500 captures exist (the delay signature +500 tail-f1 "
            "vs +1000 tail-f3/f4 is the lead).",
        "status": "OBSERVED",
        "provenance": {
            "source": "scripts/r66_analysis_correct.py (offline, "
                      "zero boots)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r66/"
                        "r66_analysis.json",
        },
    })
    ev.append({
        "what":
            "R66 the FOURTH RUNTIME GAME: metal_slug_x registered "
            "(adapter 0.2.0 + the deterministic Mission-1 rules "
            "policy with the corrected corridor predicate; 19 "
            "offline tests incl. the isolation suite).  The product "
            "path ran for real (play metal_slug_x): byte-identical "
            "runs, ep1 death 1666f score 1100 at the armored-truck "
            "encounter (px ~1164), ep2 388f score 1300; legal "
            "inputs only, zero RAM writes, no save-state rewinds, "
            "no training.  Mission 1 NOT cleared - the truck fight "
            "is the next blocker.  The frontier rebuild re-proven "
            "6-for-6 (px 1224.9/1254.8 byte-exact again).",
        "status": "TESTED",
        "provenance": {
            "source": "ps1play/adapters/metal_slug_x/ + "
                      "scripts/r66_gameplay_record.py",
            "evidence": "data/games/SLUS-01212/truck_evidence/r66/"
                        "r66_product_run.json + product_run/",
        },
    })
    c["next_experiment"] = {
        "id": "R67",
        "budget": "restore-only arms from the r66 frontiers while "
                  "they survive on disk (a rebuild boot only if "
                  "lost, disclosed)",
        "hypothesis":
            "the delay signature (+500 pays at tail f1, +1000 at "
            "tail f3/f4) plus the 19 candidate offsets separate the "
            "magnitudes once n>=2 +500 captures exist; the corrected "
            "gate makes fresh 0x4054 targets reachable at the "
            "frontiers",
        "method":
            "restore r66_frontier_a/b -> CONNECT taps preferring "
            "fresh 0x4054 with the pay-frame telemetry verbatim "
            "until TWO +500 captures land -> the zero-overlap test "
            "on the widened set -> the product-path truck campaign "
            "(grenade sequencing hp_a4 300/-100 per grenade, the "
            "R38-R52 A/B evidence; soldier prioritization before "
            "the truck gun) as the separate gameplay track",
        "m2_gate_note": "unchanged - the INTERACTIVE M2 entry stays "
                        "gated on a clean (deaths=0, no-restart) "
                        "deep resolve posture",
    }
    c["meta"]["last_updated"] = now
    c["meta"]["last_commit_note"] = (
        "R66: the corridor-gate starvation ROOT-CAUSED and fixed; "
        "the +500 captured at the pay frame; the pay-frame law "
        "established; metal_slug_x the fourth runtime game "
        "(GAMEPLAY_VERIFIED package v0.2.0); Mission 1 still open "
        "(the truck).")
    with open(MSX, "w") as f:
        json.dump(c, f, indent=1)
    print("capsule events now:", len(ev))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
