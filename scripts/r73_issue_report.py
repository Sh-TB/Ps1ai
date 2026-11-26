#!/usr/bin/env python3
"""r73_issue_report.py — post the evidence-grade R73 round report to
issue #9 (the R67-R72 precedent), read back byte-identical."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY = """**R73 round report (the capsule lever executed: the calibration table + the rear-escort exemption + the death re-classified) — badges: IMPLEMENTED / TESTED / OBSERVED / VERIFIED.** Evidence: `truck_evidence/r73/` (the calibration JSON · 1 product boot, the ledger disclosed below · the boot JSONL + the PNGs) · policy `2.0.0 -> 2.1.0` · push [`bc970af`](https://github.com/Sh-TB/Ps1ai/commit/bc970af05e65) · suite **972 passed + 10 skipped + 1 xfailed** (zero weakened).

**The product ledger (cap 3 disclosed pre-run, 1/3 spent, 2 HELD):** boot 1 = the shipped v2.1.0 exemption (NO module patching — the exemption IS the shipped default). The lever's question was answered by boot 1; no correction boot was spent. Read-only product-loop probe: legal inputs only, zero RAM writes, no training, no runtime LLM.

## The offline track — THE CALIBRATION TABLE (ZERO boots)

`scripts/r73_analysis.py` mines every committed product-boot grenade throw per **(stream, k, signed land offset) → outcome** (`truck_evidence/r73/r73_calibration.json`):

- **THE K-OWNERSHIP LAW CONFIRMED ON BOTH SIDES:** the idle-hold stream connects ONLY at **k=2 — 4/4 across BOTH side buckets** (−1f ×2: R72/R73 boots; +1f ×1: the R71 boot-3) — while **k=0/k=1 NEVER connect: 0/4 across BOTH sides** (−2f ×2 + 0f ×2). The volley stream owns k=0/k=1 (−1f ×2, the committed R69 frames f989/f1153; that probe vintage logs no live A4 events — applied from the committed round analysis, provenance disclosed per throw).
- **THE SIDE LAW DEAD:** connects occur at −1f AND +1f; misses at −2f, 0f AND **k=3 at −1f (this round's boot)** on the same stream that owns k=2. The ownership is **per-window-per-stream**, not per-side.
- **THE BLOCKED WINDOW:** the R72 boot-1 death-frame audit — the k=3 grid window (fight_f 638-642, phase open, 9 grenades live) NEVER threw: every frame f1780..f1844 was held by the T3 escort-first cadence on a **REAR escort at dx +37.8** (the truck at −133.5). A rear escort cannot eat the lob (the C2 corridor predicate already guards the descent line — a lob toward −133.5 never passes x>0): a pure loss of the owned window.

## The product track — THE REAR-ESCORT EXEMPTION (policy 2.1.0)

During the PHASE-OPEN frames ONLY, a clear-line escort on the OPPOSITE side of the truck no longer holds the grid throw. Same-side escorts keep FULL precedence (the D7/R49 law); the off-window frames stay byte-identical v2.0.0 (the stream law — the R67 cadence-law precedent). 10 new offline tests (incl. the exact R72b1 f1789 reproduction); the R66/R69/R70/R71/R72 suites re-anchored 2.0.0→2.1.0 with the evidence noted in-test — zero weakened.

**BOOT 1:** the R72b1 trajectory **REPRODUCED BYTE-EXACT to the disclosed divergence** (freeze f1151; the chips f1581/f1645; the **k=2 CONNECT f1657 a4 280→180**; the chip f1709) — and **THE EXEMPTED K=3 THROW FIRED at f1790** (the turn frame f1789 first: the rear-fire state faced R) — **the first k=3 throw ever** — land f1820 = freeze+669 (−1f): **MISS** (a4 flat 170 through the death). **THE OWNED SET ON THE IDLE-HOLD STREAM IS EXACTLY {k=2}.** 4 throws / 1 connect / 3 chips; death f1844 px 1071.0 score 700 — **BYTE-IDENTICAL to R72b1 (frame, score, posture) DESPITE the divergent inputs f1789-93** — an input divergence 55f before the death did not move it.

## THE DEATH RE-CLASSIFIED — the R72 "gun-duel attrition" reading SUPERSEDED

php is **FLAT 198 from f1200 to f1844 in BOTH boots** — NO attrition. The death is **ONE deterministic event at f1844 = freeze+693**, clock-locked to the section: byte-exact across two boots with divergent inputs; the death PNG (the truck parked at 937.5, **PRESS START**, no visible killer); the entity table f1823-1844 static — **NO table-visible projectile**; the rear thrower at +37.8 cycles its throw animation (last throw-frame f1821). The direct killer needs the watchpoint oracle; what IS proven: it is scripted-time, not health-driven.

## R74 NAMED — THE STREAM HANDOFF KILL

The two ownership sets **COMPLEMENT**: the volley stream owns k=0/k=1 (a4 300→100 by freeze+342 — the proven −1f connects) and the idle-hold stream owns k=2 (freeze+506, 4/4). A **volley HEAD → idle-hold TAIL** handoff (ONE policy variable — the cooldown stream, switched on the measured a4 transition; the r69b scroll shove at ~f1180 is the risk window) takes the k=2 land to **a4 0 = THE TRUCK KILL INSIDE the f1844 death clock**. Arm 2: the death-evasion probe (the f1844 dodge window). Arm 3 (unchanged): the PCSX-Redux writer-PC oracle (the accumulator 0x8005c4b4 / the store 0x8005c508).

The capsule: +3 R73 events (74 total) with provenance + the final-mile RECLAIM (the R72/R71/R70/R69/R48/R43/R67 cores compacted; the pre-compact texts preserved in `event_narratives_archive.json` under `what_full` / `what_full_capsule_v2` — lossless, 74 entries; the canonical compact JSON **65,520 B < the 64 KiB bound**). Mission 1 stays OPEN."""

s, d = req(f"/repos/{REPO}/issues/9/comments", method="POST",
           payload={"body": BODY})
assert s == 201, d
cid = d["id"]
s2, d2 = req(f"/repos/{REPO}/issues/comments/{cid}")
assert s2 == 200 and d2["body"] == BODY
print("posted + read back byte-identical:", cid)
