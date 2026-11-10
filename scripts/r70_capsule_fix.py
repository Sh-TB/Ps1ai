#!/usr/bin/env python3
"""r70_capsule_fix.py — repair the R70 capsule write: the schema status
('TESTED' is not in the allowed enum — the r66 final-mile precedent),
the compact separators (the HEAD format), and the size discipline (the
64 KiB warn cap: the R70 additions consolidated to the minimum that
keeps every number, address, status and evidence pointer).

Read back verbatim after the write.  Git history keeps the prior bytes.
"""
import json
import os
import sys
import time

REPO = "/home/z/my-project/ps1ai"
CAP = os.path.join(REPO, "data", "knowledge", "msx", "capsule.json")

R70_A = (
    "R70 THE PHASE LAW + the four boot corrections (policy "
    "1.7.1->1.8.5, adapter 0.4.0->0.5.1; 5 product boots, the ledger "
    "in the round report).  LAWS: (1) the vulnerability cycle 164f "
    "PHASE-LOCKED TO THE FREEZE (the first 0x9E88 sighting, f811 on "
    "every record timeline; the connects at freeze+178+164k = "
    "f989/f1153) — the scroll/knockback events sit on the SAME clock "
    "(the boot-1 push f985 = the r69 push f1149 minus 164f: the "
    "second confirmation); (2) THE SPATIAL LAW: every connect at dx "
    "-133.5 EXACTLY (the R68 record + the r69b pair), the "
    "phase-PERFECT dx -130.5 throw (the boot-4 k=1, fight_f 312, "
    "corridor clean) MISSED, the v1.7.0 -136.5/-139.5 missed — the "
    "geometry ~+-3px tight (the quantized postures "
    "-130.5/-133.5/-135.4; the throw band [131.5,135.0] admits only "
    "the proven center); (3) THE CORRIDOR LAW: 'the arc clears the "
    "blockers' REFUTED — the boot-1 f989 lob STOLEN mid-descent by "
    "an interloper at dx ~-119 (the R49 model extended to lobs); "
    "(4) THE PACKING LAW: 5 chasers nearer than the truck DROPPED "
    "the truck row (the boot-3 f909..f958), W8 read a drive-off, "
    "the clock re-anchored, the grid throw spent 248f late.  FIXES "
    "SHIPPED: C2 the corridor guard (the lob requires clear_line); "
    "C3 the drive-in hygiene (any escort 8..220 either side); C5 "
    "the escort classes (1,2,3,5,6 — the sc=6 walk-state chasers "
    "were invisible to SOLDIER_CODES and filled the corridor); the "
    "adapter 0.5.1 truck-packing priority (the truck row displaces "
    "the farthest packed); C4 the one-shot width probe (fired f823, "
    "landed f855: a4 300->290 = the CHIP -10 a4/+100 score).  "
    "OUTCOME (honest): NO kill — the best boot a4 300->230 (the "
    "escort stray bullets chip -10/+100 at ~26f: a SECOND damage "
    "path; the R68 'a4 300->80' reading reinterpreted as the "
    "chips), death f1324 = +6 past the record f1318, score 2100 = "
    "+400 over the record 1700; the boot-5 re-center walk "
    "WITHDRAWN (a -33px truck-gun knockback pinned px 1038 for "
    "126f — the scroll cancels the walk; v1.8.5 HOLDS below the "
    "throw band).  R71 kill math: the chips + TWO centered "
    "connects reach a4 0 in-window.  No new +500 (the probe paid a "
    "+100 chip) — the zero-overlap re-run NOT triggered.  "
    "Evidence: truck_evidence/r70/r70_phase_probe.jsonl."
)
R70_B = (
    "R70 the driver semantics + the suite: (1) the drive-in: st "
    "0x9C14 (f733..f808, x 842.5->937.5 at +1.25 px/f, the armor a4 "
    "ALREADY 300) then 0x9E08 (2f) then 0x9E88 — the adapter 0.5.0 "
    "maps the family to SC_TRUCK_IN = 8 (no soldier collision); "
    "(2) the flight EXACTLY 30f (the r69b pair, re-confirmed); (3) "
    "the k=0 lead window (land freeze+14 = f825) UNREACHABLE from "
    "the drive-in walk (the sx band admits the truck ~f759; the "
    "walk needs ~51f; the posture arrives ~f815-840, 20-45f late) "
    "— the lead stands down, the C4 probe is the replacement "
    "measurement; (4) the knockback hazard: the truck-gun hits "
    "shove up to -33px (px 1071->1038) and the scroll cancels the "
    "recovery walk — the posture is LOST below ~dx -115.  SUITE: "
    "903 passed + 10 skipped + 1 xfailed (the MSX set 111 green: "
    "the phase gate, one-throw-per-k, the clock "
    "anchor/flicker-freeze, the drive-in arm, C2/C3/C5, C4, the "
    "v0.5.1 packing, the v1.8.4 band, the v1.8.5 hold; the "
    "R66-R69 truck tests re-anchored, zero weakened).  The 8 "
    "failed + 11 errors in test_r61/r62/r64 = the PRE-EXISTING "
    "flappybird ONNX env regressions of THIS sandbox (verified on "
    "the clean tree; the R61 post-recycle precedent) — not the "
    "R70 footprint.  Legal inputs only, zero RAM writes, no "
    "training, no runtime LLM; m2_gate unchanged."
)

