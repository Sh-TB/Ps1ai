#!/usr/bin/env python3
"""r72_issue4_addendum.py — the R72 product-path addendum to issue #4
(the R68-R71 precedent), read back byte-identical."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY = """**R72 product-path addendum (the Metal Slug X truck campaign, the volley+phase hybrid) — the deterministic Mission-1 policy v2.0.0.** Push [`2833cf7`](https://github.com/Sh-TB/Ps1ai/commit/2833cf78553a) · the full round report on #9 · evidence `truck_evidence/r72/`.

**What changed on the product path this round:**

- **The chip-fire re-selection shipped (policy 2.0.0):** `TRUCK_CHIP_FIRE` now defaults to **False** — the R71 boot-3 one-variable evidence says the idle-hold stream connects ON GRID (1/3) while the chip-fire stream does not (0/2). The K1 aimed chip-fire stays in the code (patchable True, the K1 suite keeps it covered) as the chip-damage supplement AFTER the connect mechanism is solved.
- **The phase gate widened to the FULL ±2f of ANY grid point (both sides):** the throw fires at every 40f cadence frame whose land sits within ±2f of the nearest freeze+178+164k — the hybrid of the r69b cadence volume (7 throws, 2 connects) and the boot-3 on-grid precision (1/3).
- **BOOT 1 (cap 3 disclosed pre-run, 1/3 spent, 2 HELD): THE CONNECT LANDED ON THE PRE-SIDE GRID POINT** — thrown at fight_f 475 (the land freeze+505, the −1f side the v1.9.0 gate could never reach), **a4 280 -> 180 registered at f1657 = freeze + 506 EXACT**. The drive-in anchor was verified alias-free (`0x9C14` f1073 -> `0x9E08` f1149 -> `0x9E88` f1151).
- **The honest miss record:** the k=0/k=1 pre-side throws (freeze+176/340) MISSED with a CLEAN corridor at all four lands (the offline corridor map — the R71 theft mode was absent). THE CROSS-BOOT LAW CANDIDATE: **the connect windows are STREAM-OWNED** — k=2 2/2 vs k=0/k=1 0/4 on the idle-hold/hybrid stream across R71+R72, while the r69b volley hit k=0/k=1 on its own stream.

**The measured round outcome (honest):** no truck kill — the best boot reached **a4 170** (1 connect + 3 chips from 300); the death f1844 AT the record posture (php 198, gren 0 — the gun-duel attrition with the grenade economy exhausted); score 700 (the mechanism probe, not a score attempt). The score record stays 2400 (R71).

**The source-first closure (offline, zero boots):** the score-word payment writer is PINPOINTED — `0x8005c508: sw $a1, -0x1ce8($a2)` -> 0x800EE318 in the accumulator `0x8005c4b4` (the handle-mediated base, the P1/P2 flag bits, the 99,999,999 cap, the %100 display twin); the amounts 500/1000 arrive FORMATTED through the format->parse chain (0x8007e8b4 -> 0x8007e7d4) from the overlay kill-credit tables — exactly why the R69 immediate hunt was falsified. Exactly 3 score-word stores exist in the whole EXE. The dispatch bound (pointer-mediated, no direct jal) is disclosed; the runtime PC confirmation = the PCSX-Redux CPU oracle (the R64 tools-matrix item).

The R73 lever: the stream-calibrated throw schedule (the proven lands first + the K1 supplement after the first connect) and the PCSX-Redux writer-PC oracle. Mission 1 stays OPEN."""

s, d = req(f"/repos/{REPO}/issues/4/comments", method="POST",
           payload={"body": BODY})
assert s == 201, d
cid = d["id"]
s2, d2 = req(f"/repos/{REPO}/issues/comments/{cid}")
assert s2 == 200 and d2["body"] == BODY
print("posted + read back byte-identical:", cid)
