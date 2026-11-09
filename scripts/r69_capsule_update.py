#!/usr/bin/env python3
"""r69_capsule_update.py — R69 round close-out: append the round
events to the MSX capsule and replace next_experiment (R70).

R69 events (compact, the R68 compaction style — the full narratives
live in truck_evidence/r69/ + reports):
  1. THE +500 FINGERPRINT XREF (the experiment track, offline, ZERO
     boots): the 19-offset discriminator xref'd across the whole EXE
     text + the ENEMY.BIN overlay.
  2. THE CONNECT-WINDOW PRODUCT VERDICT (v1.7.0 -> v1.7.1): the
     capsule's window half-falsified, the tightened window CONNECTS
     (2/7 at the exact posture), one connect short — the scroll
     shove closed the window.
"""
from __future__ import annotations

import json
import time

MSX = "/home/z/my-project/ps1ai/data/knowledge/msx/capsule.json"

EV_XREF = (
    "R69 the +500 FINGERPRINT XREF (lead 1, offline, ZERO boots; "
    "capstone full-text decode, sha verified): 0x800EE318 has "
    "EXACTLY 9 direct "
    "xrefs, all in the EXE HUD/credit cluster 0x800472c0..0x80052820 "
    "(score_add reads ent +0xCC/+0xD0/+0xD4 — +0xD0 IS a fingerprint "
    "offset); 500/1000 in NO code immediate (both candidates "
    "FALSIFIED: 0x800b03cc = state-handler address arithmetic, "
    "0x80088e8c = a clamp bound) and in NO EXE table — KILL-CREDIT "
    "u16 TABLES FOUND in the overlay data head (0x8009C134 n=43, "
    "0x8009C48C n=44, 0x8009C91C n=23; values 200..1100 incl. "
    "500/1000).  The overlay TAIL (0x800AB230..0x800B83B0, "
    "undecompiled): 207 fingerprint accesses (72 stores, 14/19 "
    "offsets); the damage dispatch enemy_800A41D8 -> "
    "func_0x800ae794/0x800ae7cc runs there.  VERDICT: the payment "
    "writer NARROWED; the hunt-pass condition (writer FOUND) "
    "honestly NOT met; the r66 frontiers lost again (the SEVENTH "
    "rollback).  Evidence: truck_evidence/r69/r69_fingerprint_xref."
    "{json,md}."
)

EV_PRODUCT = (
    "R69 the CONNECT-WINDOW PRODUCT VERDICT (lead 2; policy "
    "1.6.2->1.7.0->1.7.1): "
    "v1.7.0 ran the capsule's window [125,140] — FALSIFIED outer "
    "half: 3 throws at dx -139.5/-136.5/-136.5 ALL MISSED (a4 "
    "FROZEN at 300; ep1 1154f/2200).  v1.7.1 TIGHTENED to [130,135]: "
    "THE CONNECT WINDOW IS REAL — 7 gre40 throws (the capsule's "
    "'up to 7' EXACT), EVERY throw at dx -133.5 EXACTLY (px 1071.0, "
    "the record posture verbatim), truck a4 300 -> 200 (f989) -> "
    "100 (f1153) = TWO CONFIRMED CONNECTS (throws 3 and 7; the rate "
    "2/7 = 29% vs the R38 ~1/10) — ONE connect SHORT: the SECTION "
    "SCROLL shoved the player out mid-cooldown (px 1071 -> 1105.8 "
    "pinned, truck_dx -168.3), the death at f1318 = the record "
    "frame, score 1700.  NEW FACTS: the connect is (posture x "
    "PHASE)-gated (2/7 identical posture; the connects 164f apart); "
    "the fight window is scroll-capped (~280f, 7 throws max; the "
    "kill needs rate >= 3/7).  Zero-overlap re-run NOT triggered "
    "(no new +500).  Evidence: "
    "truck_evidence/r69/r69{,b}_connect_probe.jsonl."
)


