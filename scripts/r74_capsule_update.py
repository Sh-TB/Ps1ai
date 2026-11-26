#!/usr/bin/env python3
"""r74_capsule_update.py — append the R74 events to the MSX capsule,
set next_experiment = R75, and run the final-mile reclaim (the R73/
R72/R71 events verbatim-archived — asserted; the older cores
preserved under what_full_capsule_v3 before the second-pass
compaction — lossless).  The full R74 narratives are appended to
the archive first."""
import json
import os
import sys

REPO = "/home/z/my-project/ps1ai"
CAP = os.path.join(REPO, "data", "knowledge", "msx", "capsule.json")
ARC = os.path.join(REPO, "data", "knowledge", "msx",
                   "event_narratives_archive.json")
BOUND = 65536

RECLAIM_VERBATIM = {   # the archive holds the exact form (asserted)
    71: (
        "R73 THE CALIBRATION TABLE (offline, ZERO boots): every "
        "committed boot throw mined per (stream, k, side).  THE "
        "K-OWNERSHIP LAW: the idle-hold stream connects ONLY k=2 "
        "(4/4 across -1f/+1f), k=0/k=1 NEVER (0/4); the volley "
        "stream connects k=0/k=1 (-1f x2).  THE SIDE LAW DEAD: the "
        "ownership is per-window-per-stream.  THE BLOCKED WINDOW: "
        "the r72b1 k=3 window (fight_f 638-642, 9 grenades) never "
        "threw - held by T3 escort-first on a REAR escort at +37.8 "
        "(a rear escort cannot eat the lob)."),
    72: (
        "R73 PRODUCT: THE REAR-ESCORT EXEMPTION (policy 2.1.0: "
        "during the phase-open frames ONLY an OPPOSITE-side escort "
        "no longer holds the grid throw; same-side + off-window "
        "byte-identical; zero weakened).  BOOT 1 (1/3): the r72b1 "
        "trajectory BYTE-EXACT to the divergence (the k=2 CONNECT "
        "f1657) and THE K=3 THROW FIRED f1790 - the first ever - "
        "land f1820: MISS -> THE OWNED SET IS EXACTLY {k=2}.  "
        "death f1844 score 700 BYTE-IDENTICAL DESPITE the "
        "divergent inputs - the death clock is section-locked."),
    73: (
        "R73 THE DEATH RE-CLASSIFIED (the R72 attrition "
        "SUPERSEDED): php FLAT 198 f1200..f1844 in BOTH boots; ONE "
        "deterministic event at f1844 = freeze+693 (byte-exact; "
        "the death PNG: PRESS START; no table-visible projectile). "
        " The kill math CLOSED OFF on the idle-hold stream (only "
        "k=2; 3 needed) -> R74 THE STREAM HANDOFF."),
    68: (
        "R72 PRODUCT: THE VOLLEY+PHASE HYBRID (policy 2.0.0): "
        "TRUCK_CHIP_FIRE default False (the R71 boot-3 stream "
        "evidence: the idle-hold connects, the chip-fire 0/2 - THE "
        "PHASE LAW IS STREAM-DEPENDENT; the K1 arm stays "
        "patchable) + the phase gate widened to the FULL +-2f BOTH "
        "sides.  BOOT 1 (1/3): the freeze f1151 (the drive-in "
        "0x9C14 f1073 -> 0x9E08 f1149 -> 0x9E88 f1151); the hybrid "
        "threw ON GRID at the PRE-SIDE frames (the lands "
        "freeze+176/340/505) and THE CONNECT LANDED a4 280->180 at "
        "f1657 = freeze+506 EXACT (-1f) - PRE-SIDE VALIDITY "
        "CONFIRMED at k=2; the k=0/k=1 MISSED on a CLEAN corridor; "
        "death f1844; NO kill (a4 170), score 700.  THE CROSS-BOOT "
        "LAW: the connect windows are STREAM-OWNED.  The corridor "
        "CLEAN at ALL FOUR lands - the misses are NOT thefts."),
    65: (
        "R71 THE CHIP-CONNECT KILL SCHEDULE (policy 1.9.0 K1, "
        "adapter 0.5.2; 3 boots, 3/3): K1 = the aimed cooldown "
        "chip-fire (the grenade keeps grid priority).  BOOT 1: 8 "
        "chips 300->220 (THE AIMED CHIP PATH CONFIRMED); the k=0 "
        "WITHHELD by the GHOST BLOCKER (slot23 0x6730 dead-walk); "
        "the k=1 STOLEN by the INVISIBLE THIEF STACK (x 1062.3); "
        "death f1298/2400 = THE RECORD.  BOOT 2 (the a4-aware "
        "liveness filter): the k=0 FIRED and MISSED; 13 chips "
        "300->170.  BOOT 3 (TRUCK_CHIP_FIRE=False): the connect "
        "LANDED a4 280->180 at f1659 = freeze+506+-2f ON GRID "
        "(k=2); k=0/k=1 MISSED - THE PHASE LAW IS STREAM-"
        "DEPENDENT.  NO kill - 1 connect + 5 chips, a4 160; the "
        "connect is the bottleneck."),
    5: (
        "The '+0x8E = entity HP' label CONTRADICTED for world "
        "entities, UNRESOLVED for slot 0: (a) the parked truck "
        "+0x8E stayed 254 under standing fire while +0xA4 fell "
        "300->0 (the '254->207' was the truck MOVING); (b) the "
        "chopper +0x8E decayed 148->2 with NO fire (the camera "
        "advance, 3/3); (c) the writer 0x80064674 adds "
        "camera-scroll deltas to +0x8C/+0x90 (+0x8E = the screen-x "
        "integer half).  RULE: +0x8E EXCLUDED from success "
        "oracles; armored HP evidence = +0xA4."),
}

