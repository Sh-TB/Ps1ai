#!/usr/bin/env python3
"""r72_capsule_update.py — append the R72 events to the MSX capsule,
set next_experiment = R73, and run the FINAL-MILE RECLAIM (the R71
format_note debt): the R67-R71 event what-texts compacted to the
fact-dense cores — every number/address/status preserved; the FULL
narratives already live in event_narratives_archive.json, to which
the R72 full texts are appended first.

The capsule discipline: the facts stay; the prose shrinks; the
archive holds the full form; the canonical serialization stays
COMPACT JSON under the 64 KiB shipped-validation bound.
"""
import json
import os
import sys
import time

REPO = "/home/z/my-project/ps1ai"
CAP = os.path.join(REPO, "data", "knowledge", "msx", "capsule.json")
ARC = os.path.join(REPO, "data", "knowledge", "msx",
                   "event_narratives_archive.json")
BOUND = 65536

# ---- the compactions (the fact-dense cores; the archive holds the
# full prose) ----------------------------------------------------------
COMPACT = {
    40: (
        "R47 the SINGLE-BULLET TAP PROTOCOL executed (the two-stage "
        "FOREGROUND protocol, cap disclosed pre-run).  SANDBOX "
        "ROLLBACK: the R45 frontiers LOST; the contingency verbatim "
        "(a rebuild boot, disclosed).  Stage 1: the rebuild "
        "DETERMINISTIC ACROSS ROUNDS - r47_frontier_a px 1224.9 "
        "census 13 + b px 1254.8 = the SAME postures as R45 = the "
        "4th reproduction.  Stage 2: boot 2 crashed AFTER the "
        "control tap (the post-tap scan can DROP a slot that died "
        "inside the 3f tap) - REFUNDED + cap 2->3 DISCLOSED; boot 3 "
        "clean: 12 FULL-kind taps (1 control + 11 single-bullet 3f "
        "Y), 28s wall."),
    7: (
        "D7 release condition: the section VM's pending-entity queue "
        "CLEARING releases the pin - walker state 0xB -> 0xC, flags "
        "0x1 -> 0x8, the progress word leaves 0xFFFFFFFF (PROVEN 3/3 "
        "+ the policy banner 3/3, MISSION 1 banner 6/6 total); not "
        "yet reproduced from a post-rollback rebuilt checkpoint.  "
        "Release REQUIRES the section entities dead (the chopper "
        "hop-lob |dx| 7-29; the frozen 0x4054 soldiers = 2 AIMED "
        "bullets from px ~992 side; the truck via grenade lob |dx| "
        "53-135)."),
    46: (
        "R50 the CONTROLLED-CORRIDOR tap protocol executed (fire "
        "ONLY when the aimed target is the ONLY mortal in the bullet "
        "corridor; 2 movement-only controls; CONNECT no-follow-up; "
        "KILL prefers the 0xae7c class - disclosed pre-run).  NO "
        "rollback; boot 1 CRASHED post-restore (NameError post_sc - "
        "a runner defect, ZERO taps) - cap 1->2 DISCLOSED PRE-BOOT-2; "
        "boot 2 clean, 2/2 spent.  The corridor gate STRICT (11 "
        "skips per pass); 1 marginal violation (disclosed).  GROUP "
        "RESULTS: connects 1+0, kills 0/3 - 6 paid windows, every "
        "one corridor-cleared pre-fire."),
    48: (
        "R51 the WOUND-ACCUMULATOR HUNT (restore-only, ledger cap 3 "
        "disclosed, 3/3 spent): stage 1 rebuilt the frontiers "
        "DETERMINISTICALLY (px 1224.9/1254.8 - the SAME postures as "
        "R45/R47; 4 deaths / 4 rescues, TAINTED).  Stage 2 under "
        "pay-frame telemetry: two +1000 connects (0x42bc AND 0x3f48, "
        "both slot20 recoveries), the +100 kill class n=2 more (n=6), "
        "PIERCE replicated n=2 (n=3), controls 0 payments (n=4).  NO "
        "word separated +1000 from +500 - the hunt needs the "
        "FRAME-EXACT union-net read (the R52 lever).  Ledger +2200."),
    49: (
        "R51 CORRECTED VERDICT (r51_analysis_correct.py, offline): "
        "(1) PIERCING REPLICATED n=2 - both PIERCE taps (aimed at "
        "the 0xab94 slot30) paid +100, the transparent target NEVER "
        "reacted; the +100 co-lands lag-0 on slot18's 0x515c "
        "registration BEHIND it (x 1357.2, holder_invul=30) - the "
        "bullet passes 0xab94 and kills the first vulnerable mortal "
        "behind; (2) THE CONTROLS NEVER PAY (4 windows); (3) two "
        "MORE +1000 connects (st_pre 0x42bc AND 0x3f48, both "
        "slot20 recoveries) - +500 x3 vs +1000 x5 across R48-R51; "
        "(4) the wound-word hunt NEGATIVE at tap-window granularity "
        "- needs the FRAME-EXACT read = the R52 lever; (5) 0xae7c "
        "exonerated twice more.  Ledger +2200."),
    53: (
        "R66 the +500 CAPTURED AT THE PAY FRAME (R48-R52 never "
        "reached it): pass B (the corrected predicate) tap 6: "
        "score 7702->8202 (+500) at tail f1 = the bullet-impact "
        "frame, victim pre-hit; 0x5b0c registration at tail f3; "
        "the slot12@0xa0 pulse (257->2, rec 4) co-timed.  Two more "
        "+1000s (0x42bc tail f3; 0x3f48 tail f4): magnitude +500 "
        "x4 vs +1000 x7.  PAY-FRAME LAW: the accumulator pays ~2 "
        "frames BEFORE the visible registration (3/3).  +500 is "
        "not confined to 0x42bc connects; kills do not always pay."),
    43: (
        "R48 CORRECTED VERDICT - TWO PAY CLASSES, FRAME-EXACT "
        "(r48_analysis_correct.py, offline, authoritative): (1) "
        "DEATH-INITIATION-LOCKED n=3 - the flat +100 lands EXACTLY "
        "on the 0x515c entry frame, corpse 0x4BE4 follows 1-4f "
        "(taps 2/3/5; x 1284.2/1351.2/1293.2); (2) a "
        "SURVIVING-CONNECT payment n=1 - the +500 lands at tap-1 "
        "f_rel 2 where the ONLY event is slot-20's 0x42bc "
        "hit-reaction, the slot SURVIVES (its death 23f later) - "
        "the R47 'ZERO surviving-hit payment' FALSIFIED; the R45 "
        "'+500 unresolved' RESOLVED.  Both pure models falsified: "
        "payments land at the connect/kill-registration frame, the "
        "corpse lags 1-14f; this ledger +800; the ZERO-INPUT "
        "control walk: 4 natural deaths paid 0."),
    47: (
        "R50 CORRECTED VERDICT (r50_analysis_correct.py, offline): "
        "(1) THE CONTROLS NEVER PAY (4 windows); (2) KILL LANE "
        "CLEAN: both +100 co-land lag-0 on the registrations (x "
        "1389.2/1349.8) - n=6 for the +100 registration-locked "
        "class; (3) THE PIERCING DISCOVERY: the CONNECT tap at the "
        "0xab94 target killed the mortal BEHIND it - the gate needs "
        "the bullet-transparent predicate; (4) 0xae7c EXONERATED (2 "
        "more cycles, 0 co-landings); (5) CONNECT MAGNITUDE "
        "UNSETTLED - +500 x3 vs +1000 x3 (0x42bc/0x2b74/0x3f48), "
        "all mid-wound-recovery of SURVIVING targets.  Ledger "
        "+2700 (a +1600, b +1100)."),
    45: (
        "R49 CORRECTED VERDICT (r49_analysis_correct.py v2, the "
        "GLOBAL-frame per-slot matcher): (1) surviving-connect "
        "+500 REPLICATED (a-tap1: slot20 0x42bc at the pay frame, "
        "ZERO registrations in [-2,+6]; recovers 0x5b0c and walks "
        "on - n=2); (2) +100 kill payments n=4, all lag-0 on 0x515c "
        "registrations but NONE is the aimed target - all CYCLING "
        "ZONE ENTITIES = payment REFINED to PLAYER-BULLET-VICTIM-"
        "LOCKED; the 11 zone/wound registrations paid 0; (3) "
        "UNRESOLVED residual n=1: the same connect context paid "
        "+1000 once.  Strong class-keyed form FALSIFIED; weak form "
        "stands n=1+n=4.  Ledger +1900/11 taps."),
    41: (
        "R47 CORRECTED VERDICT - PER-KILL (kill-locked) scoring: "
        "the cumulative ledger +600 (6702->7302) while ALL 12 "
        "per-tap window deltas read 0 - the 3f window ends before "
        "the bullet ARRIVES (flight ~8-15f at dx ~+50).  The +600 = "
        "EXACTLY 6 dated corpse transitions x +100 (slots "
        "19,13,23,27,33,34; st 0x515c respawned at the SAME x "
        "1274.5).  ZERO surviving-hit payment: 11 single bullets, 6 "
        "deaths, no +100 that is not a corpse.  Lessons: the tap "
        "window must contain the bullet FLIGHT; per-tap deltas "
        "INVALID for delayed-pay weapons; the entity scan can drop "
        "a slot inside the tap (fixed)."),
    39: (
        "R46 CORRECTED VERDICT - the slot-20 soft-soldier one-hit "
        "SIGNATURE (r46_analysis_correct.py, offline): the R45 "
        "'one-bullet kill' was a TWO-EVENT chain - the Y tap "
        "CONNECTED (0x42bc hit-reaction at lag 0, the victim "
        "SURVIVED) and a wandering ZONE bullet killed it ~1.2s "
        "later (0x515c + the corpse); the +500 co-landed with the "
        "CONNECT, the +100 with the registration.  The kill-class "
        "key = REGISTRATION-locked (+100 on 0x515c/0x5b0c, n=3); "
        "the connect-class key stands (+500 on 0x42bc, n=2).  The "
        "R45 kill-without-payment rows were CORPSE-BLIND scan "
        "artifacts (the corpses leave the scan window ~+138f)."),
    30: (
        "R43 boots 6+7 (two-stage split, the cross-process "
        "savestate restore): the depth-conditional gate saved "
        "r43_postkill at c172 (px=992.0, flags=0x4B = the R41 "
        "RELEASE_SIGNATURE) - but POST-RESTART + CHECKPOINT-"
        "RESPAWN (a silent timer-expiry restart px 1150->25, the "
        "checkpoint reload back to 992).  Stage 2: 900 latch "
        "chunks, 8 deaths (continue-rescued), score 4501->13704, "
        "px to 1378 (PAST the 1285-1310 wave) but held at the "
        "1272 clamp; mission_end NEVER latched.  THE PRIMARY "
        "NEGATIVE: the INTERACTIVE M2 entry is NOT claimable from "
        "a post-restart posture; the clean deaths=0 resolve "
        "posture remains the requirement."),
    5: (
        "The '+0x8E = entity HP' label is CONTRADICTED for world "
        "entities, UNRESOLVED for slot 0.  (a) the parked truck "
        "+0x8E stayed 254->254 under standing fire while +0xA4 fell "
        "300->0 under grenades (the '254->207 grenade damage' was "
        "the truck MOVING); (b) the chopper +0x8E decayed 148->2 "
        "with NO fire (the camera advance, 3/3); (c) static: writer "
        "0x80064674 adds camera-scroll deltas to +0x8C/+0x90 (+0x8E "
        "= the screen-x integer half); (d) the Issue #5 freeze A/B "
        "held the PAIR 0x800CA2F6+0x800CA2FE (word causality never "
        "isolated).  RULE: +0x8E EXCLUDED from success oracles; "
        "armored HP evidence = +0xA4; role entity_field_+0x8E."),
    9: (
        "R38 D7 PIN STILL HOLDS FROM THE REBUILT PHASE - blocker "
        "ISOLATED to the chopper: slot 4 = chopper (st 0xAA94/0xABDC "
        "cycle, hp_a4 300, h 207-210) ALIVE at every pin while the "
        "truck is a wreck (0xA44C) and the wave dead.  The aa_kill "
        "rule connected once live per run (hp_a4 300->200 = the "
        "-100 grenade signature, deterministic x2); the kill needs 3 "
        "connects and the connect rate ~1/10 throws.  A |dx|<=40 "
        "pre-throw gate FALSIFIED (0/6); ungated + rain-hop restored "
        "= stable.  F6 respawn refills grenades (8->10).  Cheats "
        "stayed OUT of all success claims."),
    26: (
        "R42 boot-2 CORE RESULT (the capsule hypothesis CONFIRMED): "
        "from r42_postkill the shipped policy latched mission_end at "
        "latch-c24 (px 1562, score 7701), then the HARD zero-input "
        "hold ran 1600 chunks: the world FLOWED through M2-load-"
        "shaped signatures (teardown at score 7800 = the M1->M2 "
        "loading score; M2-spawn-shaped px 74.0/php 74 vs the "
        "recorded spawn 74.6/76.4; teardown at score 10930 = the "
        "train-ride fade) and the restart classifier NEVER fired.  "
        "The R41 restart leak was a HARNESS INPUT LEAK; D7 CLOSED "
        "as bypassed-by-mission-end."),
    37: (
        "R45 the 0x4054 soft-soldier HP-word readout (restore-only "
        "from r45_frontier_a px 1224.9 score 6702): 1 control + 14 "
        "aimed taps + the wide net (u16 0x88..0xA8 step 2).  "
        "BOUNDED NEGATIVE + constructive: +0xA4 = 0 throughout "
        "(armored-only), +0x9E silent, +0x8E = screen-x again; the "
        "slot-20 soldier (st 0x4054, dx +60.8) died on the 2nd "
        "aimed tap, flat +100 at the death tap = the ONE-HIT kill "
        "class; no damage counter in 0x88..0xA8 (n=1).  Score: "
        "+500 (tap 1, unresolved - OBSERVED), +100 x3.  Note: the "
        "tap fallback hit AIRBORNE projectiles (dscore 0) - filter "
        "kind=='enemy'."),
    58: (
        "R67 the PRODUCT-PATH TRUCK CAMPAIGN (policy 1.1.0->1.4.2, "
        "adapter 0.2.0->0.3.0, 40 offline tests): T1 the truck "
        "identity = the 0x9E88 state word (the (6,h=64) identity "
        "was a FALSE-POSITIVE TRAP); the REAR fight (BACK = the "
        "legal LEFT; at the section pin the wave AND the truck "
        "are BEHIND the player - three identical forward-only "
        "deaths); the CADENCE law (the fire cadence is part of "
        "the deterministic wave trajectory - the 12f cadence "
        "starved the wave, the 13f rhythm reproduced the R66 "
        "record BYTE-EXACT).  ep1 score 2300 = the record then "
        "(the R68 correction REFUTED the truck-kill reading).  "
        "Mission 1 NOT cleared."),
    59: (
        "R68 EXPERIMENT TRACK - the +500 n>=2 GOAL MET (cap 3, "
        "3/3): boot 1 the env probe (the anchor restores alive "
        "px 258.6 - the SIXTH rollback: the r66 frontiers LOST); "
        "boot 2 the disclosed rebuild contingency (frontier_px "
        "1254.8 = the record EXACTLY, 7-for-7); boot 3 the hunt "
        "via r66t1.do_stage2(only='b') - THE R66 CODE PATH "
        "ITSELF: THE +500 CAPTURED AT TAP 6 (slot16, st_pre "
        "0x1e38, pay tail f1 - BYTE-IDENTICAL causal chain).  "
        "The +500 class stands n=2.  Honest note: the "
        "CONNECT/KILL counters 0/0 while the score PAID at taps "
        "2 (+1000) and 6 (+500)."),
    60: (
        "R68 PRODUCT TRACK - the failure-mode map + THE R67 "
        "CORRECTION (adapter 0.3.0->0.4.0: the truck dead family "
        "{0xA304,0xA44C,0xA45C} joins CORPSE_ST + dead_truck_x; "
        "policy 1.5.0->1.6.2: W8/W9/T2'/T6'): 'TRUCK KILLED score "
        "2300' REFUTED (the truck a4=160 from f1160 to the death "
        "f1462; the score was the wave+chips).  v1.5.0 = the R67 "
        "trace BYTE-IDENTICAL; v1.6.0 the chase = 1318f/2800 THE "
        "RECORD (the lobs LAND at dx -133.5 px 1071: a4 300->80); "
        "v1.6.1 the chip-stand = 1218f/1400 REGRESSION (THE "
        "BULLETS DO NOT REACH a truck behind the pin); v1.6.2 = "
        "tied - the CONNECT RATE (~1/10) is the R69 blocker.  "
        "Evidence: truck_evidence/r68/ + r68_analysis.json."),
    61: (
        "R69 the +500 FINGERPRINT XREF (lead 1, OFFLINE, ZERO "
        "boots; r69_fingerprint_xref.py): capstone decode 155,136 "
        "EXE + 28,850 overlay insns (shas verified).  (1) 0x800EE318 "
        "has EXACTLY 9 direct code xrefs, all in the EXE HUD/"
        "credit cluster 0x800472c0..0x80052820 (score_add reads "
        "ent +0xCC/+0xD0/+0xD4); (2) the amounts 500/1000 in NO "
        "code immediate (both candidates FALSIFIED) and in NO "
        "EXE table; (3) THE KILL-CREDIT u16 TABLES in the "
        "overlay data head (0x8009C134 n=43, 0x8009C48C n=44, "
        "0x8009C91C n=23; values 200..1100); (4) the overlay "
        "TAIL (0x800AB230.., undecompiled): 207 fingerprint "
        "accesses (72 stores) + the damage dispatch enemy_800A41D8 "
        "-> func_0x800ae794/0x800ae7cc.  VERDICT: the payment "
        "writer NARROWED (the exact store = a RUNTIME fact).  "
        "The SEVENTH rollback disclosed."),
    63: (
        "R70 THE PHASE LAW + the boot corrections (policy "
        "1.7.1->1.8.5, adapter 0.4.0->0.5.1; 5 boots): (1) the "
        "vulnerability cycle 164f PHASE-LOCKED TO THE FREEZE (the "
        "first 0x9E88 sighting f811; the connects at freeze+178+"
        "164k = f989/f1153; the scroll/knockback on the SAME "
        "clock - the boot-1 push f985 = the r69 push f1149 minus "
        "164f); (2) THE SPATIAL LAW: every connect at dx -133.5 "
        "EXACTLY; the phase-PERFECT -130.5 MISSED - the geometry "
        "~+-3px TIGHT (the band [131.5,135.0] admits only the "
        "proven center); (3) THE CORRIDOR LAW 'the arc clears "
        "the blockers' REFUTED (the f989 lob STOLEN) - the C2 "
        "guard shipped; (4) THE PACKING LAW: five chasers DROPPED "
        "the truck row - the 0.5.1 truck-packing priority; (5) "
        "C5 the escort classes (1,2,3,5,6); (6) C4 the width "
        "probe FIRED (a4 300->290 = the CHIP measured).  "
        "OUTCOME: NO kill - best a4 300->230 (the stray chips = "
        "a SECOND damage path), death f1324, score 2100.  THE "
        "KILL MATH: chips + TWO centered connects reach a4 0 "
        "in-window."),
    64: (
        "R70 the driver semantics + the suite: the FREEZE anchor "
        "chain 0x9C14 (f733..f808, x 842.5->937.5 at +1.25 px/f, "
        "a4 ALREADY 300) -> 0x9E08 (2f) -> 0x9E88 (adapter "
        "SC_TRUCK_IN = 8); the FLIGHT EXACTLY 30f (2/2); the k=0 "
        "lead UNREACHABLE from the drive-in walk (the posture "
        "arrives 20-45f late); the knockback hazard (-33px, the "
        "scroll cancels the recovery walk - v1.8.5 HOLDS below "
        "the band).  Suite 903+10+1 (the 8 failed + 11 errors = "
        "the pre-existing flappy ONNX env regressions, not the "
        "R70 footprint)."),
    65: (
        "R71 THE CHIP-CONNECT KILL SCHEDULE (the capsule lever, "
        "the product track; policy 1.8.5->1.9.0 K1, adapter "
        "0.5.1->0.5.2; 3 boots, cap 3 disclosed pre-run, 3/3 "
        "spent).  K1 = the aimed cooldown chip-fire inside the "
        "corridor-cleared throw branch (the C2 guard; the "
        "grenade keeps grid priority; the 12f cadence).  BOOT 1: "
        "8 chips 300->220 (THE AIMED CHIP PATH CONFIRMED); the "
        "k=0 WITHHELD by the GHOST BLOCKER (slot23 st 0x6730 "
        "dead-walk, a4 0); the k=1 lob STOLEN by the INVISIBLE "
        "THIEF STACK (x 1062.3: 0xb4e4/0xabdc/0xb4e4 - the h>64 "
        "drop hid live rows); death f1298 score 2400 = THE "
        "RECORD.  BOOT 2 (0.5.2: the a4-aware liveness filter): "
        "the k=0 FIRED and MISSED; 13 chips 300->170; the k=1 "
        "withheld; death f1714/1800.  BOOT 3 (the disclosed "
        "ONE-VARIABLE arm TRUCK_CHIP_FIRE=False = the v1.8.5 "
        "hold semantics): all three grid throws fired and THE "
        "CONNECT LANDED a4 280->180 at f1659 = freeze+506+-2f ON "
        "THE PHASE GRID (k=2); the k=0/k=1 ON-grid MISSED - THE "
        "PHASE LAW IS STREAM-DEPENDENT (verified on the v1.7.1 "
        "volley 2/7; falsified on the v1.9.0 streams).  OUTCOME "
        "(honest): NO kill - best 1 connect + 5 chips, a4 160; "
        "the connect is the bottleneck (1/3 idle-hold, 0/2 "
        "chip-fire).  Evidence: truck_evidence/r71/ "
        "r71_chip_probe*.jsonl + the PNGs."),
    66: (
        "R71 THE CORRIDOR-FEED MAP (offline over the preserved "
        "product JSONLs - no boots): the walker spawn zone is "
        "POSITION-KEYED (the spawn x band ~969-1180 across boots "
        "2-3; the hygiene stays position-keyed = the escort "
        "rule).  The corridor occupancy at the grid lands is "
        "STREAM-DEPENDENT: the chip-fire stream left the k=1/k=2 "
        "lands OCCUPIED (the guard withheld, boot 2); the "
        "idle-hold stream kept ALL FOUR lands clean (boot 3).  "
        "Evidence: truck_evidence/r71/r71_corridor_feed_map.json."),
    67: (
        "R71 THE WATCHPOINT PASS (the capsule lever, the "
        "experiment track, restore-only; the ledger cap 2->4 by "
        "two DISCLOSED amendments - boot 3 a no-op env-var tool "
        "bug, honestly labeled).  Stage 1: the frontier rebuild "
        "BYTE-EXACT AGAIN (px 1254.8, 8-for-8).  Stage 2: the "
        "verbatim R66 pass-B tap replay with the watchpoint "
        "telemetry at the DISCLOSED R52 seam: THE +500 CAPTURED "
        "AT THE WATCHPOINT - tap 6 verbatim (slot16, st_pre "
        "0x1e38, dx +20.3, score 7702->8202) at flight TAIL f1 - "
        "the pay-frame law 3/3.  THE CLUSTERS: the +1000 "
        "COMPLETE (1034 B, 200 regions) INCLUDING the score-word "
        "0xEE318-0xEE31A; the +500 (2695 B) had its 2-B score "
        "region cut by the top-N cap (the tool limit).  THE "
        "FOOTPRINT: the STACK band 0x1FFD00-0x1FFF00 + the "
        "ENTITY rows 0xCA6xx-0xCBDxx + the HUD neighborhood "
        "0xEE3xx-0xEF4xx.  THE PC: NOT readable on beetle (no "
        "CPU state export); the follow-up = the PCSX-Redux "
        "oracle (the R64 matrix).  The replay BYTE-IDENTICAL "
        "across three boots.  Evidence: r71wp_stage2.jsonl + "
        "r71wpc_stage2.jsonl."),
}

