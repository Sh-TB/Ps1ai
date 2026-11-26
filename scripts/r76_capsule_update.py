#!/usr/bin/env python3
"""r76_capsule_update.py — append the R76 events to the MSX capsule,
set next_experiment = R77, and run the final-mile reclaim (the R75
events verbatim-archived — asserted; the older cores preserved
under what_full_capsule_v3 — lossless)."""
import json
import os
import sys

REPO = "/home/z/my-project/ps1ai"
CAP = os.path.join(REPO, "data", "knowledge", "msx", "capsule.json")
ARC = os.path.join(REPO, "data", "knowledge", "msx",
                   "event_narratives_archive.json")
BOUND = 65536

RECLAIM_VERBATIM = {
    77: (
        "R75 PRODUCT: THE HEAD-PHASE EXTENDED SCHEDULE (policy "
        "2.3.0: the schedule + {393, 557}; the handoff 620).  "
        "BOOT 1 (1/3): the r74b1 BYTE-EXACT reproduction (the "
        "connect a4 300->200 at freeze+259; the death f1884) - "
        "THE EXTENSION THROWS NEVER FIRED: the corridor "
        "BARRICADED at fight_f 364 (the marchers ON the truck "
        "line).  The head replay byte-exact (312/312)."),
    78: (
        "R75 THE BARRICADE TIMELINE: the chaser marchers (sc=6, "
        "the march timers) spawn into the truck line ~f1450-1515 "
        "and NEVER die to the aimed fire (the transparent march "
        "+ the pierce-to-truck); the C2 guard correctly "
        "withholds the lobs.  R76 = the savestate battery."),
}
RECLAIM_PRESERVE = {
    68: (
        "R72 PRODUCT: THE VOLLEY+PHASE HYBRID (policy 2.0.0): "
        "TRUCK_CHIP_FIRE False (the idle-hold connects 1/3, the "
        "chip-fire 0/2 - the phase law IS stream-dependent) + the "
        "gate widened to the FULL +-2f BOTH sides.  BOOT 1: the "
        "freeze f1151; the PRE-SIDE lands (freeze+176/340/505) "
        "and THE CONNECT LANDED a4 280->180 at f1657 = freeze+506 "
        "(-1f) - the k=2 PRE-SIDE VALIDITY; the k=0/k=1 MISSED on "
        "a CLEAN corridor; death f1844; a4 170, score 700.  THE "
        "CROSS-BOOT LAW: the connect windows are STREAM-OWNED."),
    70: (
        "R72 THE PAYMENT-CLUSTER XREF (offline): the score-word "
        "store 0x8005c508 -> 0x800EE318 in the accumulator "
        "0x8005c4b4 (the HANDLE-mediated base; the P1/P2 bits; "
        "the cap 0x5f5e0ff).  The R69 falsification EXPLAINED: "
        "the delta via the format->parse chain (the amounts "
        "arrive FORMATTED from the overlay kill-credit tables).  "
        "Exactly 3 score-word stores in the EXE, 0 in the "
        "overlay.  NO direct jal on the accumulator (the runtime "
        "PC = the PCSX-Redux oracle)."),
    63: (
        "R70 THE PHASE LAW (policy 1.8.5, adapter 0.5.1; 5 "
        "boots): the cycle 164f PHASE-LOCKED TO THE FREEZE "
        "(f811; the connects freeze+178+164k = f989/f1153); "
        "every connect at dx -133.5 EXACTLY, -130.5 MISSED (the "
        "band [131.5,135.0]); the CORRIDOR LAW REFUTED (the f989 "
        "lob STOLEN -> the C2 guard); the PACKING LAW; C5 the "
        "escort classes (1,2,3,5,6); C4 the width probe (the "
        "CHIP measured).  NO kill - best a4 230, death f1324, "
        "score 2100."),
    67: (
        "R71 THE WATCHPOINT PASS (restore-only; the cap 2->4 "
        "disclosed): the frontier rebuild BYTE-EXACT (px 1254.8, "
        "8-for-8); the verbatim R66 pass-B tap replay: THE +500 "
        "CAPTURED AT THE WATCHPOINT - tap 6 (slot16, st_pre "
        "0x1e38, 7702->8202) at flight TAIL f1 - the pay-frame "
        "law 3/3.  The +1000 cluster COMPLETE (1034 B, 200 "
        "regions) incl. 0xEE318-0xEE31A.  THE PC NOT readable on "
        "beetle -> the PCSX-Redux oracle.  The replay "
        "BYTE-IDENTICAL x3."),
    74: (
        "R74 PRODUCT: THE STREAM HANDOFF (policy 2.2.0: the "
        "volley head = the VERBATIM r69b schedule; the handoff "
        "350; no lead, no probe).  BOOT 1 (1/3): 6/7 throws and "
        "THE FIRST HEAD CONNECT a4 300->200 at f1411 = "
        "freeze+259 (the 229 throw); the stray-feed chips x7 "
        "(200->130) - THE A4 FLOOR 130 = the record; death "
        "f1884 = freeze+733 (the truck_approach walk -> px "
        "1106; the death is POSTURE-COUPLED)."),
    30: (
        "R43 boots 6+7 (the savestate restore): r43_postkill at "
        "c172 (px 992.0, flags 0x4B) - but POST-RESTART + "
        "CHECKPOINT-RESPAWN (a timer-expiry restart px 1150->25).  "
        "900 latch chunks, 8 deaths (continue-rescued), score "
        "4501->13704, held at the 1272 clamp; mission_end NEVER "
        "latched.  THE INTERACTIVE M2 entry NOT claimable from a "
        "post-restart posture."),
    61: (
        "R69 the +500 FINGERPRINT XREF (offline): 0x800EE318 = 9 "
        "direct xrefs (the HUD/credit cluster 0x800472c0.."
        "0x80052820); 500/1000 in NO immediate and NO EXE table "
        "(BOTH FALSIFIED); the kill-credit u16 TABLES in the "
        "overlay head (0x8009C134 n=43, 0x8009C48C n=44, "
        "0x8009C91C n=23); the overlay TAIL (0x800AB230..): 207 "
        "accesses (72 stores) + the damage dispatch enemy_800A41D8 "
        "-> 0x800ae794/0x800ae7cc.  VERDICT: the writer NARROWED "
        "(the exact store = a RUNTIME fact)."),
    43: (
        "R48 CORRECTED VERDICT - TWO PAY CLASSES, FRAME-EXACT: "
        "(1) DEATH-INITIATION-LOCKED n=3 - the +100 lands EXACTLY "
        "on the 0x515c entry frame, corpse 0x4BE4 follows 1-4f; "
        "(2) SURVIVING-CONNECT n=1 - the +500 at tap-1 f_rel 2, "
        "slot-20's 0x42bc hit-reaction the ONLY event (the slot "
        "SURVIVES).  Payments land at the connect/kill-registration "
        "frame; the ZERO-INPUT control: 4 natural deaths paid 0."),
    49: (
        "R51 CORRECTED VERDICT: (1) PIERCING n=2 - the PIERCE taps "
        "(aimed 0xab94) paid +100, the transparent target NEVER "
        "reacted; the +100 co-lands on slot18's 0x515c BEHIND it "
        "(x 1357.2, holder_invul=30); (2) the controls NEVER pay; "
        "(3) two MORE +1000 connects (-100 x2: 0x42bc/0x3f48, "
        "slot20) - +500 x3 vs +1000 x5 R48-R51; (4) the wound-word "
        "hunt NEGATIVE - the R52 lever; (5) 0xae7c exonerated "
        "twice.  Ledger +2200."),
    58: (
        "R67 the PRODUCT-PATH TRUCK CAMPAIGN (policy 1.1.0->1.4.2, "
        "40 tests): T1 the truck identity = the 0x9E88 word ((6,"
        "h=64) = a FALSE-POSITIVE TRAP); the REAR fight (BACK = "
        "the legal LEFT); the CADENCE law (the 12f cadence "
        "starved the wave; the 13f rhythm reproduced the R66 "
        "record BYTE-EXACT).  ep1 2300 = the record then (REFUTED "
        "by R68)."),
    60: (
        "R68 PRODUCT (adapter 0.4.0: the dead family "
        "{0xA304,0xA44C,0xA45C}; policy 1.6.2): 'TRUCK KILLED "
        "2300' REFUTED (a4=160 f1160..f1462).  v1.6.0 the chase = "
        "1318f/2800 THE RECORD (the lobs LAND at dx -133.5: a4 "
        "300->80); v1.6.1 the chip-stand REGRESSION (the bullets "
        "DO NOT REACH a truck behind the pin); v1.6.2 tied - the "
        "CONNECT RATE is the R69 blocker."),
    65: (
        "R71 THE CHIP-CONNECT KILL SCHEDULE (policy 1.9.0 K1, "
        "adapter 0.5.2; 3 boots): BOOT 1: 8 chips 300->220; the "
        "k=0 WITHHELD by the GHOST BLOCKER (slot23 0x6730); the "
        "k=1 STOLEN by the THIEF STACK (x 1062.3); death "
        "f1298/2400 = THE RECORD.  BOOT 2 (the a4-aware liveness "
        "filter): the k=0 FIRED and MISSED; 13 chips 300->170.  "
        "BOOT 3 (TRUCK_CHIP_FIRE=False): the connect LANDED a4 "
        "280->180 at f1659 = freeze+506 ON GRID (k=2) - THE PHASE "
        "LAW IS STREAM-DEPENDENT.  NO kill - 1 connect + 5 chips, "
        "a4 160."),
    71: (
        "R73 THE CALIBRATION TABLE (offline, ZERO boots): every "
        "committed boot throw mined per (stream, k, side).  THE "
        "K-OWNERSHIP LAW: the idle-hold stream connects ONLY k=2 "
        "(4/4), k=0/k=1 NEVER (0/4); the volley stream connects "
        "k=0/k=1 (-1f x2).  THE SIDE LAW DEAD: the ownership is "
        "per-window-per-stream.  THE BLOCKED WINDOW: the r72b1 "
        "k=3 window held by T3 escort-first on a REAR escort."),
    72: (
        "R73 PRODUCT: THE REAR-ESCORT EXEMPTION (policy 2.1.0: "
        "during the phase-open frames ONLY an OPPOSITE-side escort "
        "no longer holds the grid throw).  BOOT 1 (1/3): the "
        "r72b1 trajectory BYTE-EXACT to the divergence (the k=2 "
        "CONNECT f1657) and THE K=3 THROW FIRED f1790 - the first "
        "ever - land f1820: MISS -> THE OWNED SET IS EXACTLY "
        "{k=2}.  death f1844 score 700 BYTE-IDENTICAL DESPITE the "
        "divergent inputs."),
    41: (
        "R47 CORRECTED VERDICT - PER-KILL scoring: the ledger +600 "
        "(6702->7302) while ALL 12 per-tap deltas read 0 - the 3f "
        "window ends before the bullet ARRIVES.  The +600 = 6 "
        "corpse transitions x +100 (slots 19,13,23,27,33,34; "
        "0x515c respawned at the SAME x 1274.5).  ZERO "
        "surviving-hit payment (n=11+6).  Lessons: the tap window "
        "must contain the bullet FLIGHT; per-tap deltas INVALID "
        "for delayed-pay weapons."),
    47: (
        "R50 CORRECTED VERDICT (offline): (1) THE CONTROLS NEVER "
        "PAY (4 windows); (2) KILL LANE CLEAN: both +100 co-land "
        "lag-0 on the registrations (x 1389.2/1349.8) - n=6 for "
        "the registration-locked class; (3) THE PIERCING "
        "DISCOVERY: the CONNECT tap at the 0xab94 target killed "
        "the mortal BEHIND it - the gate needs the "
        "bullet-transparent predicate; (4) 0xae7c EXONERATED x2; "
        "(5) the CONNECT MAGNITUDE UNSETTLED - +500 x3 vs +1000 "
        "x3, all mid-wound-recovery.  Ledger +2700."),
    40: (
        "R47 the SINGLE-BULLET TAP PROTOCOL (the two-stage "
        "FOREGROUND protocol, cap disclosed).  SANDBOX ROLLBACK: "
        "the R45 frontiers LOST; the rebuild DETERMINISTIC - "
        "r47_frontier_a px 1224.9 + b px 1254.8 = the 4th "
        "reproduction.  Boot 2 crashed AFTER the control tap - "
        "REFUNDED + cap 2->3 DISCLOSED; boot 3 clean: 12 taps (1 "
        "control + 11 single-bullet 3f Y), 28s wall."),
    37: (
        "R45 the 0x4054 soft-soldier HP readout (restore-only "
        "from r45_frontier_a): 1 control + 14 aimed taps + the "
        "wide net (u16 0x88..0xA8).  BOUNDED NEGATIVE: +0xA4 = 0 "
        "(armored-only), +0x8E = screen-x again; the slot-20 "
        "soldier died on the 2nd aimed tap, flat +100 = the "
        "ONE-HIT kill class; no damage counter in 0x88..0xA8 "
        "(n=1).  Score: +500 (tap 1, OBSERVED), +100 x3."),
}