RECLAIM2 = {   # the second-pass cores (the current texts -> v3)
    61: (
        "R69 the +500 FINGERPRINT XREF (offline): 0x800EE318 = "
        "EXACTLY 9 direct xrefs (the EXE HUD/credit cluster "
        "0x800472c0..0x80052820); the amounts 500/1000 in NO "
        "immediate and NO EXE table (BOTH FALSIFIED); the "
        "kill-credit u16 TABLES in the overlay head (0x8009C134 "
        "n=43, 0x8009C48C n=44, 0x8009C91C n=23; 200..1100); the "
        "overlay TAIL (0x800AB230..): 207 accesses (72 stores) + "
        "the damage dispatch enemy_800A41D8 -> 0x800ae794/"
        "0x800ae7cc.  VERDICT: the writer NARROWED (the exact "
        "store = a RUNTIME fact).  The SEVENTH rollback."),
    63: (
        "R70 THE PHASE LAW (policy 1.7.1->1.8.5, adapter 0.5.1; 5 "
        "boots): the cycle 164f PHASE-LOCKED TO THE FREEZE (f811; "
        "the connects freeze+178+164k = f989/f1153; the scroll/"
        "knockback on the SAME clock); every connect at dx -133.5 "
        "EXACTLY, -130.5 MISSED (the band [131.5,135.0]); the "
        "CORRIDOR LAW REFUTED (the f989 lob STOLEN -> the C2 "
        "guard); the PACKING LAW (five chasers dropped the truck "
        "row); C5 the escort classes (1,2,3,5,6); C4 the width "
        "probe (a4 300->290 = the CHIP).  NO kill - best a4 230, "
        "death f1324, score 2100."),
    67: (
        "R71 THE WATCHPOINT PASS (restore-only; the cap 2->4, two "
        "DISCLOSED amendments): the frontier rebuild BYTE-EXACT "
        "AGAIN (px 1254.8, 8-for-8); the verbatim R66 pass-B tap "
        "replay: THE +500 CAPTURED AT THE WATCHPOINT - tap 6 "
        "(slot16, st_pre 0x1e38, 7702->8202) at flight TAIL f1 - "
        "the pay-frame law 3/3.  The +1000 cluster COMPLETE (1034 "
        "B, 200 regions) incl. 0xEE318-0xEE31A; the +500 "
        "footprint: the STACK band 0x1FFD00-0x1FFF00 + the ENTITY "
        "rows 0xCA6xx-0xCBDxx + the HUD 0xEE3xx-0xEF4xx.  THE PC "
        "NOT readable on beetle -> the PCSX-Redux oracle."),
    43: (
        "R48 CORRECTED VERDICT - TWO PAY CLASSES, FRAME-EXACT: "
        "(1) DEATH-INITIATION-LOCKED n=3 - the flat +100 lands "
        "EXACTLY on the 0x515c entry frame, corpse 0x4BE4 follows "
        "1-4f; (2) a SURVIVING-CONNECT payment n=1 - the +500 at "
        "tap-1 f_rel 2 with slot-20's 0x42bc hit-reaction the "
        "ONLY event (the slot SURVIVES; death 23f later) - the "
        "R47 ZERO-surviving-hit FALSIFIED.  Payments land at the "
        "connect/kill-registration frame, the corpse lags 1-14f; "
        "the ZERO-INPUT control: 4 natural deaths paid 0."),
    60: (
        "R68 PRODUCT (adapter 0.4.0: the dead family "
        "{0xA304,0xA44C,0xA45C}; policy 1.6.2): 'TRUCK KILLED "
        "2300' REFUTED (a4=160 f1160..f1462).  v1.5.0 = the R67 "
        "trace BYTE-IDENTICAL; v1.6.0 the chase = 1318f/2800 THE "
        "RECORD (the lobs LAND at dx -133.5: a4 300->80); v1.6.1 "
        "the chip-stand REGRESSION (the bullets DO NOT REACH a "
        "truck behind the pin); v1.6.2 tied - the CONNECT RATE is "
        "the R69 blocker."),
    30: (
        "R43 boots 6+7 (the cross-process savestate restore): "
        "r43_postkill saved at c172 (px 992.0, flags 0x4B = the "
        "R41 RELEASE_SIGNATURE) - but POST-RESTART + "
        "CHECKPOINT-RESPAWN (a silent timer-expiry restart px "
        "1150->25).  900 latch chunks, 8 deaths (continue-"
        "rescued), score 4501->13704, held at the 1272 clamp; "
        "mission_end NEVER latched.  THE INTERACTIVE M2 entry is "
        "NOT claimable from a post-restart posture."),
    58: (
        "R67 the PRODUCT-PATH TRUCK CAMPAIGN (policy 1.1.0->1.4.2, "
        "40 offline tests): T1 the truck identity = the 0x9E88 "
        "state word ((6,h=64) = a FALSE-POSITIVE TRAP); the REAR "
        "fight (BACK = the legal LEFT; the wave AND the truck "
        "BEHIND - three identical forward-only deaths); the "
        "CADENCE law (the 12f cadence starved the wave; the 13f "
        "rhythm reproduced the R66 record BYTE-EXACT).  ep1 2300 "
        "= the record then (REFUTED by R68)."),
    49: (
        "R51 CORRECTED VERDICT (offline): (1) PIERCING n=2 - the "
        "PIERCE taps (aimed 0xab94) paid +100, the transparent "
        "target NEVER reacted; the +100 co-lands on slot18's "
        "0x515c registration BEHIND it (x 1357.2, holder_invul="
        "30); (2) the controls NEVER pay; (3) two MORE +1000 "
        "connects (0x42bc AND 0x3f48, slot20) - +500 x3 vs +1000 "
        "x5 across R48-R51; (4) the wound-word hunt NEGATIVE - "
        "the R52 lever; (5) 0xae7c exonerated twice.  Ledger "
        "+2200."),
}