# ---- the R72 events (compact; the full texts go to the archive) ------
R72_EVENTS = [
    {
        "what": (
            "R72 THE VOLLEY+PHASE HYBRID (the capsule lever, the "
            "product track; policy 1.9.0->2.0.0: TRUCK_CHIP_FIRE "
            "default RE-SELECTED to False per the R71 boot-3 "
            "stream evidence (the K1 arm stays patchable) + "
            "the phase gate widened to the FULL +-2f of ANY "
            "grid point, BOTH sides).  BOOT 1 (cap 3 disclosed "
            "pre-run, 1/3 spent, 2 HELD): the freeze f1151 (px "
            "the drive-in VERIFIED 0x9C14 f1073 x 842.5 -> 0x9E08 "
            "f1149 -> 0x9E88 f1151 - NO anchor alias); the hybrid "
            "threw ON GRID at the PRE-SIDE frames fight_f "
            "146/310/475 (the lands freeze+176/340/505 - the "
            "v1.9.0 gate could NEVER throw those); THE "
            "CONNECT LANDED a4 280->180 at f1657 = freeze+506 "
            "EXACT (the land 1656 = freeze+505, the -1f side) - "
            "THE PRE-SIDE VALIDITY CONFIRMED at k=2; the k=0/k=1 "
            "lands MISSED on a CLEAN corridor; 3 chips (300->170 "
            "at the death); the death f1844 AT the posture px "
            "1071 (php 198, gren 0 - the gun-duel attrition); "
            "NO kill (a4 170); score 700 (the mechanism probe).  "
            "THE CROSS-BOOT LAW CANDIDATE: k=2 connects 2/2 (R71 "
            "boot-3 506+-2 + R72 boot-1 505/506) while k=0/k=1 "
            "miss 0/4 across both boots x both gate sides, and "
            "the r69b volley hit k=0/k=1 on ITS stream - THE "
            "CONNECT WINDOWS ARE STREAM-OWNED; the R73 lever.  "
            "Evidence: truck_evidence/r72/"
            "r72_hybrid_probe_boot1.jsonl + the PNGs."),
        "status": "OBSERVED",
        "round": "R72",
        "provenance": {
            "source": "scripts/r72_hybrid_probe.py (the shipped "
                      "v2.0.0 default; no module patching)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r72/"
                        "r72_hybrid_probe_boot1.jsonl",
            "boots": 1,
        },
    },
    {
        "what": (
            "R72 THE CORRIDOR-FEED MAP (offline, boot-1 JSONL - no "
            "boots): the corridor was CLEAN at ALL FOUR grid "
            "lands (1329/1493/1657/1821 +-2f) - the k=0/k=1 "
            "misses were NOT thefts (the R71 interloper mode "
            "absent on the idle-hold stream); the miss mechanism "
            "NARROWED to the phase-internal question (the "
            "stream-owned lands / the flight variance), NOT the "
            "corridor feed; the connect registered at "
            "freeze+506 EXACT (the pay-frame register frame).  "
            "Evidence: truck_evidence/r72/"
            "r72_corridor_feed_map.json."),
        "status": "OBSERVED",
        "round": "R72",
        "provenance": {
            "source": "scripts/r72_corridor_feed_map.py (offline)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r72/"
                        "r72_corridor_feed_map.json",
            "boots": 0,
        },
    },
    {
        "what": (
            "R72 THE PAYMENT-CLUSTER XREF (the capsule lead 2, "
            "offline, ZERO boots; capstone decode 155,136 EXE + "
            "28,850 overlay insns + the committed call graph): "
            "THE PAYMENT WRITER PINPOINTED - the score-word store "
            "0x8005c508 sw $a1,-0x1ce8($a2) -> 0x800EE318 in the "
            "accumulator 0x8005c4b4 (frame 40 B; the base "
            "lw $a2,($a1) = HANDLE-mediated; the delta via the "
            "format->parse chain 0x8007e8b4 -> 0x8007e7d4 - the "
            "R69 falsification EXPLAINED: the amounts 500/1000 "
            "live in the overlay kill-credit tables and arrive "
            "FORMATTED); the P1 bit andi 1, the P2 twin -> "
            "0x800EE320; the 99,999,999 cap (0x5f5e0ff); the %100 "
            "display twin (0x51eb851f); the clear twin 0x8005c734 "
            "in 0x8005c6d4 (4 jal callers in the game-reset "
            "cluster).  THE CENSUS: exactly 3 score-word "
            "stores in the EXE, 0 in the overlay; 178 HUD-band "
            "store sites (confirmed on lui chains).  THE "
            "BOUNDS (disclosed): the accumulator has NO direct "
            "jal xref - the dispatch is pointer-mediated (the "
            "runtime PC = the PCSX-Redux oracle, the R64 matrix "
            "item); the stack-band churn = the accumulator's own "
            "40 B frame (depth <=2); the entity-row churn slots "
            "+1000 {0,3,4,6,7,12,16,18,20,21,24,28,30} / +500 "
            "{3,16,18} - slot 16 the capture slot, slot 12 the "
            "R66 registration witness.  Evidence: "
            "truck_evidence/r72/r72_cluster_xref.json + .md."),
        "status": "VERIFIED",
        "round": "R72",
        "provenance": {
            "source": "scripts/r72_cluster_xref.py (offline, "
                      "zero boots)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r72/"
                        "r72_cluster_xref.json",
            "boots": 0,
        },
    },
]

