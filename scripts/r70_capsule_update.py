#!/usr/bin/env python3
"""r70_capsule_update.py — append the R70 events to the MSX capsule.

The R70 round (the capsule lever continued: the product-path truck
campaign, the phase law).  THREE consolidated events with provenance,
each read back verbatim after the write (the R37+ discipline).  The
next_experiment moves to R71.
"""
import json
import os
import sys

REPO = "/home/z/my-project/ps1ai"
CAP = os.path.join(REPO, "data", "knowledge", "msx", "capsule.json")

EVENTS = [
    {
        "what": (
            "R70 THE PHASE LAW + the four boot corrections (policy "
            "1.7.1 -> 1.8.5, adapter 0.4.0 -> 0.5.1; five product "
            "boots, the r70 ledger disclosed in the round report).  "
            "THE LAW (from the r69b + the r70 boots): (1) the "
            "vulnerability cycle is 164f, PHASE-LOCKED TO THE FREEZE "
            "frame (the first 0x9E88 sighting, f811 on every record "
            "timeline) — the connects land at freeze+178+164k "
            "(f989/f1153) and the scroll/knockback events sit on the "
            "SAME clock (the r70 boot-1 push at f985 = the r69 push "
            "at f1149 minus exactly 164f — the independent second "
            "confirmation); (2) THE SPATIAL LAW: every observed "
            "connect sits at dx -133.5 EXACTLY (the R68 record + the "
            "r69b pair) while the phase-PERFECT dx -130.5 throw (the "
            "r70 boot-4 k=1 at fight_f 312, corridor clean) MISSED "
            "and the v1.7.0 -136.5/-139.5 missed — the connect "
            "geometry is ~+-3px TIGHT around -133.5 (the quantized "
            "postures -130.5/-133.5/-135.4; the throw band [131.5, "
            "135.0] admits only the proven center); (3) THE CORRIDOR "
            "LAW: 'the arc clears the ground blockers' is REFUTED — "
            "the boot-1 f989 lob was STOLEN mid-descent by an "
            "interloper at dx ~-119 (the R49 steal model extended to "
            "lobs) and the boot-4 k=0 window was correctly withheld "
            "by the corridor guard (the walkers at -61/-70/-73); "
            "(4) THE PACKING LAW: five chasers nearer than the "
            "parked truck DROPPED the truck row from the nearest-5 "
            "observation (the boot-3 f909..f958), the W8 window read "
            "a confirmed drive-off, the fight clock re-anchored and "
            "the grid throw was spent 248f late.  THE SHIPPED FIXES: "
            "C2 the corridor guard (the lob requires clear_line), C3 "
            "the drive-in hygiene (any escort 8..220 either side), "
            "C5 the escort classes (1,2,3,5,6 — the sc=6 walk-state "
            "chasers were INVISIBLE to the SOLDIER_CODES escort "
            "rules and filled the corridor), the adapter 0.5.1 "
            "truck-packing priority (the truck-family row displaces "
            "the farthest packed row — the anchor never drops), C4 "
            "the one-shot width probe (FIRED at f823, landed f855: "
            "a4 300 -> 290 = the CHIP payment -10 a4/+100 score — "
            "the wrong-phase partial hit measured).  THE ROUND "
            "OUTCOME (honest): NO truck kill — the best boot ran a4 "
            "300 -> 230 (the escort-fire stray bullets chip -10/"
            "+100 at ~26f cadence — a SECOND damage path measured), "
            "death f1324 = +6 past the record f1318, score 2100 = "
            "+400 over the record 1700; the boot-5 regression (the "
            "re-center walk withdrawn: a -33px truck-gun knockback "
            "pinned the player at px 1038 for 126f — the scroll "
            "cancels the walk, the gun line killed at f1076).  THE "
            "KILL MATH for R71: the chips (-10 each) + TWO centered "
            "connects (-100 each) reach a4 0 inside the window — "
            "the kill does NOT need three phase-connects.  "
            "Zero-overlap re-run NOT triggered (no new +500: the "
            "probe paid a +100 chip).  Evidence: truck_evidence/r70/"
            "r70_phase_probe.jsonl (5 boots, the last shipped)."
        ),
        "status": "VERIFIED",
        "round": "R70",
        "provenance": {
            "source": (
                "scripts/r70_phase_probe.py + the policy "
                "1.8.0->1.8.5 + the adapter 0.5.0->0.5.1"),
            "evidence": (
                "data/games/SLUS-01212/truck_evidence/r70/"
                "r70_phase_probe.jsonl"),
            "boots": 5,
        },
    },
    {
        "what": (
            "R70 the driver semantics consolidated: (1) the FREEZE "
            "anchor: the truck runs st 0x9C14 (f733..f808, x 842.5 -> "
            "937.5 at +1.25 px/f, the armor a4 ALREADY 300 during the "
            "drive-in) then 0x9E08 (2f) then 0x9E88 — the adapter "
            "0.5.0 maps the drive-in family to SC_TRUCK_IN = 8 (no "
            "soldier state collides); (2) the FLIGHT is EXACTLY 30f "
            "(the r69b f959->f989, f1123->f1153; re-confirmed); "
            "(3) the k=0 lead window (land freeze+14 = f825) is "
            "UNREACHABLE from the drive-in walk (the truck enters "
            "the scan only ~f759 via the sx band, the walk needs "
            "~51f, the posture arrives ~f815-840 — 20-45f late) — "
            "the lead arm stands down honestly, the C4 width probe "
            "is the replacement measurement; (4) the escort-fire "
            "stray-bullet chips are a REAL second damage path (-10 "
            "a4 + +100 score each, ~26f cadence under the walker "
            "feed) — the R68 'a4 300 -> 80' record reading is "
            "reinterpreted: the chips, not the connects, drove most "
            "of it; (5) the knockback hazard: the truck-gun hits "
            "shove the player up to -33px (px 1071 -> 1038) and the "
            "scroll cancels the recovery walk — the posture is "
            "LOSED once knocked below ~-115; the v1.8.5 policy "
            "HOLDS below the throw band instead of walking."
        ),
        "status": "OBSERVED",
        "round": "R70",
        "provenance": {
            "source": (
                "the r70 boot traces (the 5-boot ledger) + the "
                "r69b connect probe"),
            "evidence": (
                "data/games/SLUS-01212/truck_evidence/r70/"
                "r70_phase_probe.jsonl + truck_evidence/r69/"
                "r69b_connect_probe.jsonl"),
            "boots": 5,
        },
    },
    {
        "what": (
            "R70 the SUITE: 903 passed + 10 skipped + 1 xfailed "
            "(the MSX policy/adapter set 111 green: the phase gate, "
            "the grid one-throw-per-k, the clock anchor/flicker "
            "freeze, the drive-in arm, the C2 corridor guard, the "
            "C3/C5 escort classes, the C4 width probe, the v0.5.1 "
            "packing priority, the v1.8.4 spatial band, the v1.8.5 "
            "hold-below-band; the R66-R69 truck tests re-anchored "
            "on the committed rules, zero weakened).  The 8 failed "
            "+ 11 errors in test_r61/r62/r64 are the PRE-EXISTING "
            "flappybird ONNX environment regressions of THIS "
            "sandbox (verified on the clean tree before the R70 "
            "changes; the R61 post-recycle precedent) — NOT the "
            "R70 footprint.  Legal inputs only, zero RAM writes, "
            "no training, no runtime LLM; m2_gate unchanged."
        ),
        "status": "TESTED",
        "round": "R70",
        "provenance": {
            "source": "tests/test_r70_msx_phase_law.py + the updated "
                      "R66/R69 sets",
            "evidence": "the pytest run (the round report)",
        },
    },
]