R76_EVENTS = [
    {
        "round": "R76",
        "status": "OBSERVED",
        "what": (
            "R76 THE SAVESTATE BATTERY (the owner directive "
            "executed: freeze at the death point, load, test - 100 "
            "tests, each exactly once; ONE product boot + the "
            "restore-only battery via the core serialize/"
            "unserialize; the boot-1 route parity-gate string/int "
            "defect fixed; the battery-only retry on the boot-1 "
            "disk checkpoints; the DISCLOSED cap 3->4 amendment "
            "for the crashed boot-3).  THE BLOCKS: A the "
            "death-dodge matrix (55 = 11 offsets x 5 actions from "
            "CP_C f1820), B the marcher/corridor (20 from CP_B "
            "f1495), C the connect geometry (12 from CP_A2 f1375: "
            "the lands 255..263), D the death mystery (10 from "
            "CP_D f1878), E the controls (3)."),
        "provenance": {
            "source": "scripts/r76_savestate_battery.py + "
                      "r76_battery_plan.json",
            "evidence": "data/games/SLUS-01212/truck_evidence/r76/"
                        "r76_battery.jsonl",
            "boots": 2,
        },
    },
    {
        "round": "R76",
        "status": "VERIFIED",
        "what": (
            "R76 THE CONNECT-WINDOW WIDTH MEASURED (the C-block): "
            "the connectable lands = {255, 257, 259, 261} (the "
            "259-grid +-3f, the EVEN lands closed - the 2f "
            "parity); the determinism x2 (the 259 repeat "
            "connected); the IDLE control clean.  FOUR "
            "connectable lands per 164f period at the 2f spacing "
            "- the gre40 cadence admits one connect per window."),
        "provenance": {
            "source": "scripts/r76_savestate_battery.py (the "
                      "C-block)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r76/"
                        "r76_battery.jsonl",
            "boots": 2,
        },
    },
    {
        "round": "R76",
        "status": "VERIFIED",
        "what": (
            "R76 THE FEED-CLEARING LOB PROVEN + THE DEATH-RESPAWN "
            "CYCLE (the B/A blocks): (1) the walk-out lob + the "
            "return lob = THE MARCHERS DIE (the score +100/+200) "
            "AND THE TRUCK CONNECTS (a4 200->100) - all three "
            "walk distances (20/40/62f) worked; (2) the FIRE "
            "barrage chips the truck once through the marchers "
            "(-10); (3) THE DEATH: every A/D test crossed the "
            "f1884 death window and RESPAWNED at px 992 php 120 "
            "gren 10 with the fight INTACT (a4 130) - THE DEATH "
            "IS THE RESPAWN CYCLE, NOT A FAIL STATE (the PRESS "
            "START auto-continue; 1UP=2 = the lives).  R77 NAMED: "
            "THE RESPAWN KILL RUN (the policy 2.4.0: the "
            "approach-walk withdrawal + the respawn handoff (the "
            "walk back to px 1071 + the ungated gre40 volley - "
            "the r69b volume law) + the kill continuation -> the "
            "W8/W9 -> the section continues)."),
        "provenance": {
            "source": "scripts/r76_savestate_battery.py (the B/A "
                      "blocks)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r76/"
                        "r76_battery.jsonl",
            "boots": 2,
        },
    },
]

