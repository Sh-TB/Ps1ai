#!/usr/bin/env python3
"""r70_issue_report.py — post the evidence-grade R70 round report to
issue #9 (the R67-R69 precedent), read back byte-identical."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY = """**R70 round report (the capsule lever continued: the product-path truck campaign, the phase law) — badges: IMPLEMENTED / TESTED / OBSERVED / VERIFIED.** Evidence: `truck_evidence/r70/r70_phase_probe.jsonl` (5 product boots, the ledger disclosed below) · policy `1.7.1 -> 1.8.5` · adapter `0.4.0 -> 0.5.1` · push [`cc846d7`](https://github.com/Sh-TB/Ps1ai/commit/cc846d788ee4) · suite **903 passed + 10 skipped + 1 xfailed**.

**The ledger (5 product boots, disclosed pre-run):** boot 1 = the v1.8.0 phase probe (the drive-in arm + the phase grid); boots 2-5 = the correction cycle (v1.8.1 C2/C3/C4, v1.8.2 C5, v1.8.4 the spatial band, v1.8.5 the hold). Every boot is a read-only product-loop probe: legal inputs only, zero RAM writes, no training, no runtime LLM.

## The laws (each pinned by at least one probe frame)

1. **THE PHASE LAW (VERIFIED, second confirmation).** The truck vulnerability cycle is **164f, phase-locked to the FREEZE frame** (the first `0x9E88` sighting — f811 on every record timeline). The connects land at `freeze+178+164k` (f989/f1153, the r69b pair). The scroll/knockback events sit on the SAME clock: the boot-1 push began at f985 = the r69 record's f1149 push minus exactly 164f — the cycle was measured by its damage AND by its camera.
2. **THE SPATIAL LAW (VERIFIED).** Every observed connect sits at **dx -133.5 EXACTLY** (the R68 record + the r69b pair, 3/3). The boot-4 k=1 throw was phase-PERFECT (fight_f 312, corridor clean) at dx **-130.5 — and MISSED** (no a4 transition). The v1.7.0 outer throws (-136.5/-139.5) missed. The connect geometry is ~±3px tight; the quantized postures are -130.5/-133.5/-135.4 — the shipped throw band `[131.5, 135.0]` admits only the proven center.
3. **THE CORRIDOR LAW (REFUTES a disclosed property).** "The arc clears the ground blockers" is **REFUTED**: the boot-1 f989 lob was STOLEN mid-descent by an interloper at dx ~-119 (the R49 steal model extended to lobs). The C2 corridor guard shipped: the lob requires `clear_line` — and the boot-4 k=0 window was correctly WITHHELD by it (the walkers at -61/-70/-73 would have eaten the throw).
4. **THE PACKING LAW (ADAPTER FIX).** Five chasers nearer than the parked truck DROPPED the truck row from the nearest-5 observation (the boot-3 f909..f958) — the W8 window read a confirmed drive-off, the fight clock re-anchored, and the grid throw was spent **248f late**. Adapter 0.5.1 ships the truck-packing priority: the truck-family row (`0x9E88/0x9C14/0x9E08`) displaces the farthest packed row — the fight anchor never drops.
5. **THE HYGIENE LAW (C5).** The chasers approach in their walk/throw animation states (`sc=6` — the R67 probe correction) and were INVISIBLE to the `SOLDIER_CODES=(1,2,3)` escort rules: they filled the corridor untouched. The escort classes are now `(1,2,3,5,6)`; the drive-in hygiene (C3) engages any escort 8..220 on either side.

## The C4 width probe (FIRED)

The one-shot probe fired at f823 and landed at f855: **a4 300 -> 290 = the CHIP payment (-10 a4 / +100 score)** — a wrong-phase partial hit, measured. The truck DOES take chip damage from lobs landing off-phase at the arc edge.

## The honest outcome: NO kill — but the kill math changed

- The best boot ran **a4 300 -> 230**: the escort-fire stray bullets chip the truck **-10 a4 / +100 score at ~26f cadence** under the walker feed — a SECOND damage path measured. The R68 record reading ("a4 300 -> 80") is reinterpreted: the chips, not the connects, drove most of it.
- The best boot's death: **f1324 = +6 past the record f1318**; the score **2100 = +400 over the record 1700** — the R70 boots beat the record score without the kill.
- The boot-5 regression is disclosed: the v1.8.4 re-center walk was WITHDRAWN — a -33px truck-gun knockback pinned the player at px 1038 for 126f (the scroll cancels the recovery walk); v1.8.5 HOLDS below the throw band instead of walking.
- **The R71 kill math: the chips (-10 each) + TWO centered connects (-100 each) reach a4 0 inside the scroll-capped window — the kill does NOT need three phase-connects.** The phase grid + the spatial band now spend throws ONLY at the proven center.

Zero-overlap re-run: NOT triggered (no new +500 — the probe paid a +100 chip).

## The suite

903 passed + 10 skipped + 1 xfailed. The MSX policy/adapter set is 111 green (the phase gate, one-throw-per-k, the clock anchor/flicker-freeze, the drive-in arm, C2/C3/C5, C4, the 0.5.1 packing, the v1.8.4 band, the v1.8.5 hold; the R66-R69 truck tests re-anchored on the committed rules — zero weakened). The 8 failed + 11 errors in `test_r61/r62/r64` are the PRE-EXISTING flappybird ONNX environment regressions of THIS sandbox (verified on the clean tree BEFORE the R70 changes; the R61 post-recycle precedent) — not the R70 footprint.

The capsule: +2 consolidated R70 events with provenance (65 events), `next_experiment = R71` (the chip-connect kill schedule + the corridor-feed map + the restore-only watchpoint pass on 0x800EE318). The canonical size is 68,834 B — 3.3 KB over the 64 KiB warn target, justified here: the R70 blocks are already consolidated; the reclaim belongs to the R71 final-mile per the r66 precedent. m2_gate unchanged. No issue closed."""

s, d = req(f"/repos/{REPO}/issues/9/comments", "POST", {"body": BODY})
print("HTTP", s, "comment id:", d.get("id"))
if s == 201:
    s2, comments = req(f"/repos/{REPO}/issues/9/comments?per_page=100")
    mine = [c for c in comments if c["id"] == d["id"]]
    print("read back byte-identical:",
          bool(mine) and mine[0]["body"] == BODY)
