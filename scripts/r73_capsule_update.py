#!/usr/bin/env python3
"""r73_capsule_update.py — append the R73 events to the MSX capsule,
set next_experiment = R74, and run the final-mile reclaim: the R72
idx70/idx68 what-texts (verbatim-archived — asserted) + the R69/R70/
R71/R48 fact cores (idx61/63/67/43 — their pre-compact capsule texts
preserved in the archive under what_full_capsule_v2, lossless) — the
r66/r67/r71/r72 precedent.  The full R73 narratives are appended to
the archive first.

The capsule discipline: the facts stay; the prose shrinks; the
archive holds the full form; the canonical serialization stays
COMPACT JSON under the 64 KiB shipped-validation bound.
"""
import json
import os
import sys

REPO = "/home/z/my-project/ps1ai"
CAP = os.path.join(REPO, "data", "knowledge", "msx", "capsule.json")
ARC = os.path.join(REPO, "data", "knowledge", "msx",
                   "event_narratives_archive.json")
BOUND = 65536

# ---- the reclaim: the fact-dense cores -------------------------------
# verbatim-archived (asserted against the archive before compacting)
RECLAIM_VERBATIM = {
    70: (
        "R72 THE PAYMENT-CLUSTER XREF (offline, ZERO boots; capstone "
        "155,136 EXE + 28,850 overlay insns): the score-word store "
        "0x8005c508 sw $a1,-0x1ce8($a2) -> 0x800EE318 in the "
        "accumulator 0x8005c4b4 (frame 40 B, HANDLE-mediated; the "
        "P1/P2 bits -> 0x800EE318/0x800EE320; the cap 0x5f5e0ff; "
        "the %100 twin 0x51eb851f).  The R69 falsification "
        "EXPLAINED: the delta via the format->parse chain "
        "0x8007e8b4 -> 0x8007e7d4 (the amounts 500/1000 arrive "
        "FORMATTED from the overlay kill-credit tables).  Exactly 3 "
        "score-word stores in the EXE, 0 in the overlay, 178 "
        "HUD-band store sites.  Bounds: NO direct jal on the "
        "accumulator (pointer-mediated dispatch; the runtime PC = "
        "the PCSX-Redux oracle)."),
    68: (
        "R72 PRODUCT: THE VOLLEY+PHASE HYBRID (policy 2.0.0): "
        "TRUCK_CHIP_FIRE default RE-SELECTED False per the R71 "
        "boot-3 stream evidence (the idle-hold stream connects ON "
        "GRID 1/3, the chip-fire stream 0/2 - THE PHASE LAW IS "
        "STREAM-DEPENDENT; the K1 arm stays patchable) + the phase "
        "gate widened to the FULL +-2f of ANY grid point BOTH "
        "sides; 19 new offline tests, zero weakened.  BOOT 1 (cap "
        "3 disclosed, 1/3 spent): the freeze f1151 (the drive-in "
        "0x9C14 f1073 x 842.5 -> 0x9E08 f1149 -> 0x9E88 f1151); "
        "the hybrid threw ON GRID at the PRE-SIDE frames fight_f "
        "146/310/475 (the lands freeze+176/340/505) and THE "
        "CONNECT LANDED a4 280->180 at f1657 = freeze+506 EXACT "
        "(the -1f side) - PRE-SIDE VALIDITY CONFIRMED at k=2; the "
        "k=0/k=1 MISSED on a CLEAN corridor; the death f1844 AT "
        "the posture; NO kill (a4 170), score 700.  THE CROSS-BOOT "
        "LAW CANDIDATE: the connect windows are STREAM-OWNED.  THE "
        "CORRIDOR-FEED MAP: the corridor CLEAN at ALL FOUR lands - "
        "the misses are NOT thefts."),
}
# the pre-compact capsule text preserved in the archive (lossless),
# then the fact-dense core
RECLAIM_PRESERVE = {
    61: (
        "R69 the +500 FINGERPRINT XREF (offline, ZERO boots): "
        "0x800EE318 = EXACTLY 9 direct code xrefs, all in the EXE "
        "HUD/credit cluster 0x800472c0..0x80052820 (score_add "
        "reads ent +0xCC/+0xD0/+0xD4); the amounts 500/1000 in NO "
        "code immediate and NO EXE table (both candidates "
        "FALSIFIED); the kill-credit u16 TABLES in the overlay "
        "data head (0x8009C134 n=43, 0x8009C48C n=44, 0x8009C91C "
        "n=23; values 200..1100); the overlay TAIL (0x800AB230.., "
        "undecompiled): 207 fingerprint accesses (72 stores) + "
        "the damage dispatch enemy_800A41D8 -> 0x800ae794/"
        "0x800ae7cc.  VERDICT: the writer NARROWED (the exact "
        "store = a RUNTIME fact).  The SEVENTH rollback disclosed."),
    63: (
        "R70 THE PHASE LAW + the boot corrections (policy "
        "1.7.1->1.8.5, adapter 0.4.0->0.5.1; 5 boots): the "
        "vulnerability cycle 164f PHASE-LOCKED TO THE FREEZE "
        "(f811; the connects freeze+178+164k = f989/f1153; the "
        "scroll/knockback on the SAME clock - the boot-1 push "
        "f985 = the r69 push f1149 minus 164f); THE SPATIAL LAW: "
        "every connect at dx -133.5 EXACTLY, the phase-PERFECT "
        "-130.5 MISSED (the band [131.5,135.0]); the CORRIDOR LAW "
        "REFUTED (the f989 lob STOLEN -> the C2 guard); THE "
        "PACKING LAW (five chasers DROPPED the truck row -> the "
        "0.5.1 priority); C5 the escort classes (1,2,3,5,6); C4 "
        "the width probe (a4 300->290 = the CHIP measured).  NO "
        "kill - best a4 300->230 (the stray chips = a SECOND "
        "damage path), death f1324, score 2100; the kill math: "
        "chips + TWO centered connects reach a4 0 in-window."),
    67: (
        "R71 THE WATCHPOINT PASS (restore-only; the ledger cap "
        "2->4 by two DISCLOSED amendments - boot 3 a no-op "
        "env-var tool bug, honestly labeled).  Stage 1: the "
        "frontier rebuild BYTE-EXACT AGAIN (px 1254.8, 8-for-8).  "
        "Stage 2: the verbatim R66 pass-B tap replay with the "
        "watchpoint telemetry at the disclosed R52 seam: THE +500 "
        "CAPTURED AT THE WATCHPOINT - tap 6 verbatim (slot16, "
        "st_pre 0x1e38, dx +20.3, score 7702->8202) at flight "
        "TAIL f1 - the pay-frame law 3/3.  The +1000 cluster "
        "COMPLETE (1034 B, 200 regions) incl. the score-word "
        "0xEE318-0xEE31A; the +500 footprint: the STACK band "
        "0x1FFD00-0x1FFF00 + the ENTITY rows 0xCA6xx-0xCBDxx + "
        "the HUD 0xEE3xx-0xEF4xx.  THE PC NOT readable on beetle "
        "-> the PCSX-Redux oracle.  The replay BYTE-IDENTICAL "
        "across three boots."),
    43: (
        "R48 CORRECTED VERDICT - TWO PAY CLASSES, FRAME-EXACT "
        "(offline): (1) DEATH-INITIATION-LOCKED n=3 - the flat "
        "+100 lands EXACTLY on the 0x515c entry frame, corpse "
        "0x4BE4 follows 1-4f (taps 2/3/5; x 1284.2/1351.2/"
        "1293.2); (2) a SURVIVING-CONNECT payment n=1 - the +500 "
        "at tap-1 f_rel 2 where the ONLY event is slot-20's "
        "0x42bc hit-reaction (the slot SURVIVES; its death 23f "
        "later) - the R47 'ZERO surviving-hit payment' FALSIFIED, "
        "the R45 '+500 unresolved' RESOLVED.  Both pure models "
        "falsified: payments land at the connect/kill-"
        "registration frame, the corpse lags 1-14f; this ledger "
        "+800; the ZERO-INPUT control walk: 4 natural deaths "
        "paid 0."),
    65: (
        "R71 THE CHIP-CONNECT KILL SCHEDULE (policy 1.8.5->1.9.0 "
        "K1, adapter 0.5.1->0.5.2; 3 boots, 3/3).  K1 = the aimed "
        "cooldown chip-fire inside the corridor-cleared throw "
        "branch (the grenade keeps grid priority).  BOOT 1: 8 "
        "chips 300->220 (THE AIMED CHIP PATH CONFIRMED); the k=0 "
        "WITHHELD by the GHOST BLOCKER (slot23 0x6730 dead-walk); "
        "the k=1 lob STOLEN by the INVISIBLE THIEF STACK (x "
        "1062.3: 0xb4e4/0xabdc); death f1298/2400 = THE RECORD.  "
        "BOOT 2 (0.5.2 the a4-aware liveness filter): the k=0 "
        "FIRED and MISSED; 13 chips 300->170.  BOOT 3 (the "
        "ONE-VARIABLE arm TRUCK_CHIP_FIRE=False): the connect "
        "LANDED a4 280->180 at f1659 = freeze+506+-2f ON GRID "
        "(k=2); the k=0/k=1 ON-grid MISSED - THE PHASE LAW IS "
        "STREAM-DEPENDENT.  NO kill - best 1 connect + 5 chips, "
        "a4 160; the connect is the bottleneck (1/3 idle-hold, "
        "0/2 chip-fire)."),
    60: (
        "R68 PRODUCT - the failure-mode map + THE R67 CORRECTION "
        "(adapter 0.4.0: the dead family {0xA304,0xA44C,0xA45C} + "
        "dead_truck_x; policy 1.5.0->1.6.2): 'TRUCK KILLED 2300' "
        "REFUTED (a4=160 f1160..f1462; the score was the "
        "wave+chips).  v1.5.0 = the R67 trace BYTE-IDENTICAL; "
        "v1.6.0 the chase = 1318f/2800 THE RECORD (the lobs LAND "
        "at dx -133.5: a4 300->80); v1.6.1 the chip-stand = "
        "1218f/1400 REGRESSION (THE BULLETS DO NOT REACH a truck "
        "behind the pin); v1.6.2 tied - the CONNECT RATE is the "
        "R69 blocker."),
    30: (
        "R43 boots 6+7 (two-stage split, the cross-process "
        "savestate restore): the depth gate saved r43_postkill at "
        "c172 (px 992.0, flags 0x4B = the R41 RELEASE_SIGNATURE) "
        "- but POST-RESTART + CHECKPOINT-RESPAWN (a silent "
        "timer-expiry restart px 1150->25, the checkpoint reload "
        "to 992).  900 latch chunks, 8 deaths (continue-rescued), "
        "score 4501->13704, px to 1378 but held at the 1272 "
        "clamp; mission_end NEVER latched.  THE PRIMARY NEGATIVE: "
        "the INTERACTIVE M2 entry is NOT claimable from a "
        "post-restart posture; the clean deaths=0 resolve "
        "posture remains the requirement."),
    58: (
        "R67 the PRODUCT-PATH TRUCK CAMPAIGN (policy 1.1.0->1.4.2, "
        "adapter 0.2.0->0.3.0, 40 offline tests): T1 the truck "
        "identity = the 0x9E88 state word (the (6,h=64) identity "
        "= a FALSE-POSITIVE TRAP); the REAR fight (BACK = the "
        "legal LEFT; at the section pin the wave AND the truck "
        "are BEHIND - three identical forward-only deaths); the "
        "CADENCE law (the fire cadence is part of the wave "
        "trajectory - the 12f cadence starved the wave, the 13f "
        "rhythm reproduced the R66 record BYTE-EXACT).  ep1 2300 "
        "= the record then (the R68 correction REFUTED the "
        "truck-kill reading).  Mission 1 NOT cleared."),
}