R77_NEXT = {
    "id": "R77",
    "budget": "ONE kill-run boot (cap 3 disclosed pre-run; boots 2-3 "
              "the correction cycle); the restore-only arms unchanged",
    "hypothesis": "THE RESPAWN KILL RUN: (1) the approach-walk "
                  "withdrawal - the A-block proved the hold "
                  "survives the f1884 window (the walk-in IS the "
                  "death trigger); (2) after the accepted deaths: "
                  "the respawn at px 992 php 120 gren 10 -> walk "
                  "RIGHT to px 1071 -> the ungated gre40 volley "
                  "(the r69b volume law: 2/7 connects) -> the "
                  "connects (-100) + the chips -> a4 130 -> 0 = "
                  "THE TRUCK KILL; (3) the W8/W9 kill transition "
                  "-> the section continues = THE STAGE PROGRESS.  "
                  "The lives: 1UP=2 at the first death - the path "
                  "needs <=2 deaths.",
    "method": "policy 2.4.0 = the approach-walk withdrawal + the "
              "respawn handoff (the dead-branch: count the death "
              "frames, on the alive-return with px<1050 walk RIGHT "
              "to 1071, then the volley mode) + the volley "
              "endgame; the boot measures the exact kill frame + "
              "the W8/W9 transition + the post-kill section",
    "m2_gate_note": "unchanged - M2 entry gated on a clean "
                    "(deaths=0, no-restart) resolve posture",
}