R74_EVENTS = [
    {
        "round": "R74",
        "status": "OBSERVED",
        "what": (
            "R74 PRODUCT: THE STREAM HANDOFF (policy 2.2.0: the "
            "volley head = the VERBATIM r69b schedule fight_f "
            "64/106/147/188/229/270/311; the clock handoff 350 -> "
            "the idle-hold tail; no lead, no probe in the head).  "
            "BOOT 1 (cap 3, 1/3): the head threw 6/7 (the 106 "
            "frame absorbed by the cooldown, the 147 slot by the "
            "gate's early throw at 146) and THE FIRST HEAD CONNECT "
            "LANDED a4 300->200 at f1411 = freeze+259 (the 229 "
            "throw); the stray-feed chips x7 (200->130, ~26f) - "
            "THE A4 FLOOR 130 = the record; death f1884 = "
            "freeze+733 (NOT the f1844 clock: the truck_approach "
            "walk moved the player to px 1106 - the death is "
            "posture-coupled); 6 throws / 1 connect / 7 chips."),
        "provenance": {
            "source": "scripts/r74_handoff_probe.py (product boot)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r74/"
                        "r74_calibrated_probe_boot1.jsonl",
            "boots": 1,
        },
    },
    {
        "round": "R74",
        "status": "VERIFIED",
        "what": (
            "R74 THE HEAD-PHASE LAW: the connect phase is "
            "STREAM-DETERMINED per head variant - the r74b1 head's "
            "connect grid = freeze+259 (+81f, ~the half-period, vs "
            "the r69b/178-grid): the 229 throw landed ON it (+0f, "
            "CONNECTED), the 270/311 throws missed (+41f/+82f off "
            "- the predicted off-window) and the tail's 178-grid "
            "k=2 window is MOOT on this stream.  The +-1-throw "
            "stream delta (the 106/147 absorptions) shifted the "
            "phase +81f - deterministic and reproducible (the "
            "pattern 64/146/188/229/270/311)."),
        "provenance": {
            "source": "scripts/r74_handoff_probe.py + the offline "
                      "grid check",
            "evidence": "data/games/SLUS-01212/truck_evidence/r74/"
                        "r74_calibrated_probe_boot1.jsonl",
            "boots": 1,
        },
    },
    {
        "round": "R74",
        "status": "OBSERVED",
        "what": (
            "R74 THE CORRIDOR-FEED SHIELD: the tail's k=2 window "
            "(the gate opens fight_f 474) never threw - the "
            "corridor BLOCKED f1600+ by the walkers (-10.2 h~210, "
            "-67.9, -101.9); the escort-first cadence every 13f at "
            "the -8.7 walker, but the bullets PIERCE it (the R51 "
            "transparent law) and STRAY-CHIP the truck (the 7 "
            "chips) - the walkers never die to aimed fire, the lob "
            "withheld by C2 (correct).  R75 NAMED: THE HEAD-PHASE "
            "EXTENDED SCHEDULE - the handoff -> fight_f 620; the "
            "schedule + {393, 557} (the head's OWN grid: the lands "
            "freeze+423/+587): 3 head connects = a4 0 INSIDE the "
            "death clock; arm 2 the corridor hygiene; arm 3 the "
            "oracle (unchanged)."),
        "provenance": {
            "source": "scripts/r74_handoff_probe.py (the rule "
                      "timeline + the ents analysis)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r74/"
                        "r74_calibrated_probe_boot1.jsonl",
            "boots": 1,
        },
    },
]