NEXT = {
    "id": "R71",
    "budget": (
        "product boots + probes are the separate gameplay track; "
        "the experiment track stays restore-only arms from the r66 "
        "frontiers (the R68 rebuild is byte-exact)"),
    "hypothesis": (
        "two evidence-armed leads: (1) PRODUCT - the CHIP-CONNECT "
        "kill schedule: the escort-fire stray bullets chip -10/+100 "
        "at ~26f under the walker feed AND a centered connect pays "
        "-100 — a4 300 reaches 0 inside the scroll-capped window "
        "with TWO centered connects + the chips; the boot-4 best "
        "was a4 230 with ONE miss — the v1.8.5 spatial band "
        "[131.5,135.0] + the phase grid now spend the throws ONLY "
        "at the proven -133.5 center; (2) the corridor-feed "
        "management: the walker spawn zone (~1100-1150) sits "
        "UPSTREAM of the record posture (1071) — map the feed "
        "(time- vs position-triggered) and hold the fire cadence "
        "so the corridor is clean AT each grid window; "
        "(3) SOURCE-FIRST - one restore-only watchpoint pass on "
        "0x800EE318 to log the payment-writer PC (the R69 xref: "
        "the overlay damage tail + the credit tables "
        "0x8009C134/0x8009C48C/0x8009C91C); needs the frontier "
        "rebuild (the disclosed contingency)"),
    "method": (
        "product-path: play metal_slug_x with the v1.8.5 policy "
        "(the phase grid + the spatial band + the corridor guard + "
        "the hygiene); experiment-track: the watchpoint pass only "
        "if the frontier rebuild is spent (the R66 gate verbatim); "
        "the zero-overlap test re-runs on any new +500 capture"),
    "m2_gate_note": (
        "unchanged - interactive M2 entry stays gated on a clean "
        "(deaths=0, no-restart) deep resolve posture"),
}


def main():
    with open(CAP) as f:
        cap = json.load(f)
    before = len(cap["events"])
    cap["events"].extend(EVENTS)
    cap["next_experiment"] = NEXT
    meta = cap.setdefault("meta", {})
    meta["last_updated"] = \
        __import__("time").strftime("%FT%TZ",
                                    __import__("time").gmtime())
    meta["last_commit_note"] = (
        "R70: the PHASE LAW confirmed (the 164f cycle phase-locked "
        "to the freeze; the scroll on the same clock — the second "
        "confirmation), the SPATIAL LAW discovered (the connects "
        "ONLY at dx -133.5; the -130.5 phase-perfect throw missed), "
        "the corridor law (the lobs stolen; the C2 guard), the "
        "packing law (the adapter 0.5.1 truck priority), the C5 "
        "escort classes (the sc=6 chasers), the C4 width probe "
        "fired (the chip -10/+100 measured), the chips = the "
        "second damage path; NO kill (the best a4 230, the score "
        "2100 = +400 over the record); the R71 = the chip-connect "
        "kill schedule + the corridor-feed map.  Mission 1 OPEN.")
    with open(CAP, "w") as f:
        json.dump(cap, f, indent=1, ensure_ascii=False)
    # read back verbatim
    with open(CAP) as f:
        back = json.load(f)
    assert len(back["events"]) == before + len(EVENTS), \
        "event count mismatch"
    for i, e in enumerate(EVENTS):
        assert back["events"][before + i] == e, f"event {i} mismatch"
    assert back["next_experiment"] == NEXT
    print(f"capsule updated: +{len(EVENTS)} events "
          f"({before} -> {len(back['events'])}), "
          f"next_experiment={NEXT['id']}, "
          f"bytes={os.path.getsize(CAP)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