def main():
    cap = json.load(open(CAP))
    arc = json.load(open(ARC))
    evs = cap["events"]
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
    for i, ev in enumerate(R76_EVENTS, start=79):
        arc["events"][str(i)] = {"round": ev["round"],
                                 "status": ev["status"],
                                 "what_full": ev["what"]}
    evs.extend(R76_EVENTS)
    cap["next_experiment"] = R77_NEXT
    cap["meta"]["last_updated"] = "2026-11-26T00:00:00Z"
    cap["meta"]["last_commit_note"] = (
        "R76: the 100-test savestate battery — the connect width "
        "{255,257,259,261}; the feed-clearing lob proven; the "
        "death = the respawn cycle; R77 = the respawn kill run")
    blob = json.dumps(cap, indent=None, ensure_ascii=False,
                      separators=(",", ":"))
    size = len(blob.encode("utf-8"))
    print(f"after: {len(evs)} events, {size} B (bound {BOUND})")
    assert size < BOUND, f"capsule over the bound: {size}"
    with open(CAP, "w") as f:
        f.write(blob)
    with open(ARC, "w") as f:
        json.dump(arc, f, indent=1)
    cap2 = json.load(open(CAP))
    assert len(cap2["events"]) == 82
    assert cap2["next_experiment"]["id"] == "R77"
    arc2 = json.load(open(ARC))
    assert arc2["events"]["81"]["status"] == "VERIFIED"
    print("round-trip OK; archive events:", len(arc2["events"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
