#!/usr/bin/env python3
"""r74_issue4_addendum.py — the R74 product-path addendum to
issue #9 (the R67-R73 precedent), read back byte-identical."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY = """**R74 product-path addendum (the Metal Slug X truck campaign, THE STREAM HANDOFF) — the deterministic Mission-1 policy v2.2.0.** Push [`04c6bc0`](https://github.com/Sh-TB/Ps1ai/commit/04c6bc02a73b) · the full round report on #9 · evidence `truck_evidence/r74/`.

**What changed on the product path this round:**

- **Policy 2.1.0 -> 2.2.0 THE STREAM HANDOFF:** the shipped policy starts on the VOLLEY HEAD = the VERBATIM r69b throw schedule (fight_f 64/106/147/188/229/270/311 — the schedule IS the stream; a dynamic 40f cadence never lands on-grid) and hands off ON THE CLOCK at fight_f 350 to the idle-hold tail (the v2.1.0 gate + the rear-escort exemption verbatim). No lead, no probe in the head (foreign inputs to the r69b stream). 14 new offline tests; 6 suites re-anchored — zero weakened.
- **BOOT 1 (cap 3 disclosed pre-run, 1/3 spent): THE FIRST HEAD CONNECT on the product path** — a4 300 -> 200 at f1411 = freeze+259 (the fight_f 229 throw, +0f on the head's own grid). The escort-feed strays chipped ×7 (200 -> 130) — **THE A4 FLOOR 130 = the product-path record** (the previous 170). Score 1300.
- **THE HEAD-PHASE LAW:** the connect phase is stream-determined per head variant — the r74b1 head's grid = freeze+259 (+81f, ~the half-period, vs the r69b/178-grid); the 270/311 throws missed exactly as the law predicts (+41f/+82f off); the tail's 178-grid k=2 window is MOOT on this stream. Deterministic and reproducible.
- **THE CORRIDOR-FEED SHIELD:** the k=2 gate window never threw — the corridor blocked from ~f1600 (the walkers -10.2/-67.9/-101.9); the escort-first cadence every 13f; the bullets PIERCE the transparent point-blank walker (the R51 law) and stray-chip the truck. The death f1884 = freeze+733 (the truck_approach walk moved the player to px 1106) — **the death is posture-coupled**, refining the R73 section-locked reading.

**The measured round outcome (honest):** no truck kill — a4 floor 130 (1 connect + 7 chips from 300); the mechanism proven: the head's own grid connects ON SCHEDULE. Score record stays 2400 (R71).

**R75 NAMED — THE HEAD-PHASE EXTENDED SCHEDULE:** the head's grid continues at freeze+423/+587 (the throws at fight_f 393/557) — policy 2.3.0 = v2.2.0 with the handoff 350 -> 620 and the schedule + {393, 557}: the 2nd and 3rd connects deliver **a4 200 -> 100 -> 0 = THE TRUCK KILL INSIDE the death clock** (the r74b1 death at freeze+733 admits the freeze+587 land with 146f of runway). Arm 2: the corridor hygiene at the extended windows. Arm 3 (unchanged): the PCSX-Redux writer-PC oracle. Mission 1 stays OPEN."""

s, d = req(f"/repos/{REPO}/issues/4/comments", method="POST",
           payload={"body": BODY})
assert s == 201, d
cid = d["id"]
s2, d2 = req(f"/repos/{REPO}/issues/comments/{cid}")
assert s2 == 200 and d2["body"] == BODY
print("posted + read back byte-identical:", cid)
