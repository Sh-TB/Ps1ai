#!/usr/bin/env python3
"""r74_issue_report.py — post the evidence-grade R74 round report to
issue #9 (the R67-R73 precedent), read back byte-identical."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY = """**R74 round report (the capsule lever executed: THE STREAM HANDOFF — the first head connect on the product path, the head-phase law, the corridor-feed shield) — badges: IMPLEMENTED / TESTED / OBSERVED / VERIFIED.** Evidence: `truck_evidence/r74/` (1 product boot, the ledger disclosed below) · policy `2.1.0 -> 2.2.0` · push [`04c6bc0`](https://github.com/Sh-TB/Ps1ai/commit/04c6bc02a73b) · suite **986 passed + 10 skipped + 1 xfailed** (zero weakened).

**The product ledger (cap 3 disclosed pre-run, 1/3 spent, 2 HELD):** boot 1 = the shipped v2.2.0 handoff (NO module patching). Process note: the sandbox recycled mid-round — the clone was resynced to `428488f` and the change set re-applied via the verified re-apply scripts (every replacement asserted); the suites re-verified the result. Read-only product-loop probe: legal inputs only, zero RAM writes, no training, no runtime LLM.

## The product track — THE STREAM HANDOFF (policy 2.2.0)

The R73 calibration table proved the ownership sets COMPLEMENT (the volley owns k=0/k=1; the idle-hold owns k=2; no stream owns all three). The shipped policy therefore **starts on the volley head — THE VERBATIM r69b throw schedule** (fight_f 64/106/147/188/229/270/311 — the R68 verbatim-replay precedent; a dynamic 40f cadence does NOT reproduce this stream: its landing phase never reaches ANY grid point — **the schedule IS the stream**) — and hands off ON THE CLOCK at fight_f 350 to the idle-hold tail (the v2.1.0 semantics verbatim). The head has NO lead throws and NO C4 probe (foreign inputs to the r69b stream). 14 new offline tests; 6 suites re-anchored with the hold-state migrations — zero weakened.

**BOOT 1:** the head threw **6/7** (the fight_f 106 frame absorbed by the gre40 cooldown off-by-one; the 147 slot by the gate's early throw at 146 — both deterministic) and **THE FIRST HEAD CONNECT LANDED a4 300 -> 200 at f1411 = freeze+259** (the fight_f 229 throw, +0f on the head's own grid, the land+1 read latency). The escort-feed strays **chipped ×7** (200 -> 130, the ~26f cadence — the R51 piercing: the bullets pass the transparent point-blank walker and register on the truck) — **THE A4 FLOOR 130 = the product-path record** (the previous 170). Death f1884 = freeze+733 (NOT the f1844 clock: the `truck_approach` walk moved the player from px 1071 to 1106 — the r69b death posture). **The death is POSTURE-COUPLED**, refining the R73 section-locked reading: the same posture reproduces byte-exact; a moved posture moves the death. 6 throws / 1 connect / 7 chips; score 1300.

## THE HEAD-PHASE LAW — the connect phase is stream-determined per head variant

The r74b1 head's connect grid = **freeze+259 (+81f, ~the half-period, vs the r69b/178-grid)**: the 229 throw landed ON it (+0f, CONNECTED); the 270/311 throws missed (+41f/+82f off — the predicted off-window); the tail's 178-grid k=2 window is **MOOT** on this stream. The ±1-throw stream delta (the 106/147 absorptions) shifted the phase +81f — **deterministic and reproducible** (the pattern 64/146/188/229/270/311). The offline decision replay (the committed policy over the boot's exact observations) reproduced the boot byte-for-byte.

## THE CORRIDOR-FEED SHIELD

The tail's k=2 window (the gate opens fight_f 474) never threw — the corridor BLOCKED from ~f1600 by the walkers (−10.2 h~210, −67.9, −101.9); the escort-first cadence every 13f at the point-blank −8.7 walker, but the bullets **PIERCE** it (the R51 transparent law) and **STRAY-CHIP the truck** (the 7 chips = the stray-feed second damage path) — the walkers never die to aimed fire, and the lob is withheld by C2 (correct).

## R75 NAMED — THE HEAD-PHASE EXTENDED SCHEDULE (the kill attempt, round 2)

The head's own grid continues past the old handoff: **freeze+423 and freeze+587** (the throws at fight_f 393 and 557). Policy 2.3.0 = v2.2.0 with `TRUCK_HANDOFF_FIGHT_F` 350 → 620 and the schedule **+ {393, 557}**: the 2nd and 3rd head connects deliver **a4 200 -> 100 -> 0 = THE TRUCK KILL INSIDE the death clock** (the r74b1 death at freeze+733 admits the freeze+587 land with 146f of runway). The extension throws are ON the head's grid — not perturbations. Arm 2: the corridor hygiene at the extended windows (the r74b1 feed blocked ~fight_f 449 — the 393 window may still be clean). Arm 3 (unchanged): the PCSX-Redux writer-PC oracle.

The capsule: +3 R74 events (77 total) with provenance + the final-mile RECLAIM (the R73/R72/R71 events verbatim-archived — asserted; the older cores preserved under `what_full_capsule_v3` — lossless; 77 archive entries; the canonical compact JSON **64,877 B < the 64 KiB bound**). Mission 1 stays OPEN."""

s, d = req(f"/repos/{REPO}/issues/9/comments", method="POST",
           payload={"body": BODY})
assert s == 201, d
cid = d["id"]
s2, d2 = req(f"/repos/{REPO}/issues/comments/{cid}")
assert s2 == 200 and d2["body"] == BODY
print("posted + read back byte-identical:", cid)