R75_NEXT = {
    "id": "R75",
    "budget": "the product track: ONE extended-schedule boot (cap 3 "
              "disclosed pre-run; boots 2-3 the correction cycle); "
              "the experiment track restore-only (r66 frontiers)",
    "hypothesis": "THE HEAD-PHASE EXTENDED SCHEDULE: the r74b1 head "
                  "stream (64/146/188/229/270/311 + the absorptions) "
                  "owns the connect grid freeze+259+164k - extending "
                  "the schedule by the head's OWN grid {393, 557} "
                  "(the lands freeze+423/+587; the handoff -> 620) "
                  "delivers the 2nd and 3rd connects: a4 200->100->0 "
                  "= THE KILL INSIDE the death clock (the r74b1 "
                  "death freeze+733).  The extension throws are ON "
                  "the head's grid - not perturbations.",
    "method": "policy 2.3.0 = v2.2.0 with TRUCK_HANDOFF_FIGHT_F "
              "350->620 and the schedule + {393, 557}; the corridor "
              "check at the extended windows (the r74b1 feed "
              "blocked ~fight_f 449); arm 2 = the corridor hygiene "
              "(the fallback: the 2-connect floor + the chips "
              "math); arm 3 = the PCSX-Redux writer-PC oracle "
              "(unchanged)",
    "m2_gate_note": "unchanged - M2 entry gated on a clean "
                    "(deaths=0, no-restart) resolve posture",
}


