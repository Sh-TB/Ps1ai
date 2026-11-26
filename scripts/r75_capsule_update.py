#!/usr/bin/env python3
"""r75_capsule_update.py — append the R75 events to the MSX capsule,
set next_experiment = R76, and run the final-mile reclaim (the R74
events verbatim-archived — asserted; the older cores preserved
under what_full_capsule_v3 — lossless).  The full R75 narratives
are appended to the archive first."""
import json
import os
import sys

REPO = "/home/z/my-project/ps1ai"
CAP = os.path.join(REPO, "data", "knowledge", "msx", "capsule.json")
ARC = os.path.join(REPO, "data", "knowledge", "msx",
                   "event_narratives_archive.json")
BOUND = 65536

# the archive holds the exact forms (asserted — the r74 round wrote
# them verbatim)
RECLAIM_VERBATIM = {
    74: (
        "R74 PRODUCT: THE STREAM HANDOFF (policy 2.2.0: the volley "
        "head = the VERBATIM r69b schedule; the clock handoff 350 "
        "-> the idle-hold tail; no lead, no probe).  BOOT 1 (cap 3, "
        "1/3): the head threw 6/7 and THE FIRST HEAD CONNECT "
        "LANDED a4 300->200 at f1411 = freeze+259 (the 229 throw); "
        "the stray-feed chips x7 (200->130) - THE A4 FLOOR 130 = "
        "the record; death f1884 = freeze+733 (the truck_approach "
        "walk -> px 1106; the death is POSTURE-COUPLED); 6 throws "
        "/ 1 connect / 7 chips."),
    75: (
        "R74 THE HEAD-PHASE LAW: the connect phase is "
        "STREAM-DETERMINED per head variant - the r74b1 head's "
        "grid = freeze+259 (+81f ~ the half-period): the 229 throw "
        "ON it (+0f, CONNECTED), the 270/311 missed (+41f/+82f off "
        "- the predicted off-window); the tail's 178-grid k=2 MOOT "
        "on this stream.  The +-1-throw delta shifted the phase "
        "+81f - deterministic (the pattern 64/146/188/229/270/"
        "311)."),
    76: (
        "R74 THE CORRIDOR-FEED SHIELD: the tail's k=2 window never "
        "threw - the corridor BLOCKED f1600+ by the walkers; the "
        "escort-first every 13f; the bullets PIERCE the transparent "
        "walker and STRAY-CHIP the truck; the lob withheld by C2 "
        "(correct).  R75 = the extended schedule {393, 557}."),
}
# the older cores: the current text -> the archive (v3), then the
# second-pass core
RECLAIM_PRESERVE = {
    68: (
        "R72 PRODUCT: THE VOLLEY+PHASE HYBRID (policy 2.0.0): "
        "TRUCK_CHIP_FIRE default False (the idle-hold connects "
        "1/3, the chip-fire 0/2 - THE PHASE LAW IS STREAM-"
        "DEPENDENT; the K1 arm patchable) + the gate widened to "
        "the FULL +-2f BOTH sides.  BOOT 1 (1/3): the freeze "
        "f1151; the hybrid threw ON GRID at the PRE-SIDE frames "
        "(the lands freeze+176/340/505) and THE CONNECT LANDED a4 "
        "280->180 at f1657 = freeze+506 EXACT (-1f) - PRE-SIDE "
        "VALIDITY CONFIRMED at k=2; the k=0/k=1 MISSED on a CLEAN "
        "corridor; death f1844; NO kill (a4 170), score 700.  THE "
        "CROSS-BOOT LAW: the connect windows are STREAM-OWNED; "
        "the corridor CLEAN at ALL FOUR lands."),
    70: (
        "R72 THE PAYMENT-CLUSTER XREF (offline, ZERO boots): the "
        "score-word store 0x8005c508 sw $a1,-0x1ce8($a2) -> "
        "0x800EE318 in the accumulator 0x8005c4b4 (frame 40 B, "
        "HANDLE-mediated; the P1/P2 bits; the cap 0x5f5e0ff; the "
        "%100 twin 0x51eb851f).  The R69 falsification EXPLAINED: "
        "the delta via the format->parse chain 0x8007e8b4 -> "
        "0x8007e7d4 (the amounts 500/1000 arrive FORMATTED from "
        "the overlay kill-credit tables).  Exactly 3 score-word "
        "stores in the EXE, 0 in the overlay, 178 HUD-band store "
        "sites.  NO direct jal on the accumulator (the runtime PC "
        "= the PCSX-Redux oracle)."),
    65: (
        "R71 THE CHIP-CONNECT KILL SCHEDULE (policy 1.9.0 K1, "
        "adapter 0.5.2; 3 boots, 3/3): BOOT 1: 8 chips 300->220 "
        "(THE AIMED CHIP PATH CONFIRMED); the k=0 WITHHELD by the "
        "GHOST BLOCKER (slot23 0x6730 dead-walk); the k=1 STOLEN "
        "by the INVISIBLE THIEF STACK (x 1062.3); death f1298/2400 "
        "= THE RECORD.  BOOT 2 (the a4-aware liveness filter): the "
        "k=0 FIRED and MISSED; 13 chips 300->170.  BOOT 3 "
        "(TRUCK_CHIP_FIRE=False): the connect LANDED a4 280->180 "
        "at f1659 = freeze+506+-2f ON GRID (k=2); k=0/k=1 MISSED - "
        "THE PHASE LAW IS STREAM-DEPENDENT.  NO kill - 1 connect + "
        "5 chips, a4 160."),
    39: (
        "R46 CORRECTED VERDICT (offline): the slot-20 one-hit "
        "SIGNATURE - the R45 'one-bullet kill' was a TWO-EVENT "
        "chain: the Y tap CONNECTED (0x42bc hit-reaction at lag 0, "
        "the victim SURVIVED) and a wandering ZONE bullet killed "
        "it ~1.2s later (0x515c + the corpse); the +500 "
        "co-landed with the CONNECT, the +100 with the "
        "registration.  The kill-class key = REGISTRATION-locked "
        "(+100 on 0x515c/0x5b0c, n=3); the connect-class key "
        "stands (+500 on 0x42bc, n=2).  The R45 kill-without-"
        "payment rows = CORPSE-BLIND scan artifacts."),
    45: (
        "R49 CORRECTED VERDICT (the GLOBAL-frame per-slot "
        "matcher): (1) surviving-connect +500 REPLICATED (slot20 "
        "0x42bc at the pay frame, ZERO registrations in [-2,+6]; "
        "n=2); (2) +100 kill payments n=4, all lag-0 on 0x515c "
        "registrations but NONE is the aimed target - all CYCLING "
        "ZONE ENTITIES = payment REFINED to PLAYER-BULLET-VICTIM-"
        "LOCKED; the 11 zone/wound registrations paid 0; (3) "
        "UNRESOLVED residual n=1: the same connect context paid "
        "+1000 once.  Strong class-keyed form FALSIFIED; weak "
        "form stands.  Ledger +1900/11 taps."),
}