NEXT = {
    "id": "R71",
    "budget": (
        "product boots + probes are the separate gameplay track; "
        "the experiment track stays restore-only arms from the r66 "
        "frontiers (the R68 rebuild is byte-exact)"),
    "hypothesis": (
        "the CHIP-CONNECT kill schedule: the escort stray bullets "
        "chip -10/+100 at ~26f under the walker feed AND a centered "
        "connect pays -100 — a4 300 reaches 0 in-window with TWO "
        "centered connects + the chips (the boot-4 best was a4 230 "
        "with one miss); the v1.8.5 spatial band [131.5,135.0] + "
        "the phase grid spend throws ONLY at the proven -133.5 "
        "center; map the corridor feed (the walker spawn zone "
        "~1100-1150 sits UPSTREAM of the posture 1071 — time- vs "
        "position-triggered) and hold the fire cadence so the "
        "corridor is clean AT each grid window; SOURCE-FIRST: one "
        "restore-only watchpoint pass on 0x800EE318 to log the "
        "payment-writer PC (the R69 xref: the overlay damage tail "
        "+ the credit tables 0x8009C134/0x8009C48C/0x8009C91C); "
        "needs the frontier rebuild (the disclosed contingency)"),
    "method": (
        "product-path: play metal_slug_x with the v1.8.5 policy "
        "(the phase grid + the spatial band + the corridor guard + "
        "the hygiene); the watchpoint pass only if the frontier "
        "rebuild is spent (the R66 gate verbatim); the zero-overlap "
        "test re-runs on any new +500 capture"),
    "m2_gate_note": (
        "unchanged - interactive M2 entry stays gated on a clean "
        "(deaths=0, no-restart) deep resolve posture"),
}

META_NOTE = (
    "R70: the PHASE LAW confirmed (the 164f cycle locked to the "
    "freeze; the scroll on the same clock), the SPATIAL LAW (the "
    "connects only at dx -133.5; -130.5 missed), the corridor law "
    "(the lobs stolen; C2), the packing law (the adapter 0.5.1 "
    "truck priority), C5 the escort classes, C4 the width probe "
    "fired (the chip -10/+100), the chips = the second damage "
    "path; NO kill (the best a4 230, the score 2100 = +400 over "
    "the record); the R71 = the chip-connect kill schedule + the "
    "corridor-feed map.  Mission 1 OPEN."
)


def main():
    with open(CAP) as f:
        cap = json.load(f)
    evs = cap["events"]
    # drop the malformed R70 write (the indent-format events 63-65)
    evs = [e for e in evs if e.get("round") != "R70"]
    evs.append({"what": R70_A, "status": "VERIFIED", "round": "R70",
                "provenance": {
                    "source": "scripts/r70_phase_probe.py + the "
                              "policy 1.8.0->1.8.5 + the adapter "
                              "0.5.0->0.5.1",
                    "evidence": "data/games/SLUS-01212/"
                                "truck_evidence/r70/"
                                "r70_phase_probe.jsonl",
                    "boots": 5}})
    evs.append({"what": R70_B, "status": "OBSERVED", "round": "R70",
                "provenance": {
                    "source": "the r70 boot traces + the r69b probe "
                              "+ the pytest run",
                    "evidence": "truck_evidence/r70/"
                                "r70_phase_probe.jsonl"}})
    cap["events"] = evs
    cap["next_experiment"] = NEXT
    cap.setdefault("meta", {})
    cap["meta"]["last_updated"] = \
        time.strftime("%FT%TZ", time.gmtime())
    cap["meta"]["last_commit_note"] = META_NOTE
    # the COMPACT format (the HEAD discipline)
    out = json.dumps(cap, ensure_ascii=False,
                     separators=(",", ":"))
    size = len(out.encode("utf-8"))
    with open(CAP, "w") as f:
        f.write(out)
    # read back verbatim
    back = json.load(open(CAP))
    assert [e for e in back["events"]
            if e.get("round") == "R70"][-1]["what"] == R70_B
    assert back["next_experiment"]["id"] == "R71"
    print(f"capsule fixed: {len(back['events'])} events, "
          f"size={size} B (warn cap 65536) "
          f"{'OK' if size <= 65536 else 'OVER'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