def main():
    cap = json.load(open(CAP))
    arc = json.load(open(ARC))
    evs = cap["events"]
    # the entries whose archive copy is an OLDER/longer form: the
    # current capsule text is preserved under what_full_capsule_v3
    # before compacting (lossless)
    PRESERVE = (68, 65, 5) + tuple(RECLAIM2)
    # 1. the archive-asserted reclaim + the preserved reclaim
    for idx, core in list(RECLAIM_VERBATIM.items()) + \
            list(RECLAIM2.items()):
        ent = arc["events"].setdefault(str(idx), {})
        full = ent.get("what_full")
        if idx in PRESERVE:
            ent.setdefault("round", evs[idx].get("round"))
            ent.setdefault("status", evs[idx].get("status"))
            ent.setdefault("what_full", evs[idx]["what"])
            if ent["what_full"] != evs[idx]["what"]:
                ent["what_full_capsule_v3"] = evs[idx]["what"]
        else:
            assert full == evs[idx]["what"], \
                f"archive mismatch at idx{idx}; refuse to compact"
    # 2. the reclaims in
    for idx, core in list(RECLAIM_VERBATIM.items()) + \
            list(RECLAIM2.items()):
        evs[idx]["what"] = core
    # 3. the R74 full narratives -> the archive (74,75,76)
    for i, ev in enumerate(R74_EVENTS, start=74):
        arc["events"][str(i)] = {"round": ev["round"],
                                 "status": ev["status"],
                                 "what_full": ev["what"]}
    # 4. the compact R74 events -> the capsule
    evs.extend(R74_EVENTS)
    cap["next_experiment"] = R75_NEXT
    cap["meta"]["last_updated"] = "2026-11-26T00:00:00Z"
    cap["meta"]["last_commit_note"] = (
        "R74: the stream handoff executed (boot 1: the FIRST head "
        "connect - a4 300->200 at freeze+259; the head-phase law "
        "(+81f); the corridor-feed shield; R75 = the extended "
        "schedule {393,557})")
    # 5. the canonical compact write + the bound check
    blob = json.dumps(cap, indent=None, ensure_ascii=False,
                      separators=(",", ":"))
    size = len(blob.encode("utf-8"))
    print(f"after: {len(evs)} events, {size} B (bound {BOUND})")
    assert size < BOUND, f"capsule over the bound: {size}"
    with open(CAP, "w") as f:
        f.write(blob)
    with open(ARC, "w") as f:
        json.dump(arc, f, indent=1)
    # 6. the round-trip check
    cap2 = json.load(open(CAP))
    assert len(cap2["events"]) == 77
    assert cap2["next_experiment"]["id"] == "R75"
    arc2 = json.load(open(ARC))
    assert arc2["events"]["76"]["status"] == "OBSERVED"
    print("round-trip OK; archive events:", len(arc2["events"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
