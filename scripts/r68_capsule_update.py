#!/usr/bin/env python3
"""r68_capsule_update.py — R68 round close-out: append the round
events to the MSX capsule and replace next_experiment (R69).

R68 events (all provenance-complete):
  1. THE +500 n>=2 GOAL MET: the R66 pass-B tap sequence replayed
     VERBATIM (the corridor gate as committed in r66t1) on the
     byte-exact rebuilt frontier -> the +500 captured at tap 6,
     slot16, st_pre 0x1e38, pay tail f1 — the causal chain
     BYTE-IDENTICAL to the R66 capture; the tap kinds identical to
     the R66 pass-B (the amendment-G lesson CONFIRMED: the gate
     variant WAS the divergence).
  2. THE WIDENED-SET ZERO-OVERLAP DISCRIMINATOR RESOLVED: n=2 +500
     vectors (R66 t6 + R68 t6) vs n=7 +1000 banked vectors — 19
     union-net offsets separate EVERY +500 from EVERY +1000
     (0x60..0xc6 intersection); the +500 delay = tail f1 (2/2),
     the +1000 delay = tail f3/f4.
  3. THE R67 CORRECTION (the honest-registry law): "the truck
     KILLED, score 2300" REFUTED — the probe read a4=160 at the
     v1.4.2 death; the truck has NEVER been killed on the product
     path; the score came from the wave kills + chip events.
  4. THE PRODUCT-PATH FAILURE-MODE MAP (three probe-pinned
     variants): the v1.5.0 W8/W9 (the kill never lands — the trace
     byte-identical to v1.4.2), the v1.6.0 chase (the band window
     + the a4 floor 80; the record 2800), the v1.6.1 chip-stand
     (the bullets BLOCKED behind the pin — a4 frozen at 300; the
     regression 1400), the v1.6.2 chase+gre40 (the record tied
     2800; the connect rate ~1/10 = the named R69 blocker).
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
            "R68 the +500 n>=2 GOAL MET (the capsule lever's "
            "experiment track; ledger cap 3 disclosed pre-run, "
            "3/3 spent: env probe + the stage-1 frontier rebuild "
            "(the disclosed SIXTH-rollback contingency; the "
            "rebuilt arms byte-exact — frontier_px 1254.8 = the "
            "R66 record, the determinism dividend now 7-for-7) + "
            "the pass-B hunt): the R66 pass-B tap sequence "
            "replayed VERBATIM (the corridor gate as committed "
            "in r66t1 — combat.CORPSE_ST {0x4BE4, 0x5CC8}, the "
            "amendment-G exclusion NOT applied) and THE +500 "
            "CAPTURED AT TAP 6: slot16, st_pre 0x1e38, pay tail "
            "f1 — the causal chain BYTE-IDENTICAL to the R66 "
            "capture, and the tap-kind sequence IDENTICAL to the "
            "R66 pass-B end to end.  THE AMENDMENT-G LESSON "
            "CONFIRMED BY REPRODUCTION: the gate variant WAS the "
            "R67 divergence; the tap order is part of the "
            "experiment.  The +500 class stands n=2.  Honest "
            "note: the CONNECT/KILL counters read 0/0 (the "
            "0x42bc wound registration never appeared in the "
            "tap windows) while the score PAID at taps 2 (+1000) "
            "and 6 (+500) — the pay-before-registration law "
            "(the accumulator pays on the internal damage event "
            "~2 frames before the visible registration) now "
            "seen from the missing-registration side too.",
        "status": "OBSERVED",
        "provenance": {
            "source": "scripts/r68_env_probe.py (boot 1) + "
                      "scripts/r68_rebuild.py (boot 2) + "
                      "scripts/r68_passb_hunt.py (boot 3) + "
                      "scripts/r68_analysis_correct.py (offline)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r68/"
                        "r68_env_probe.json + r68_boot2_s1_report"
                        ".json + r68_boot3_s2b.jsonl + "
                        "r68_analysis.json",
        },
    })
    ev.append({
        "what":
            "R68 the WIDENED-SET ZERO-OVERLAP DISCRIMINATOR "
            "RESOLVED (the R67 PENDING item closed): +500 n=2 "
            "pay-frame vectors (R66 passB t6 + R68 passB t6) vs "
            "+1000 n=7 banked vectors (2 R52 + 2 R66 + 2 R67) — "
            "19 union-net offsets separate EVERY +500 vector "
            "from EVERY +1000 vector (the intersection: 0x60, "
            "0x62, 0x6c, 0x70, 0x74, 0x78, 0x7a, 0x8c, 0x8e, "
            "0x94, 0x96, 0xc6, ...).  THE DELAY SIGNATURE IS "
            "CLASS-CONSISTENT: the +500 pays at tail f1 (2/2 "
            "captures, the bullet-impact frame), the +1000 pays "
            "at tail f3/f4 (the wound-recovery class) — the "
            "st_pre->delay law is now a two-class law.  The "
            "magnitude table: +500 x5 vs +1000 x9.  The "
            "discriminator offsets are the payment=f(wound_"
            "state) fingerprint candidates for the R69 "
            "source-first hunt (the xref of the 0xa0-adjacent "
            "writer).",
        "status": "OBSERVED",
        "provenance": {
            "source": "scripts/r68_analysis_correct.py (offline, "
                      "zero boots; the r67 reusable core "
                      "verbatim)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r68/"
                        "r68_analysis.json (zero_overlap_test: "
                        "n_intersection=19, verdict RESOLVED)",
        },
    })
    ev.append({
        "what":
            "R68 THE R67 CORRECTION (the honest-registry law): "
            "the R67 event 'THE ARMORED TRUCK KILLED ON THE "
            "PRODUCT PATH (T2 3-lobs vs hp_a4 300, score 2300)' "
            "is REFUTED by the R68 read-only product-stack probe "
            "(r68_postkill_probe, the every-frame entity table "
            "from f=1150): the truck row sat at a4=160 (0x9E88, "
            "x 937.5, h 64, slot 14) from f1160 to the v1.4.2 "
            "death at f1462 — the truck was NEVER killed; the "
            "score 2300 came from the wave kills + chip events; "
            "the three lobs (f875/f972/f1063) landed ONE connect "
            "(-100) + chips (-40).  The 'truck AIRBORNE' death-"
            "shot reading is likewise corrected (the airborne "
            "object is the encounter's follower, not the truck's "
            "death animation).  The player died PINNED at px "
            "1164 (the section pin) with the parked truck behind "
            "at dx -226.5 — outside the lob band (135) and the "
            "chip window reach (the bullets never arrive: see "
            "the R68 failure-mode map).",
        "status": "OBSERVED",
        "provenance": {
            "source": "scripts/r68_postkill_probe.py (the "
                      "read-only product-stack diagnostic; the "
                      "policy identity line logged in-band)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r68/"
                        "r68_postkill_probe_v161_chipstand.jsonl + "
                        "r68_probe_death.png (the truck a4 "
                        "trajectory is in the v1.6.0/v1.5.0 "
                        "narrative records; the intermediate "
                        "probe artifacts were overwritten in "
                        "place by the fixed-path probe — "
                        "disclosed)",
        },
    })
    ev.append({
        "what":
            "R68 the PRODUCT-PATH FAILURE-MODE MAP (four policy "
            "variants, each probe-pinned; the adapter 0.4.0 adds "
            "the truck dead family {0xA304, 0xA44C, 0xA45C} to "
            "the corpse filter + the dead_truck_x kill "
            "signature; the policy 1.5.0->1.6.2; 9 new offline "
            "tests, the suite 864 green): "
            "(a) v1.5.0 W8/W9 (the kill transition + the hazard "
            "retreat): the product run reproduced the R67 v1.4.2 "
            "trace BYTE-IDENTICAL (1462f/2300/91, the same "
            "trace_sha256) — the chain never fires because the "
            "truck never dies; "
            "(b) v1.6.0 T2' unlimited lobs + T6' the chase: ep1 "
            "1318f/2800 = the score RECORD; the probe: the lobs "
            "LANDED in the band (dx -133.5, px 1071) driving a4 "
            "300->230->110->100->80, then FROZE when the truck "
            "crossed the band edge and the chase walked against "
            "the scroll (px 1071->1105.8 while pressing BACK); "
            "(c) v1.6.1 T6' stand-ground chip-fire: ep1 1218f/"
            "1400 = a REGRESSION — the a4 sat at 300 FROZEN "
            "through five 12f chip windows: THE BULLETS DO NOT "
            "REACH a truck behind the pin (the wave soldiers + "
            "the pin scenery eat the shot); the R38 chip model "
            "requires a CLEAR LINE; "
            "(d) v1.6.2 T6' the chase restored + the R38 gre40 "
            "cadence (TRUCK_GRENADE_CD=40): ep1 1318f/2800 (the "
            "record tied) — the same band window, the same a4 "
            "floor 80: the CONNECT RATE (~1/10, the R38 chopper "
            "evidence) is the named R69 blocker, not the "
            "cadence.  Mission 1 NOT cleared (not claimed).",
        "status": "OBSERVED",
        "provenance": {
            "source": "ps1play/adapters/metal_slug_x/policy.py "
                      "v1.6.2 + adapter.py 0.4.0 + "
                      "scripts/r68_postkill_probe.py + "
                      "scripts/r68_gameplay_record.py",
            "evidence": "data/games/SLUS-01212/truck_evidence/r68/"
                        "r68_product_run.json + product_run/ "
                        "(the v1.6.2 episodes + shots) + "
                        "r68_postkill_probe_v161_chipstand.jsonl",
        },
    })
    c["meta"]["last_updated"] = now
    c["meta"]["last_commit_note"] = (
        "R68: the +500 n>=2 GOAL MET (the verbatim R66 tap replay "
        "on the byte-exact rebuilt frontier; the tap-6 capture "
        "slot16 0x1e38 tail-f1 — the causal chain byte-identical "
        "to R66), the zero-overlap DISCRIMINATOR RESOLVED (19 "
        "offsets, n=2 +500 vs n=7 +1000; the delay law two-class), "
        "the R67 truck-kill claim REFUTED (a4=160 at death), the "
        "product-path failure-mode map (the record 2800; the "
        "connect rate = the R69 blocker).  Mission 1 OPEN.")
    c["next_experiment"] = {
        "id": "R69",
        "budget": "restore-only arms from the r66 frontiers while "
                  "they survive on disk (the R68 rebuild is "
                  "byte-exact and reproducible if lost again); "
                  "product-path boots are the separate gameplay "
                  "track (the R67/R68 precedent)",
        "hypothesis":
            "two leads, both evidence-armed: (1) SOURCE-FIRST — "
            "the 19 zero-overlap offsets (the +500 fingerprint) "
            "xref'd inside the ENEMY.BIN overlay @0x8009C0E8 + "
            "the EXE to find the payment writer (the "
            "0xa0-adjacent accumulator lead; the pay-before-"
            "registration law pins the write order); (2) "
            "PRODUCT — the truck kill needs the CONNECT RATE, "
            "not the cadence: the lob lands at dx -133.5 from a "
            "STATIONARY throw posture (px 1071); the R69 policy "
            "holds that posture and throws on the gre40 cadence "
            "ONLY while |dx| in [125, 140] (the measured connect "
            "window), walking otherwise; the band window is "
            "~280f => up to 7 throws => the kill inside the "
            "window at the measured connect rate",
        "method":
            "product-path: play metal_slug_x with the R69 "
            "connect-window policy (the hold-gate at 125..140 "
            "replaces the in-band lob gate); experiment-track: "
            "the +500 fingerprint xref (offline, zero boots — "
            "the overlay index + the re_index edges) THEN one "
            "restore-only hunt pass if the writer is found "
            "(the R66 gate verbatim, the R68 disclosure "
            "pattern); the zero-overlap test re-runs on any new "
            "capture",
        "m2_gate_note": "unchanged - interactive M2 entry stays "
                        "gated on a clean (deaths=0, no-restart) "
                        "deep resolve posture",
    }
    with open(MSX, "w") as f:
        json.dump(c, f, indent=1, ensure_ascii=False)
    print("capsule updated:", MSX)
    print("events:", len(c["events"]))
    import os
    print("size:", os.path.getsize(MSX), "bytes (the 64 KiB cap)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