R75_EVENTS = [
    {
        "round": "R75",
        "status": "OBSERVED",
        "what": (
            "R75 PRODUCT: THE HEAD-PHASE EXTENDED SCHEDULE (policy "
            "2.3.0: the schedule + {393, 557} — the lands "
            "freeze+423/+587; the handoff 350->620; 8 new tests, 7 "
            "suites re-anchored, zero weakened).  BOOT 1 (cap 3, "
            "1/3): the boot REPRODUCED r74b1 BYTE-EXACT (the "
            "connect a4 300->200 at f1411 = freeze+259; the chips "
            "x7; the death f1884 px 1106 score 1300; 6 throws / 1 "
            "connect) — THE EXTENSION THROWS NEVER FIRED: the "
            "corridor BARRICADED at f1515 = fight_f 364 (the "
            "chaser marchers -74.5/-101.9 ON the truck line), 71f "
            "before the first extension window; the 557 window "
            "blocked by the point-blank -8.7 stack.  The head "
            "replay byte-exact (312/312)."),
        "provenance": {
            "source": "scripts/r75_extsched_probe.py (product boot)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r75/"
                        "r75_calibrated_probe_boot1.jsonl",
            "boots": 1,
        },
    },
    {
        "round": "R75",
        "status": "OBSERVED",
        "what": (
            "R75 THE BARRICADE TIMELINE: the chaser marchers (sc=6, "
            "h 190-226 declining ~1/30f = the march timers) spawn "
            "into the truck line ~f1450-1515 and NEVER die to the "
            "aimed fire (the transparent march + the pierce-to-"
            "truck = the chips); the T3 targets only the CLEAR-LINE "
            "walkers and the fire pierces them too; the C2 guard "
            "correctly withholds the lobs.  R76 NAMED: THE "
            "FEED-CLEARING LOB — the player repositions RIGHT "
            "(+62px, px ~1133) so the lob lands ON the marcher "
            "stack (~999.5; the lob-feed interaction PROVEN — the "
            "R70 'the f989 lob STOLEN'); the corridor opens -> the "
            "3-connect kill resumes; arm 2 the marcher-vulnerability "
            "watchpoint; arm 3 the oracle (unchanged)."),
        "provenance": {
            "source": "scripts/r75_extsched_probe.py (the ents "
                      "timeline + the corridor map)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r75/"
                        "r75_calibrated_probe_boot1.jsonl",
            "boots": 1,
        },
    },
]

