#!/usr/bin/env python3
"""r72_issue_report.py — post the evidence-grade R72 round report to
issue #9 (the R67-R71 precedent), read back byte-identical."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY = """**R72 round report (the capsule lever executed: the volley+phase hybrid + the payment-cluster xref) — badges: IMPLEMENTED / TESTED / OBSERVED / VERIFIED.** Evidence: `truck_evidence/r72/` (1 product boot, the ledger disclosed below · the xref JSON/MD · the corridor map) · policy `1.9.0 -> 2.0.0` · push [`2833cf7`](https://github.com/Sh-TB/Ps1ai/commit/2833cf78553a) · suite **962 passed + 10 skipped + 1 xfailed** (the onnxruntime install cleared the pre-existing flappy env regressions of the fresh sandbox — zero weakened).

**The product ledger (cap 3 disclosed pre-run, 1/3 spent, 2 HELD):** boot 1 = the shipped v2.0.0 hybrid (NO module patching — the re-selection IS the shipped default). The lever's product question was answered by boot 1; no correction boot was spent. Read-only product-loop probe: legal inputs only, zero RAM writes, no training, no runtime LLM.

## The experiment track — THE PAYMENT WRITER PINPOINTED (offline, ZERO boots)

`scripts/r72_cluster_xref.py`: the capstone full-text decode (155,136 EXE + 28,850 overlay insns, shas verified) with a symbolic lui/addiu base tracker + per-site clean-window verification + the committed call graph:

- **THE PAYMENT WRITER = `0x8005c508: sw $a1, -0x1ce8($a2)` -> 0x800EE318**, inside the score accumulator at `0x8005c4b4` (frame 40 B). The chain, instruction by instruction: `lw $a2,($a1)` (the score-base HANDLE — pointer-mediated) -> `jal 0x8007e8b4` (format) -> `jal 0x8007e7d4` (parse) -> `$a3 = the numeric delta` -> `andi $v0,$s0,1` (the P1 bit) -> `lw $v1,-0x1ce8($a2)` (read) -> `addu $a1,$v1,$a3` (score += delta) -> `slt` vs **0x5f5e0ff (the 99,999,999 cap)** -> `sw` (THE STORE) -> the %100 display twin (`0x51eb851f`). The P2 bit writes **0x800EE320**. The clear twin `0x8005c734 sw $zero` (in `0x8005c6d4`) is called from the game-reset cluster (4 jal sites).
- **THE R69 FALSIFICATION EXPLAINED:** the amounts 500/1000 appear in NO code immediate because the credit amount arrives **FORMATTED** — the delta passes through the format->parse chain (the overlay kill-credit tables 0x8009C134/0x8009C48C/0x8009C91C upstream).
- **THE CENSUS:** exactly **3 score-word stores in the whole EXE** (the two accumulator stores + the clear) and **0 in the overlay**; 178 HUD-band store sites (the confirmed set verified on clean lui chains; the unverified candidates disclosed separately).
- **THE BOUNDS (disclosed):** the accumulator has NO direct jal xref — the dispatch is pointer-mediated (statically invisible); the runtime PC confirmation belongs to the PCSX-Redux CPU oracle (the R64 tools-matrix item). The stack-band churn = the accumulator's own 40 B frame (fits the churned top band at depth <= 2 — the R71 stack evidence explained). The entity-row churn slots: +1000 {0,3,4,6,7,12,16,18,20,21,24,28,30}, +500 {3,16,18} — slot 16 the capture slot, slot 12 the R66 registration witness.

## The product track — THE VOLLEY+PHASE HYBRID (policy 2.0.0)

Two evidence-armed changes: **TRUCK_CHIP_FIRE default re-selected to False** (the R71 boot-3 one-variable evidence: the idle-hold stream connects, the chip-fire stream does not; the K1 arm stays patchable as the chip supplement AFTER the connect mechanism is solved) and **the phase gate widened to the FULL ±2f of ANY grid point** (both sides — v1.9.0 admitted only the 0..2f-after side). 19 new offline tests; the R69/R70/R71 suites re-anchored with the K1-arm patch preserved (zero weakened).

**BOOT 1:** the freeze f1151 (px 1089; the drive-in VERIFIED `0x9C14` f1073 x 842.5 -> `0x9E08` f1149 -> `0x9E88` f1151 — **NO anchor alias**). The hybrid threw **ON GRID at the PRE-SIDE frames** (fight_f 146/310/475 = the lands freeze+176/340/505 — the v1.9.0 gate could NEVER throw those frames) and **THE CONNECT LANDED: a4 280 -> 180 at f1657 = freeze + 506 EXACT** (the land 1656 = freeze+505, the −1f side; the register frame ON the grid) — **THE PRE-SIDE VALIDITY CONFIRMED at k=2**. The k=0/k=1 lands MISSED on a CLEAN corridor; 3 chips (300 -> 170 at the death); the death f1844 AT the posture px 1071 (php 198, gren 0 — the gun-duel attrition); NO kill (a4 170 at death); score 700 (the mechanism probe, not a score attempt).

## THE CROSS-BOOT LAW CANDIDATE — the connect windows are STREAM-OWNED

k=2 connects **2/2** (the R71 boot-3 at 506±2 + the R72 boot-1 at 505/506) while **k=0/k=1 miss 0/4** across both boots × both gate sides — and the r69b volley hit k=0/k=1 on ITS stream. The corridor map (offline) shows the corridor CLEAN at ALL FOUR lands — the misses are NOT thefts. **Each input stream has its own connect lands** (the R67 cadence law at the meta level again). THE R73 LEVER: (1) the stream-calibrated throw schedule (spend the grenades at the stream's PROVEN lands first; the K1 supplement re-armed AFTER the first connect); (2) the writer-PC runtime confirmation via the PCSX-Redux oracle.

The capsule: +3 R72 events (71 total) with provenance + the final-mile RECLAIM (the R43-R71 what-texts compacted to the fact-dense cores, every number/address/status preserved; the full narratives in `event_narratives_archive.json`, 71 entries; the canonical compact JSON **65,333 B < the 64 KiB bound** — the R71 debt cleared). Mission 1 stays OPEN."""

s, d = req(f"/repos/{REPO}/issues/9/comments", method="POST",
           payload={"body": BODY})
assert s == 201, d
cid = d["id"]
s2, d2 = req(f"/repos/{REPO}/issues/comments/{cid}")
assert s2 == 200 and d2["body"] == BODY
print("posted + read back byte-identical:", cid)