NEXT_EXPERIMENT = {
    "id": "R73",
    "budget": "the experiment track stays restore-only arms from "
              "the r66 frontiers (the rebuild byte-exact 8-for-8); "
              "the product track: ONE hybrid boot with the "
              "stream-calibrated throw schedule (the ledger cap "
              "disclosed pre-run)",
    "hypothesis": "THE CONNECT WINDOWS ARE STREAM-OWNED (the R72 "
                  "cross-boot law candidate: k=2 2/2 vs k=0/k=1 "
                  "0/4 on the idle-hold/hybrid stream; the r69b "
                  "volley hit k=0/k=1 on ITS stream).  The kill "
                  "needs 3 connects — the schedule must spend the "
                  "grenades at the stream's PROVEN lands first.  "
                  "Two evidence-armed leads: (1) PRODUCT — the "
                  "stream-calibrated schedule: bias the hybrid's "
                  "throw budget to the measured connect lands of "
                  "the CURRENT stream (the k=2 window freeze+506+-2 "
                  "first; the k=0/k=1 demoted to opportunistic), + "
                  "the K1 chip supplement re-armed AFTER the first "
                  "connect (the R70 kill math); (2) SOURCE-FIRST — "
                  "the writer-PC runtime confirmation via the "
                  "PCSX-Redux CPU oracle (the R64 tools-matrix "
                  "item; the accumulator 0x8005c4b4 is pinpointed — "
                  "the oracle closes the dispatch bound)",
    "method": "product-path: policy 2.1.0 = the stream-calibrated "
              "schedule (the measured lands first, the one-variable "
              "delta vs v2.0.0); experiment-track: the PCSX-Redux "
              "oracle build (headless Lua, the PC watch on "
              "0x8005c508) — offline tooling, zero boots",
    "m2_gate_note": "unchanged - interactive M2 entry stays gated "
                    "on a clean (deaths=0, no-restart) deep resolve "
                    "posture",
}