# ---- the R73 events (the compact capsule forms) -----------------------
R73_EVENTS = [
    {
        "round": "R73",
        "status": "VERIFIED",
        "what": (
            "R73 THE CALIBRATION TABLE (offline, ZERO boots; "
            "r73_analysis.py): every committed boot throw mined "
            "per (stream, k, signed side).  THE K-OWNERSHIP "
            "LAW CONFIRMED ON BOTH SIDES: the idle-hold stream "
            "connects ONLY at k=2 (4/4 across -1f AND +1f) while "
            "k=0/k=1 NEVER (0/4 across -2f AND +0f); the volley "
            "stream connects k=0/k=1 (-1f x2, the committed R69 "
            "frames; that vintage has no live A4 events - "
            "disclosed).  THE SIDE LAW DEAD: connects at -1f AND "
            "+1f, misses at -2f, +0f AND k=3 at -1f (R73 b1) on "
            "the stream that owns k=2 - the ownership is "
            "per-window-per-stream, not per-side.  THE BLOCKED "
            "WINDOW: the r72b1 k=3 window (fight_f 638-642, phase "
            "open, 9 grenades) never threw - held f1780..1844 by "
            "T3 escort-first on a REAR escort at +37.8 (truck "
            "-133.5); a rear escort cannot eat the lob (C2 guards "
            "the descent) - a pure loss."),
        "provenance": {
            "source": "scripts/r73_analysis.py (offline, zero boots)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r73/"
                        "r73_calibration.json",
            "boots": 0,
        },
    },
    {
        "round": "R73",
        "status": "OBSERVED",
        "what": (
            "R73 PRODUCT: THE REAR-ESCORT EXEMPTION (policy 2.1.0: "
            "during the phase-open frames ONLY, a clear-line escort "
            "on the OPPOSITE side of the truck no longer holds the "
            "grid throw; same-side + off-window byte-identical "
            "v2.0.0; 10 new tests, 6 suites re-anchored 2.1.0, "
            "zero weakened).  BOOT 1 (cap 3 disclosed, 1/3 spent; "
            "the divergence disclosed f1789..1793): the r72b1 "
            "trajectory REPRODUCED BYTE-EXACT to the divergence "
            "(freeze f1151; the chips f1581/f1645; the k=2 CONNECT "
            "f1657 a4 280->180; the chip f1709) and THE EXEMPTED "
            "K=3 THROW FIRED at f1790 (the turn f1789 first) - "
            "the first ever - land f1820 = freeze+669 (-1f): MISS "
            "(a4 flat 170 to the death) -> THE OWNED SET IS "
            "EXACTLY {k=2}.  4 throws / 1 connect / 3 chips; "
            "death f1844 px 1071 score 700 - BYTE-IDENTICAL to "
            "r72b1 DESPITE the divergent inputs f1789-93: the "
            "death clock is section-locked, not wave-coupled."),
        "provenance": {
            "source": "scripts/r73_calibrated_probe.py (product boot)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r73/"
                        "r73_calibrated_probe_boot1.jsonl",
            "boots": 1,
        },
    },
    {
        "round": "R73",
        "status": "CONTRADICTED",
        "what": (
            "R73 THE DEATH RE-CLASSIFIED (the R72 'gun-duel "
            "attrition' reading SUPERSEDED): php is FLAT 198 from "
            "f1200 to the death f1844 in BOTH boots - NO "
            "attrition; ONE deterministic event at f1844 = "
            "freeze+693 (byte-exact across both boots; the death "
            "PNG: the truck parked "
            "937.5, PRESS START, no visible killer; the table "
            "f1823-1844 static - NO table-visible projectile (the "
            "rear thrower +37.8, last throw-frame f1821)).  The "
            "kill math on the idle-hold stream is CLOSED OFF "
            "(only k=2 connects; 3 needed) - THE R74 STREAM-"
            "HANDOFF KILL NAMED (next_experiment): the volley "
            "head owns k=0/k=1 (a4 300->100 by freeze+342) -> "
            "the idle-hold tail owns k=2 (freeze+506) -> a4 0 "
            "INSIDE the f1844 clock; arm 2 the death-evasion "
            "probe; arm 3 the PCSX-Redux oracle (unchanged)."),
        "provenance": {
            "source": "scripts/r73_calibrated_probe.py + "
                      "r73_analysis.py (the r69-r73 boot JSONLs)",
            "evidence": "data/games/SLUS-01212/truck_evidence/r73/"
                        "r73_calibrated_probe_boot1.jsonl",
            "boots": 1,
        },
    },
]