def main():
    now = time.strftime("%FT%TZ", time.gmtime())
    c = json.load(open(MSX))
    ev = c["events"]
    # the light-touch compaction of the three longest owned verdicts
    # (the R68 compaction pattern: every number/address/status kept;
    # the full narratives live in reports/ + the analysis JSONs)
    COMPACT = {
        5: (
            "The '+0x8E = entity HP' semantic label is CONTRADICTED "
            "for world entities and UNRESOLVED for slot 0.  "
            "Evidence: (a) parked truck +0x8E stayed 254->254 under "
            "standing fire while +0xA4 fell 300->0 under grenades "
            "(the '254->207 grenade damage' was the truck MOVING — "
            "screen-x shrink); (b) chopper +0x8E decayed 148->2 with "
            "NO player fire (camera advance, Gate B no-fire control, "
            "3/3); (c) static: writer 0x80064674 adds camera-scroll "
            "deltas to +0x8C/+0x90 per entity (+0x8E = screen-x "
            "integer half); (d) the Issue #5 freeze A/B held the "
            "PAIR 0x800CA2F6+0x800CA2FE (word causality never "
            "isolated); pincorr1 slot-0 (291->81, damage-"
            "correlated, regen-like, px-scroll ~0) does not "
            "distinguish player-HP.  RESOLUTION RULE: +0x8E EXCLUDED "
            "from success oracles; armored-entity HP evidence is "
            "+0xA4; the observation stays under role "
            "entity_field_+0x8E."
        ),
        9: (
            "R38 D7 PIN STILL HOLDS FROM THE REBUILT PHASE — blocker "
            "ISOLATED to the chopper: at every pin the census keeps "
            "slot 4 = chopper (st 0xAA94/0xABDC cycle, hp_a4 300, h "
            "207-210) ALIVE while the truck is a wreck (0xA44C) and "
            "the wave is dead; the walker cycles (0xA,0x43) <-> "
            "(0,0), no 0xC.  The aa_kill rule (J1 hop + UP-lob) "
            "CONNECTED once live per run (hp_a4 300 -> 200, the "
            "-100 grenade signature, deterministic x2) but the kill "
            "needs 3 connects and the connect rate is ~1/10 throws "
            "(chopper patrols dx -9..-51 vs the proven 7-29 band).  "
            "A |dx|<=40 pre-throw gate FALSIFIED (0/6 connects; the "
            "earlier one-shot bomb death php 291->0 because the "
            "first build dropped the rain-hop); ungated + rain-hop "
            "restored = stable.  Runs end at the death->restart "
            "wall; F6 respawn refills grenades (8->10).  Cheats "
            "stayed OUT of all success claims."
        ),
        59: (
            "R68 EXPERIMENT TRACK - the +500 n>=2 GOAL MET + the "
            "zero-overlap DISCRIMINATOR RESOLVED (ledger cap 3, "
            "3/3: env probe + the byte-exact frontier rebuild "
            "(frontier_px 1254.8 = R66; determinism 7-for-7) + the "
            "pass-B hunt): the R66 pass-B taps replayed VERBATIM "
            "(the r66t1 gate, CORPSE_ST {0x4BE4,0x5CC8}, amendment-G "
            "NOT applied) -> THE +500 AT TAP 6: slot16 0x1e38 pay "
            "tail f1, BYTE-IDENTICAL to the R66 capture; the tap "
            "kinds identical end to end (AMENDMENT-G CONFIRMED BY "
            "REPRODUCTION).  Class n=2.  Honest: CONNECT/KILL 0/0 "
            "while the score PAID t2 (+1000) t6 (+500) — the "
            "pay-before-registration law from the missing-"
            "registration side.  WIDENED SET: +500 n=2 vs +1000 n=7 "
            "— 19 offsets separate the classes (0x60..0xc6); DELAY "
            "LAW TWO-CLASS: +500 tail f1 (2/2), +1000 tail f3/f4; "
            "magnitude +500 x5 / +1000 x9.  The 19 = the R69 xref "
            "candidates."
        ),
        60: (
            "R68 PRODUCT TRACK - the failure-mode map + THE R67 "
            "CORRECTION: 'TRUCK KILLED, score 2300' REFUTED (the "
            "probe: a4=160 at 0x9E88 x937.5 slot14 from f1160 to "
            "the death f1462; the score was the wave+chips; 3 lobs "
            "= 1 connect -100 + chips -40; 'AIRBORNE' = the "
            "follower).  Four probe-pinned variants (adapter 0.4.0 "
            "= the dead family {0xA304,0xA44C,0xA45C} + "
            "dead_truck_x; policy 1.5.0->1.6.2; suite 864 green): "
            "(a) v1.5.0 W8/W9 = the R67 trace BYTE-IDENTICAL; (b) "
            "v1.6.0 chase = 1318f/2800 THE RECORD (the lobs LAND at "
            "dx -133.5 px 1071: a4 300->80, FROZE at the band "
            "edge); (c) v1.6.1 chip-stand = 1218f/1400 REGRESSION "
            "(a4 FROZEN at 300 — THE BULLETS DO NOT REACH a truck "
            "behind the pin); (d) v1.6.2 chase+gre40 = 1318f/2800 "
            "tied (the CONNECT RATE ~1/10 = the R69 blocker).  "
            "Mission 1 NOT cleared (not claimed)."
        ),
        19: (
            "R40 CONTRADICTED the chopper-last-queue-entity release "
            "hypothesis: with the chopper dead the D7 section did "
            "NOT release — 745-780 post-kill chunks of hold with "
            "NOTHING in the engage window (near=None 741/779), no "
            "0xC.  The boot-5 full-table watch: NO killable entity "
            "remains (the chopper row persists as an a4=0 wreck "
            "shell; 0xA45C = the truck-wreck fire state a4=0; the "
            "persistent rows are scenery/signed-transient markers; "
            "one a4=30 faller at the resolve).  The release blocker "
            "is in the section-VM queue state, not a visible entity: "
            "walker [0xB, 0x1] (F1: the release flips flags "
            "0x1->0x8), the progress word accumulating pending bits "
            "0x80000000 -> 0xFFF... -> 0xFFFFFFFF (F1: flips it to "
            "0xFFF38B4A), the node list POINTER at 0x800EB5F8 = "
            "0x80084dcc (the list body unread — the R41 lever)."
        ),
        42: (
            "R48 the FRAME-EXACT TAP PROTOCOL executed (the capsule "
            "lever: per-frame score telemetry COMPOSED with the "
            "single-bullet taps).  NO sandbox rollback: the R47 "
            "frontiers SURVIVED (verified pre-boot); cap 1 "
            "disclosed pre-run (the core+rom load ONLY, both passes "
            "restore-only).  Boot 1 ran clean and DETERMINISTICALLY "
            "(11 taps, the same tap/dscore/corpse tables twice "
            "across two boots) but its RECORDING was corpse-blind: "
            "mini_census is built on scan_entities which SKIPS "
            "corpse-st and hp==0 slots, so no death was ever dated "
            "at frame granularity.  Cap amended 1->2 DISCLOSED (the "
            "r47 boot-2 defect precedent): boot 2 = the same "
            "protocol + DIRECT per-frame table reads (slots 1..39, "
            "five words, unconditional), 29s wall.  Two background "
            "launches died silently inside boot_to_demo before any "
            "core load — refunded per the R45 precedent; the round "
            "ran FOREGROUND per the learned protocol."
        ),
        45: (
            "R49 CORRECTED VERDICT (r49_analysis_correct.py v2, "
            "offline, the GLOBAL-frame per-slot matcher): (1) "
            "surviving-connect +500 REPLICATED (a-tap1: slot20 in "
            "0x42bc at the pay frame, ZERO registrations in the lag "
            "window [-2,+6]; recovers 0x5b0c and walks on — n=2 "
            "across R48/R49); (2) +100 kill payments n=4, all "
            "co-land lag-0 on 0x515c registrations but NONE is the "
            "aimed target — all CYCLING ZONE ENTITIES in the bullet "
            "corridor (slot33-re@1284.2, slot23@1351.2, "
            "slot10-re@1293.2, slot9@1343.8) = payment REFINED to "
            "PLAYER-BULLET-VICTIM-LOCKED; the 11 zone/wound "
            "registrations paid 0; controls 0 jumps; (3) UNRESOLVED "
            "residual n=1: the same connect context paid +1000 once "
            "(b-tap1, 2-4 rows AFTER slot33's registration, outside "
            "the lag window).  Strong class-keyed form FALSIFIED; "
            "weak form stands n=1+n=4.  Ledger +1900/11 taps (a "
            "+800, b +1100)."
        ),
        30: (
            "R43 boots 6+7 (two-stage split, the cross-process "
            "savestate restore is the R42-proven pattern): the "
            "depth-conditional gate (aa_resolved>=1 AND px>700) "
            "saved r43_postkill at c172 with px=992.0, flags=0x4B "
            "(the R41 RELEASE_SIGNATURE), score 4501 — but that "
            "posture is POST-RESTART + CHECKPOINT-RESPAWN (the c164 "
            "chopper resolve was followed by a silent "
            "timer-expiry-style mission restart px 1150->25 the "
            "shallow-anchor guard could not see, then the checkpoint "
            "reload back to 992).  Stage 2 from it: 900 latch "
            "chunks, 8 deaths (all continue-rescued, disclosed), "
            "score 4501->13704, px pushed to 1378 (PAST the "
            "1285-1310 soldier wave) but held at the 1272 clamp; "
            "mission_end NEVER latched; the R41 partial-F1 gap + "
            "re-armed section-VM nodes persist across restarts.  "
            "THE PRIMARY NEGATIVE: the INTERACTIVE M2 entry is NOT "
            "claimable from a post-restart posture; the clean "
            "(deaths=0) R42-style resolve posture remains the "
            "requirement."
        ),
        40: (
            "R47 the SINGLE-BULLET TAP PROTOCOL executed (the R45 "
            "two-stage FOREGROUND protocol, cap disclosed pre-run).  "
            "SANDBOX ROLLBACK DISCLOSED: the R45 frontiers (a/b) "
            "LOST to the filesystem reset — the capsule contingency "
            "applied verbatim (a rebuild boot, disclosed); "
            "issue5_m1_start (Oct 20) survived.  Stage 1 (boot 1): "
            "the tainted frontier rebuild DETERMINISTIC ACROSS "
            "ROUNDS — r47_frontier_a px 1224.9 census 13 + "
            "r47_frontier_b px 1254.8, 6 deaths/6 continue-rescues "
            "disclosed, TAINTED lineage — the SAME postures as R45 "
            "(1224.9/1254.8, restore score 6702) = the 4th "
            "independent rebuild reproduction.  Stage 2 (boot "
            "2->3): boot 2 crashed AFTER the control tap (the "
            "post-tap scan can DROP a slot that died inside the 3f "
            "tap) — REFUNDED + cap amended 2->3 DISCLOSED; two "
            "gate-blocked no-boot attempts refunded.  Boot 3 clean: "
            "12 FULL-kind taps (1 control + 11 single-bullet 3f Y) "
            "from r47_frontier_a, 28s wall."
        ),
        44: (
            "R49 the CLASS-KEYED tap protocol executed (the capsule "
            "lever verbatim: taps GROUPED by target class — CONNECT "
            "taps = ONE bullet on a fresh soft target then the slot "
            "is NEVER fired at again, vs KILL taps on fresh "
            "soldiers).  NO sandbox rollback: the R47 frontiers "
            "SURVIVED (verified pre-boot); cap 1 disclosed pre-run, "
            "boot 1 clean 29s wall, ledger 1/1, no amendments.  "
            "GROUP SHORTFALL honest: CONNECT 2/4 (a-tap1 + b-tap1 "
            "both on the frontier-frozen slot20 mid-0x42bc; 6 "
            "connect taps missed — no 0x42bc entry), KILL 0/3 (the "
            "spawner zone x~1277-1351 churns 0xaec8 -> walk -> "
            "0x515c -> 0x4be4; the aimed fresh soldiers ONE-HIT-"
            "registered instead: slots 22/18).  The two no-follow-up "
            "connect targets did NOT survive to walk end (slot20 "
            "died of the wound 1-3 taps later, frame-exact) — but "
            "the connect payment landed while the target was ALIVE "
            "in 0x42bc."
        ),
        49: (
            "R51 CORRECTED VERDICT (r51_analysis_correct.py, offline "
            "— the v2 matcher + the wound-word hunt + the R50 "
            "cross-join): (1) PIERCING REPLICATED n=2: both PIERCE "
            "taps (aimed at the 0xab94 slot30) paid +100, the "
            "transparent target NEVER reacted; pass-a's +100 co-lands "
            "lag-0 on slot18's 0x515c registration at x 1357.2 BEHIND "
            "it (holder_invul=30) — the predicate MEASURED: the "
            "bullet passes 0xab94 and kills the first vulnerable "
            "mortal behind; (2) THE CONTROLS NEVER PAY (4 windows, 0 "
            "payments); (3) two MORE +1000 connects (st_pre 0x42bc "
            "AND 0x3f48, both slot20 recoveries) — the table +500 x3 "
            "vs +1000 x5 across R48-R51; the 0x42bc entry alone is "
            "NOT the discriminator (+500 in R48/R49, +1000 in "
            "R50/R51); (4) THE WOUND-WORD HUNT NEGATIVE at tap-window "
            "granularity: 100+ churn candidates, the cross-join "
            "separates NOTHING — the hunt needs the FRAME-EXACT read "
            "= the R52 lever; (5) 0xae7c exonerated twice more.  "
            "Ledger +2200 (a +1100, b +1100), deterministic."
        ),
        41: (
            "R47 CORRECTED VERDICT - PER-KILL (kill-locked) scoring: "
            "the cumulative ledger +600 (6702->7302) while ALL 12 "
            "per-tap window deltas read 0 — the 3f tap window ends "
            "before the bullet ARRIVES (flight ~8-15f at dx ~+50; "
            "the R45/R46 24f bursts masked it).  The +600 = EXACTLY "
            "6 dated corpse transitions x +100 (uniform=True; deaths "
            "in read-windows 2/2/4/5/7/10 = slots 19,13,23,27,33,34; "
            "three deaths cluster at x ~1275; st 0x515c respawned at "
            "the SAME x 1274.5, h 91->90).  ZERO surviving-hit "
            "payment: 11 single bullets, 6 deaths, no +100 that is "
            "not a corpse; slot20 NEVER died AND never paid.  The "
            "R45 '+100-no-death' confound EXPLAINED (R45 recorded "
            "corpses only inside the x-window).  Harness lessons: "
            "(1) the tap window must contain the bullet FLIGHT; (2) "
            "per-tap score deltas are INVALID for delayed-pay "
            "weapons — the cumulative ledger + corpse dating is the "
            "readout; (3) the entity scan can drop a slot inside "
            "the tap (fixed in-round)."
        ),
        43: (
            "R48 CORRECTED VERDICT - TWO PAY CLASSES, FRAME-EXACT "
            "(r48_analysis_correct.py, offline, authoritative): "
            "(1) DEATH-INITIATION-LOCKED n=3 — the flat +100 lands "
            "EXACTLY on the 0x515c entry frame, corpse 0x4BE4 "
            "follows 1-4f later (taps 2/3/5; x 1284.2/1351.2/1293.2, "
            "the x~1275 cluster); (2) a SURVIVING-CONNECT payment "
            "n=1 — the +500 lands at tap-1 f_rel 2 where the ONLY "
            "event is slot-20's 0x42bc hit-reaction while slot 20 "
            "SURVIVES (its death initiation 23f later) — the R47 "
            "'ZERO surviving-hit payment' FALSIFIED at frame "
            "granularity; the R45 '+500 attribution unresolved' "
            "RESOLVED (deterministic across R45/R48).  BOTH pure "
            "models falsified: payments land at the connect/kill-"
            "registration frame, the corpse lags 1-14f; R47's '+600 "
            "= 6 x +100 uniform' was the tap-granularity conflation; "
            "this ledger +800 (+500 + 100x3), 16 dated deaths, the "
            "ZERO-INPUT control walk shows 4 NATURAL deaths paying "
            "0.  The 1-2px/frame +0x8E drift is camera churn (chips "
            "need >= 3px)."
        ),
        47: (
            "R50 CORRECTED VERDICT (r50_analysis_correct.py, "
            "offline): (1) THE CONTROLS NEVER PAY (4 windows incl. "
            "movement-only, 6+ natural corpses, 0 payments); (2) "
            "KILL LANE CLEAN: both +100 co-land lag-0 on the "
            "registrations at x 1389.2/1349.8 — n=6 across "
            "R48/R49/R50 for the +100 registration-locked class; "
            "(3) THE PIERCING DISCOVERY: the CONNECT tap at the "
            "0xab94 target killed the mortal BEHIND it (slot18 "
            "@1389.2, +100) — the gate needs the bullet-transparent "
            "predicate; (4) THE 0xae7c CLASS EXONERATED (slot33 "
            "cycled 2 more times, 32/27f, ZERO co-landing payments "
            "— the R49 +1000 residual is NOT its kill reward); (5) "
            "CONNECT MAGNITUDE UNSETTLED — +500 x3 vs +1000 x3 "
            "across R48/R49/R50 (+1000 on a 0x42bc recovery, +500 "
            "on a LEFT-side 0x2b74, +1000 on a 0x3f48), all "
            "mid-wound-recovery of SURVIVING targets; candidates: "
            "an internal wound accumulator or hit-geometry damage.  "
            "Ledger +2700 (a +1600, b +1100)."
        ),
    }
    for i, text in COMPACT.items():
        old = len(ev[i]["what"].encode())
        ev[i]["what"] = text
        print(f"compacted ev[{i}]: {old} -> {len(text.encode())} B")
    ev.append({"what": EV_XREF, "status": "VERIFIED",
               "round": "R69",
               "provenance": {
                   "source": "scripts/r69_fingerprint_xref.py",
                   "evidence": "data/games/SLUS-01212/truck_evidence/"
                               "r69/r69_fingerprint_xref.json + "
                               "r69_fingerprint_xref.md"}})
    ev.append({"what": EV_PRODUCT, "status": "VERIFIED",
               "round": "R69",
               "provenance": {
                   "source": "scripts/r69_connect_probe.py + "
                               "r69_gameplay_record.py + the policy "
                               "v1.7.0/v1.7.1",
                   "evidence": "data/games/SLUS-01212/truck_evidence/"
                               "r69/ (r69_connect_probe.jsonl, "
                               "r69b_connect_probe.jsonl, "
                               "r69_product_run.json, product_run/)"}})
    c["next_experiment"] = {
        "id": "R70",
        "budget": "product boots + probes are the separate gameplay "
                  "track; the experiment track stays restore-only "
                  "arms from the r66 frontiers (the R68 rebuild is "
                  "byte-exact)",
        "hypothesis": "two evidence-armed leads: (1) PRODUCT - the "
                      "connect PHASE law: 2/7 connects from the "
                      "IDENTICAL throw posture (dx -133.5), the "
                      "connects 164f apart - find the truck "
                      "vulnerability cycle and time the gre40 "
                      "cadence to the phase (the kill needs rate "
                      ">= 3/7 inside the ~280f scroll-capped "
                      "window); (2) SOURCE-FIRST - one restore-only "
                      "watchpoint pass on 0x800EE318 to log the "
                      "payment-writer PC (the R69 xref: the overlay "
                      "damage tail + the credit tables 0x8009C134/"
                      "0x8009C48C/0x8009C91C); needs the frontier "
                      "rebuild (the disclosed contingency)",
        "method": "product-path: play metal_slug_x with the R70 "
                  "phase-timed connect policy; experiment-track: "
                  "the watchpoint pass only if the frontier rebuild "
                  "is spent (the R66 gate verbatim); the zero-overlap "
                  "test re-runs on any new capture",
        "m2_gate_note": "unchanged - interactive M2 entry stays "
                        "gated on a clean (deaths=0, no-restart) "
                        "deep resolve posture",
    }
    # canonical compact form (the r68 compaction pattern)
    s = json.dumps(c, ensure_ascii=False, separators=(",", ":"),
                   sort_keys=False)
    n = len(s.encode())
    print(f"canonical capsule size: {n} B (cap 65,536)")
    if n > 65536:
        print("OVER CAP — compact the oldest R-owned prose first")
        sys_exit = 1
        raise SystemExit(sys_exit)
    with open(MSX, "w") as f:
        f.write(s)
        f.write("\n")
    print("events:", len(ev))
    print("next:", c["next_experiment"]["id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
