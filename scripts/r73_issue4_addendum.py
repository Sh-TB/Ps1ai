#!/usr/bin/env python3
"""r73_issue4_addendum.py — the R73 product-path addendum to issue #4
(the R68-R72 precedent), read back byte-identical."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY = """**R73 product-path addendum (the Metal Slug X truck campaign, the rear-escort exemption) — the deterministic Mission-1 policy v2.1.0.** Push [`bc970af`](https://github.com/Sh-TB/Ps1ai/commit/bc970af05e65) · the full round report on #9 · evidence `truck_evidence/r73/`.

**What changed on the product path this round:**

- **The calibration table shipped first (offline, ZERO boots):** every committed boot throw mined per (stream, k, signed land offset). **THE K-OWNERSHIP LAW CONFIRMED ON BOTH SIDES** — the idle-hold stream connects ONLY at k=2 (4/4 across −1f AND +1f) while k=0/k=1 NEVER (0/4 across −2f AND +0f); the volley stream owns k=0/k=1 (−1f ×2). **THE SIDE LAW DEAD:** the ownership is per-window-per-stream, not per-side.
- **THE BLOCKED WINDOW found:** the R72 boot-1 audit — the k=3 grid window (fight_f 638-642, phase open, 9 grenades live) NEVER threw: every frame f1780..f1844 was held by the T3 escort-first cadence on a REAR escort at dx +37.8 (the truck at −133.5). A rear escort cannot eat the lob (the C2 corridor predicate guards the descent line) — a pure loss of the owned window.
- **Policy 2.0.0 → 2.1.0 THE REAR-ESCORT EXEMPTION:** during the phase-open frames ONLY, a clear-line escort on the OPPOSITE side of the truck no longer holds the grid throw; same-side precedence and the off-window frames stay byte-identical v2.0.0 (the stream law). 10 new offline tests; 6 suites re-anchored with the evidence noted in-test — zero weakened.
- **BOOT 1 (cap 3 disclosed pre-run, 1/3 spent, 2 HELD): the exempted K=3 THROW FIRED at f1790** (the turn frame f1789 first) — the first k=3 throw ever — land f1820 = freeze+669 (−1f): MISS (a4 flat 170). **THE OWNED SET ON THE IDLE-HOLD STREAM IS EXACTLY {k=2}.** The R72b1 trajectory reproduced BYTE-EXACT to the disclosed divergence (freeze f1151; the k=2 CONNECT f1657 a4 280→180; the chips f1581/f1645/f1709); 4 throws / 1 connect / 3 chips.

**The measured round outcome (honest):** no truck kill — the best boot holds at **a4 170** (1 connect + 3 chips from 300); score 700 (the mechanism probe, not a score attempt). The score record stays 2400 (R71). **THE DEATH RE-CLASSIFIED (the R72 "gun-duel attrition" reading SUPERSEDED):** php is FLAT 198 from f1200 to f1844 in BOTH boots — NO attrition; the death is ONE deterministic event at f1844 = freeze+693, byte-exact across two boots with divergent inputs (an input divergence 55f before the death did not move it) — the death clock is SECTION-LOCKED, not wave-coupled, and not health-driven (the death PNG: PRESS START; no table-visible projectile).

**R74 NAMED — THE STREAM HANDOFF KILL:** the ownership sets COMPLEMENT — the volley stream owns k=0/k=1 (a4 300→100 by freeze+342) and the idle-hold stream owns k=2 (freeze+506, 4/4) — so a **volley HEAD → idle-hold TAIL** handoff (ONE policy variable: the cooldown stream, switched on the measured a4 transition; the r69b scroll shove at ~f1180 is the risk window) takes the k=2 land to **a4 0 = THE TRUCK KILL INSIDE the f1844 death clock**. Arm 2: the death-evasion probe (the f1844 dodge window). Arm 3 (unchanged): the PCSX-Redux writer-PC oracle. Mission 1 stays OPEN."""

s, d = req(f"/repos/{REPO}/issues/4/comments", method="POST",
           payload={"body": BODY})
assert s == 201, d
cid = d["id"]
s2, d2 = req(f"/repos/{REPO}/issues/comments/{cid}")
assert s2 == 200 and d2["body"] == BODY
print("posted + read back byte-identical:", cid)