R74_NEXT = {
    "id": "R74",
    "budget": "the product track: ONE handoff boot (cap disclosed "
              "pre-run; boots 2-3 correction); the experiment "
              "track restore-only (r66 frontiers)",
    "hypothesis": "THE STREAM HANDOFF KILL: the ownership sets "
                  "COMPLEMENT (the volley owns k=0/k=1: "
                  "freeze+178/+342 -1f x2; the idle-hold owns k=2: "
                  "freeze+506, 4/4 across -1f/+1f) - a volley HEAD "
                  "(a4 300->100 by freeze+342) then an idle-hold "
                  "TAIL (hold px 1071; the r69b scroll shove "
                  "~f1180 is the risk) takes k=2 freeze+506 -> a4 "
                  "0 = THE KILL inside the f1844 clock "
                  "(freeze+693).  The handoff = ONE policy "
                  "variable (the cooldown stream).",
    "method": "product-path: policy 2.2.0 THE STREAM HANDOFF (the "
              "volley head = the fire-cadence cooldowns until the "
              "k=1 connect lands; then the idle-hold tail; the "
              "handoff = the measured a4 transition); arm 2 = the "
              "death-evasion probe (the f1844 dodge window, only "
              "if needed); arm 3 = the PCSX-Redux writer-PC "
              "oracle (0x8005c4b4 / the store 0x8005c508 - "
              "unchanged)",
    "m2_gate_note": "unchanged - M2 entry gated on a clean "
                    "(deaths=0, no-restart) resolve posture",
}