def main():
    cap = json.load(open(CAP))
    arc = json.load(open(ARC))
    evs = cap["events"]
    before = os.path.getsize(CAP)
    print(f"before: {len(evs)} events, {before} B")

    # 1. the archive: append the R72 FULL texts
    for ev in R72_EVENTS:
        arc["events"][str(len(arc["events"]))] = {
            "round": ev["round"], "status": ev["status"],
            "what_full": ev["what"]}

    # 2. the compaction (the facts stay; the prose shrinks)
    for idx, txt in COMPACT.items():
        full = evs[idx]["what"]
        assert len(txt) < len(full), (idx, len(txt), len(full))
        evs[idx]["what"] = txt
    saved = sum(len(evs[i]["what"]) for i in COMPACT)
    print(f"compacted {len(COMPACT)} events")

    # 3. the R72 events
    for ev in R72_EVENTS:
        evs.append(dict(ev))
    print(f"events now: {len(evs)}")

    # 4. next_experiment + the meta
    cap["next_experiment"] = NEXT_EXPERIMENT
    cap["meta"]["last_updated"] = time.strftime(
        "%FT%TZ", time.gmtime())
    cap["meta"]["last_commit_note"] = (
        "R72: the volley+phase hybrid executed (policy 2.0.0 - "
        "the chip-fire default re-selected False + the FULL +-2f "
        "gate; boot 1 threw ON GRID at the PRE-SIDE frames and "
        "THE CONNECT LANDED at freeze+506, k=2; the k=0/k=1 "
        "missed on a CLEAN corridor; NO kill, a4 170; the law "
        "candidate: the connect windows are STREAM-OWNED, k=2 "
        "2/2 vs k=0/k=1 0/4) + the payment-cluster xref (ZERO "
        "boots): THE PAYMENT WRITER PINPOINTED - 0x8005c508 in "
        "0x8005c4b4 (the R69 falsification explained); the R73 "
        "lever = the stream-calibrated schedule + the PCSX-Redux "
        "writer-PC oracle.  Mission 1 OPEN.")
    cap["meta"]["format_note"] = (
        "R72: the canonical serialization stays COMPACT JSON "
        "(indent=None); the R72 final-mile reclaim compacted the "
        "R67-R71 event what-texts to the fact-dense cores (every "
        "number/address/status preserved; the FULL narratives in "
        "event_narratives_archive.json + git history); the "
        "shipped-validation bound is < 64 KiB.")

    # 5. the canonical compact write + the bound check
    blob = json.dumps(cap, indent=None, ensure_ascii=False,
                      separators=(",", ":"))
    size = len(blob.encode("utf-8"))
    print(f"after: {len(evs)} events, {size} B (bound {BOUND})")
    assert size < BOUND, f"capsule over the bound: {size}"
    with open(CAP, "w") as f:
        f.write(blob)
    # the round-trip check
    cap2 = json.load(open(CAP))
    assert len(cap2["events"]) == len(evs)
    assert cap2["next_experiment"]["id"] == "R73"
    print("round-trip OK; archive events:",
          len(json.load(open(ARC))["events"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
