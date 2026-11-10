#!/usr/bin/env python3
"""r70_issue4_addendum.py — the R70 product-path addendum to issue #4
(the R68/R69 precedent), read back byte-identical."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY = """**R70 product-path addendum (the Metal Slug X truck campaign, the phase law) — the deterministic Mission-1 policy v1.8.5 + the adapter 0.5.1.** Push [`cc846d7`](https://github.com/Sh-TB/Ps1ai/commit/cc846d788ee4) · the full round report on #9 · evidence `truck_evidence/r70/r70_phase_probe.jsonl`.

**What changed on the product path this round:**

- **The phase law shipped (P1):** the lob fires only on the vulnerability grid — the land sits at `freeze+178+164k` (the 164f cycle phase-locked to the freeze frame; the r69b connects f989/f1153 are now DETERMINISTIC, no longer a cadence accident). One throw per grid point, the clock freezes through a scan flicker, a fresh truck re-anchors the grid.
- **The spatial band shipped (v1.8.4):** the throw requires |dx| in `[131.5, 135.0]` — every measured miss (-130.5/-136.5/-139.5) is rejected, every measured connect (-133.5) admitted. Below the band the player HOLDS (the re-center walk was tried and withdrawn — the boot-5 knockback-pin evidence).
- **The corridor guard shipped (C2):** the lob requires a clean descent corridor — the boot-1 lob was stolen mid-descent by an interloper (the R49 steal model extends to lobs).
- **The drive-in arm shipped (P2/P3, adapter 0.5.0):** the truck drive-in states (`0x9C14/0x9E08`) map to `SC_TRUCK_IN=8` — the policy walks to the record posture ~60f earlier than v1.7.1 managed. The k=0 lead window (land freeze+14) is measured UNREACHABLE from the drive-in walk (the sx band admits the truck ~f759; the posture arrives ~f815-840) — the lead stands down honestly, the one-shot width probe replaces it.
- **The packing priority shipped (adapter 0.5.1):** the truck row can no longer be dropped from the observation by the chaser swarm (the boot-3 clock re-anchor failure is closed).
- **The escort classes fixed (C5):** the `sc=6` walk-state chasers are now engaged (they used to fill the corridor untouched).

**The measured round outcome (honest):** no truck kill yet — the best boot reached **a4 230** (from 300) via the chips (the escort stray bullets: -10 a4/+100 score at ~26f) and beat the record: **the death at f1324 (+6 past the f1318 record), the score 2100 (+400 over 1700)**. The R71 schedule is armed: the chips + TWO centered connects reach a4 0 inside the window.

Suite 903 passed + 10 skipped + 1 xfailed (the MSX set 111 green; zero weakened). Zero RAM writes, legal inputs only, no training, no runtime LLM."""

s, d = req(f"/repos/{REPO}/issues/4/comments", "POST", {"body": BODY})
print("HTTP", s, "comment id:", d.get("id"))
if s == 201:
    s2, comments = req(f"/repos/{REPO}/issues/4/comments?per_page=100")
    mine = [c for c in comments if c["id"] == d["id"]]
    print("read back byte-identical:",
          bool(mine) and mine[0]["body"] == BODY)