def main():
    cap = json.load(open(CAP))
    arc = json.load(open(ARC))
    evs = cap["events"]
    # 1. the verbatim-archived reclaim: assert before compacting
    for idx, core in RECLAIM_VERBATIM.items():
        full = arc["events"].get(str(idx), {}).get("what_full")
        assert full == evs[idx]["what"], \
            f"archive mismatch at idx{idx}; refuse to compact"
    # 2. the preserved reclaim: the pre-compact text -> the archive
    for idx, core in RECLAIM_PRESERVE.items():
        ent = arc["events"].setdefault(str(idx), {})
        ent.setdefault("round", evs[idx].get("round"))
        ent.setdefault("status", evs[idx].get("status"))
        ent.setdefault("what_full", evs[idx]["what"])
        if ent["what_full"] != evs[idx]["what"]:
            ent["what_full_capsule_v2"] = evs[idx]["what"]
        evs[idx]["what"] = core
    # 3. the verbatim reclaims in
    for idx, core in RECLAIM_VERBATIM.items():
        evs[idx]["what"] = core
    # 4. the R73 full narratives -> the archive (indices 71,72,73)
    for i, ev in enumerate(R73_EVENTS, start=71):
        arc["events"][str(i)] = {"round": ev["round"],
                                 "status": ev["status"],
                                 "what_full": ev["what"]}
    # 5. the compact R73 events -> the capsule
    evs.extend(R73_EVENTS)
    cap["next_experiment"] = R74_NEXT
    cap["meta"]["last_updated"] = "2026-11-26T00:00:00Z"
    cap["meta"]["last_commit_note"] = (
        "R73: the rear-escort exemption executed (boot 1: the k=3 "
        "throw FIRED, MISS - the owned set is {k=2}; the f1844 "
        "death clock-locked; R74 = the stream handoff)")
    # 6. the canonical compact write + the bound check
    blob = json.dumps(cap, indent=None, ensure_ascii=False,
                      separators=(",", ":"))
    size = len(blob.encode("utf-8"))
    print(f"after: {len(evs)} events, {size} B (bound {BOUND})")
    assert size < BOUND, f"capsule over the bound: {size}"
    with open(CAP, "w") as f:
        f.write(blob)
    with open(ARC, "w") as f:
        json.dump(arc, f, indent=1)
    # the round-trip check
    cap2 = json.load(open(CAP))
    assert len(cap2["events"]) == 74
    assert cap2["next_experiment"]["id"] == "R74"
    arc2 = json.load(open(ARC))
    assert arc2["events"]["73"]["status"] == "CONTRADICTED"
    assert "what_full_capsule_v2" in arc2["events"]["61"]
    print("round-trip OK; archive events:", len(arc2["events"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
