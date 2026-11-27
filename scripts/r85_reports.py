#!/usr/bin/env python3
"""r85_reports.py — post the R84/R85 report (the kill x3 deterministic
+ the tree recovery) to #9 + #4 (byte-identical read-back)."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

REPORT = """**R84/R85 round report — THE KILL x3 DETERMINISTIC (f=2125–2131, score 2700) + the tree recovery after the second recycle + the post-kill section engages — badges: IMPLEMENTED / TESTED / VERIFIED.** Push [`9f9bb5f`](https://github.com/Sh-TB/Ps1ai/commit/9f9bb5f) + the tree-recovery commit [`028ab9b`](https://github.com/Sh-TB/Ps1ai/commit/028ab9b) · the suite **998 passed** + 11 skipped + 1 xfailed (zero weakened) · the evidence `truck_evidence/r85/r85_calibrated_probe_boot2.jsonl` + the 3 kill PNGs (the owner directive: NO bulk image uploads — the 2470 probe PNGs stripped from the commit, the 3 kill PNGs kept).

## The tree recovery #2

The second sandbox recycle wiped the local git OBJECTS (the checkout reverted to the Oct-22 base; `git fetch` blocked). **The working tree rebuilt from the GitHub API against remote main 05cb7fd: 1595 files restored, 0 failed** (the code + the data + the scripts + the capsule; the images per the owner directive). Then the r61/r62/r64 deployment stack completed (the flappy npz models ×21 + the onnx ×4 + the tsv) → the suite back to 998 green.

## THE CRITICAL FIX: the pair-mode block

The restored policy still carried the FALSIFIED pair-mode block (the walk-out volley) — **914 `pair_volley` frames blocked the kill path** in the r85 boot-1 (the score frozen at 1400). The removal restored the kill instantly: **f=2125, score 2700**.

## THE KILL x3 — DETERMINISTIC

| boot | kill frame | score |
|---|---|---|
| r82 boot-2 | f=2131 | 2700 |
| r83 boot-1 | f=2131 | 2700 |
| r85 boot-2 | f=2125 | 2700 |

The recipe: the byte-exact pre-death stream (the k=0 CONNECT at 1411; the chips → 130; the scripted death at 1884) → the respawn detected → the walk-back 992→1071 → **the post-respawn chip-fire (the aimed bullets at the 13f cadence; the bullets pierce the marchers — the R51 law) → 13 chips 130→0 → a4 0 = THE TRUCK DEAD**.

## THE POST-KILL SECTION (r85 boot-2, MAX_F 6000)

The kill at 2125 → **`face_rear` at px 1148–1159 (f2200–2300) — PAST the old 1105.8 wall** → the rear-fight machinery engaged (the SECOND encounter) → the walk 1046–1091 → the 3-life budget consumed ~2950 → the game over. The TRUCK_DEAD_ROW (st 0xa44c, x 937.5) persists — the wreck documented.

## R84 parked — the no-death kill (the m2_gate lever)

The 13f endgame escort cadence installed (the chips accelerated: 1683/1697/1711) but the marcher WAVES eat the bullets (the a4 stuck at 120 at the death #1). The lever: **the lane clear before the endgame** (the marcher budget spent first, then the 13f chip-fire) → the kill before 1884 → the CLEAN resolve → the m2_gate.

## R86 named — THE REAR FIGHT

The second encounter's completion with the r73 exemption law + the rear-fight rules; the post-kill posture hold saves the lives.

The capsule: 84 events (the KILL event VERIFIED, the provenance = the boot2 jsonl), 65,039 B < the 64 KiB bound; next_experiment = R86. Legal inputs only, zero RAM writes, no training, no runtime LLM."""

ADD = ("**R84/R85 product-path addendum (the MSX truck campaign) — THE KILL x3 DETERMINISTIC (f=2125–2131); the post-kill section engages (face_rear past the old wall → the rear fight = the second encounter).** Push [`9f9bb5f`](https://github.com/Sh-TB/Ps1ai/commit/9f9bb5f) · the full round report on #9 · the policy 2.6.1 (the chip-fire; the pair-mode block REMOVED — it was blocking the kill in the restored tree) · the recovery: the tree rebuilt from the GitHub API after the second recycle (1595 files; the owner directive honored: no bulk image uploads — the 3 kill PNGs only).\n\n"
       + REPORT[REPORT.index("## THE CRITICAL FIX"):])

for issue, body in ((9, REPORT), (4, ADD)):
    s, d = req(f"/repos/{REPO}/issues/{issue}/comments", method="POST",
               payload={"body": body})
    assert s == 201, d
    cid = d["id"]
    s2, d2 = req(f"/repos/{REPO}/issues/comments/{cid}")
    assert s2 == 200 and d2["body"] == body
    print(f"#{issue} posted byte-identical:", cid)
