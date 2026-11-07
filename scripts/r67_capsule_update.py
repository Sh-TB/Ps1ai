#!/usr/bin/env python3
"""r67_capsule_update.py — R67 round close-out: append the round
events to the MSX capsule and replace next_experiment (R68).

R67 events (all provenance-complete):
  1. the +500 hunt executed (restore-only, cap 3): 0 NEW +500
     captures — the goal NOT met; the amendment-G lesson (the gate
     order change moved the deterministic trajectory off the R66
     +500 posture) and the target-starved frontier landscape.
  2. the widened-set zero-overlap test: the discriminator stays
     PENDING (single-capture separation); the +1000 class
     strengthened (n=6 pay-frame vectors; the st_pre->tail delay
     signature replicated: 0x42bc->tail3, 0x3f48->tail4 in BOTH
     R66 and R67).
  3. the product-path truck campaign: the T1 identity fix (the
     (6,h=64) false-positive trap caught by the product run + the
     probe), the rear fight (the BACK action), the truck KILLED by
     the T2 3-lobs sequencing, the record score 2300, the blast
     retreat + the outer-edge hold; the next blocker named.
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
            "R67 the +500 HUNT executed (the capsule lever "
            "verbatim; restore-only from the r66 frontiers, ledger "
            "cap 3 disclosed pre-run, all 3 spent: env probe + "
            "frontier_a + frontier_b): 0 NEW +500 captures - the "
            "n>=2 goal NOT met, the +500 class stands at n=1 (the "
            "R66 capture).  THE AMENDMENT-G LESSON: the disclosed "
            "0x5b0c gate-corpset alignment (the product-adapter "
            "contract; the dry-run finding) changed the tap ORDER "
            "on the byte-exact frontier_b and the trajectory "
            "diverged EXACTLY at tap 6 (R66: slot16 0x1e38 +500; "
            "R67: slot18 0x540c +100) - the +500 capture is a "
            "TRAJECTORY-SENSITIVE posture, not a standing property "
            "of the frontier.  The landscape: BOTH frontiers are "
            "target-starved past the spawner-cluster edge (the "
            "de-starve advance walked px 1246->1540 / 1254->1546 "
            "and found NO targetable enemy rows); the fresh 0x4054 "
            "soldiers exist only AT the frontier at restore time "
            "(frontier_a census: slot20 0x4054) and churn out of "
            "the fresh class before the tap lands.  The +1000 "
            "class REPLICATED x2 this round (0x42bc pay tail f3; "
            "0x3f48 pay tail f4 - the exact R66 st_pre->tail "
            "delay signature).",
        "status": "OBSERVED",
        "provenance": {
            "source": "scripts/r67_env_probe.py (boot 1) + "
                      "scripts/r67t1_payframe_500hunt.py (boots "
                      "2-3) + scripts/r67_analysis_correct.py "
                      "(offline)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r67/"
                        "r67_boot2_s2a.jsonl + r67_boot3_s2b.jsonl"
                        " + r67_analysis.json + r67_env_probe.json",
        },
    })
    ev.append({
        "what":
            "R67 the WIDENED-SET zero-overlap test (the capsule "
            "lever's second step): +500 n=1 pay-frame vector vs "
            "+1000 n=6 vectors (2 R52 + 2 R66 + 2 R67) - 19 "
            "union-net offsets separate the single +500 vector "
            "from ALL six +1000 vectors with zero overlap, but "
            "with n=1 the intersection IS that capture's own set "
            "(identity words dominate) - the CLASS discriminator "
            "stays honestly PENDING until n>=2 +500 captures "
            "exist.  What IS established: the +1000 pay-frame "
            "vectors reproduce the delay signature ACROSS ROUNDS "
            "(0x42bc -> tail f3 in R66 AND R67; 0x3f48 -> tail f4 "
            "in R66 AND R67) - the st_pre->delay law is the "
            "strongest live lead.  The magnitude table: +500 x4 "
            "vs +1000 x9.",
        "status": "OBSERVED",
        "provenance": {
            "source": "scripts/r67_analysis_correct.py (offline, "
                      "zero boots)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r67/"
                        "r67_analysis.json (widened_zero_overlap "
                        "+ delay_signature + magnitude_table)",
        },
    })
    ev.append({
        "what":
            "R67 the PRODUCT-PATH TRUCK CAMPAIGN (the lever's third "
            "step; policy msx_mission1_rules 1.1.0->1.4.2 + the "
            "adapter 0.3.0, 40 offline tests): THE ARMORED TRUCK "
            "KILLED ON THE PRODUCT PATH - the T2 grenade "
            "sequencing (3 lobs x -100 vs hp_a4 300, the capsule "
            "semantics verbatim) took the truck to zero and the "
            "death screenshot shows it AIRBORNE; ep1 score 2300 = "
            "the RECORD product-path score (the previous best "
            "1300, R66).  The evidence-driven rule chain that got "
            "there: T1 the truck identity = the 0x9E88 state word "
            "(code 7) - the v1.1.0 (sc=6, h=64) identity was a "
            "FALSE-POSITIVE TRAP (ground soldiers in walk/throw "
            "states also present (6, h=64): the hold froze at px "
            "493 on a scenery row; the read-only truck-zone probe "
            "read the REAL truck live at 937.5/h64/a4=300); T3 "
            "soldiers-before-the-truck-gun (a clear-line escort "
            "holds the lob; a corridor-blocked escort does not - "
            "the R49 model); the REAR FIGHT (the BACK action = the "
            "legal LEFT button; the loop-probe evidence: at the "
            "section pin the wave AND the truck are BEHIND the "
            "player - a forward-only policy stands pinned while "
            "the rear kills it; three identical v1.0.0-v1.3.0 "
            "deaths); T5 the outer-edge hold (90..135; the dx-52 "
            "hold LOST the gun duel); T7 the blast retreat (the "
            "3-lobs kill exploded the player standing in the "
            "band).  THE CADENCE LAW (v1.2.0's regression, "
            "restored in v1.3.0): the fire cadence is part of the "
            "deterministic wave trajectory - the top-tick 12f "
            "cadence starved the wave (0 kills, the truck never "
            "entered, zero a4>=100 rows in the probe), the "
            "v1.0.0 13f rhythm reproduced the R66 record "
            "byte-exact.  Mission 1 NOT cleared: the post-kill "
            "death (the second truck / the death animation) is "
            "the named next blocker; ep2 continues from the "
            "section start (score 2300 at 366f).",
        "status": "OBSERVED",
        "provenance": {
            "source": "ps1play/adapters/metal_slug_x/policy.py "
                      "v1.4.2 + adapter.py 0.3.0 + "
                      "scripts/r67_product_loop_probe.py + "
                      "scripts/r67_truckzone_probe.py (read-only "
                      "product-stack diagnostics)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r67/"
                        "r67_product_run.json + product_run/ "
                        "(episodes.jsonl iteration lineage + "
                        "shots) + r67_truckzone_probe.jsonl + "
                        "r67_product_loop_probe.jsonl",
        },
    })
    c["meta"]["last_updated"] = now
    c["meta"]["last_commit_note"] = (
        "R67: the +500 hunt executed (0 new; the amendment-G "
        "trajectory lesson), the widened-set zero-overlap test "
        "(PENDING, n=1 vs n=6; the st_pre->delay law replicated), "
        "and the product-path truck campaign: THE TRUCK KILLED "
        "(T2 3-lobs vs hp_a4 300), the record score 2300, the "
        "identity/cadence/rear-fight/blast-retreat rule chain, "
        "40 offline tests green.  Mission 1 stays OPEN.")
    c["next_experiment"] = {
        "id": "R68",
        "budget": "restore-only arms from the r66 frontiers while "
                  "they survive on disk; product-path boots are "
                  "the separate gameplay track (the R67 "
                  "precedent)",
        "hypothesis":
            "the post-kill death is the second truck / the death "
            "animation: a wreck-aware policy (the wreck 0xA44C "
            "and the death state 0xA304 are already capsule "
            "knowledge) that retreats THROUGH the truck-kill and "
            "re-engages the SECOND truck with the same T2 "
            "sequencing clears the roadblock section; in "
            "parallel, n>=2 +500 captures need the R66 tap order "
            "replayed VERBATIM (the amendment-G gate reverted "
            "for the hunt only) - the trajectory sensitivity "
            "makes the tap order part of the experiment",
        "method":
            "product-path: play metal_slug_x with the R68 policy "
            "(wreck-aware T7 extension + the second-truck "
            "sequencing) until the roadblock section clears; "
            "experiment-track: ONE restore-only boot replaying "
            "the R66 pass-B tap sequence verbatim (the corridor "
            "gate as committed in r66t1, not the r67 "
            "amendment-G variant) for the third +500 attempt; "
            "the zero-overlap test re-runs on any new capture",
        "m2_gate_note": "unchanged - interactive M2 entry stays "
                        "gated on a clean (deaths=0, no-restart) "
                        "deep resolve posture",
    }
    with open(MSX, "w") as f:
        json.dump(c, f, indent=1, ensure_ascii=False)
    print("capsule updated:", MSX)
    print("events:", len(c["events"]))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