R76_NEXT = {
    "id": "R76",
    "budget": "ONE feed-clearing boot (cap 3 disclosed pre-run; "
              "boots 2-3 the correction cycle); the experiment "
              "track restore-only",
    "hypothesis": "THE FEED-CLEARING LOB: the barricade (the "
                  "marchers ON the truck line from fight_f 364) "
                  "blocks every grid throw — but the lob lands at "
                  "the player px - 133.5: repositioning RIGHT to "
                  "px ~1133 puts the lob ON the marcher stack "
                  "(~999.5; the lob-feed interaction PROVEN — the "
                  "R70 'the f989 lob STOLEN').  If the lob clears "
                  "the marchers, the corridor opens for the "
                  "freeze+587 window -> a4 100 -> 0 = THE KILL "
                  "INSIDE the death clock (the r74b1 death "
                  "freeze+733).",
    "method": "policy 2.4.0 THE FEED-CLEARING LOB (a barricade-"
              "aware rule: the corridor occupied by the marchers + "
              "a pending extension window -> walk RIGHT to align "
              "the lob with the marcher centroid, lob, return to "
              "the record posture); arm 2 = the marcher-"
              "vulnerability watchpoint (the transparent-march end "
              "frame — the restore-only track); arm 3 = the "
              "PCSX-Redux writer-PC oracle (unchanged)",
    "m2_gate_note": "unchanged - M2 entry gated on a clean "
                    "(deaths=0, no-restart) resolve posture",
}


def main():
    cap = json.load(open(CAP))
    arc = json.load(open(ARC))
    evs = cap["events"]
    # 1. the archive-asserted reclaim + the preserved reclaim
    for idx, core in RECLAIM_VERBATIM.items():
        full = arc["events"].get(str(idx), {}).get("what_full")
        assert full == evs[idx]["what"], \
            f"archive mismatch at idx{idx}; refuse to compact"
    for idx, core in RECLAIM_PRESERVE.items():
        ent = arc["events"].setdefault(str(idx), {})
        ent.setdefault("round", evs[idx].get("round"))
        ent.setdefault("status", evs[idx].get("status"))
        ent.setdefault("what_full", evs[idx]["what"])
        if ent["what_full"] != evs[idx]["what"]:
            ent["what_full_capsule_v3"] = evs[idx]["what"]
    for idx, core in list(RECLAIM_VERBATIM.items()) + \
            list(RECLAIM_PRESERVE.items()):
        evs[idx]["what"] = core
    # 2. the R75 full narratives -> the archive (77, 78)
    for i, ev in enumerate(R75_EVENTS, start=77):
        arc["events"][str(i)] = {"round": ev["round"],
                                 "status": ev["status"],
                                 "what_full": ev["what"]}
    # 3. the compact R75 events -> the capsule
    evs.extend(R75_EVENTS)
    cap["next_experiment"] = R76_NEXT
    cap["meta"]["last_updated"] = "2026-11-26T00:00:00Z"
    cap["meta"]["last_commit_note"] = (
        "R75: the extended schedule boot — the head stream "
        "reproduced byte-exact; the extension windows barricaded "
        "by the marchers; R76 = the feed-clearing lob")
    # 4. the canonical compact write + the bound check
    blob = json.dumps(cap, indent=None, ensure_ascii=False,
                      separators=(",", ":"))
    size = len(blob.encode("utf-8"))
    print(f"after: {len(evs)} events, {size} B (bound {BOUND})")
    assert size < BOUND, f"capsule over the bound: {size}"
    with open(CAP, "w") as f:
        f.write(blob)
    with open(ARC, "w") as f:
        json.dump(arc, f, indent=1)
    # 5. the round-trip check
    cap2 = json.load(open(CAP))
    assert len(cap2["events"]) == 79
    assert cap2["next_experiment"]["id"] == "R76"
    arc2 = json.load(open(ARC))
    assert arc2["events"]["78"]["status"] == "OBSERVED"
    assert "what_full_capsule_v3" in arc2["events"]["68"]
    print("round-trip OK; archive events:", len(arc2["events"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
