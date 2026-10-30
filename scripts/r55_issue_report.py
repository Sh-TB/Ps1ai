#!/usr/bin/env python3
"""r55_issue_report.py — post the R55-learn round report to Issues
#11 (hello_pong) and #12 (FlappyBirdPSX), then single-GET verify."""
import json
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

C12 = """**R55-learn — the perception round: the same-sensor teacher reaches the full-res tier; the student matches it on 3/5 seeds**

Ten boots spent this round (all disclosed in `data/learn/r55_flappy_evidence.json`), zero undisclosed amendments. Five death mechanisms were each proven by pixel dissection on recorded traces and fixed at the source in `ps1play/learn/visual_only.py`:

1. **Bird-extended gap run** — the bird occludes the rim rows behind its body; the free run extends ~32px; the tracker's 24px gate adopted the bias (tv7g_k90: the raw gap ALTERNATED 125<->141 inside ONE static pipe; the law flew a 16px-too-low line into the bottom rim). Fix: the **constant-gap decontamination** — the gap height is source-constant 70px, so a run > 82px proves one side bird-extended; the side NEARER the bird is pinned out and the center pins on the opposite edge.
2. **Pipe-gradient mask holes** — the v2 brightness gates (g>135, r<205) rejected the pipe gradient's bright (216,232,128) and shaded (80,120,40) ends; the lower-pipe rows flipped free/pipe as the band width wobbled (3/6 vs 3/9 columns). Fix: the measured hue rule `(g > r+8) & (b < g-40)`.
3. **Band-fragment gap shift** — a single-dip column split the band; the left fragment's profile shifted the whole reported gap 19px (101->83); the tracker adopted it as the "next pipe"; the law flapped at the shifted target and rose into the top rim (tv7m_k6/k60). Fix: merge dip-split bands + the bird-overlap band pick.
4. **Score-glyph edge latch** — one (147,144,94) digit anti-alias block (r-g=3) passed the face test and kept the observer latched at y=28 while the true bird fell 66->99 (tv7m_k90). Fix: the **proximity rule** — weak orange (r>g+3) survives only within 2 small blocks of strong orange (r>g+8; the bird's beak r-g>=13; the digit edge has no strong neighbor).
5. **Rim-row fraction flip** — one edge column's sub-pixel washout flipped 4 rim-adjacent rows (frac 0.56<->0.44 = 5/9 vs 4/9 columns) and shifted the reported gap 19px in ALL THREE tv7n deaths. Fix: the **core-window profile** — a row is PIPE iff ANY 3 adjacent band columns are mostly green; the pipe's solid core reads 1.0 in every window.

Plus the measured dynamics correction: the r54k "terminal +2" fit was faked by the 8-frame rounding plateaus; the corpus truth (183 impulse events): the rise arc decelerates exactly +1 px/f², the fall accelerates +0.125 px/f² with the screen dy rounded HALF-UP, no cap.

**M1 ACHIEVED** — the law-on-v7 (small frames + own action history ONLY) flies **51/37/38/34/34 = 194 pipes with 4/5 lives ALIVE AT BUDGET** (k6/k60/k90/k210) — the first small-frame agent to survive the k90/k210 budgets; the per-seed numbers match or exceed the full-res teacher tier (38/38/38/34/34) measured within-boot.

**The student** (feature_version 7, subprocess brain, frames only, artifact 7,101 B): the champion (BC, hidden 128) = **155 pipes (51/37/20/34/13)** — MEETS the teacher on 3/5 seeds (k6 51 = budget-exact with the teacher's exact 382-flap flight; k30 37 with death at 4398 = the teacher's 4398; k90 34 = budget), BELOW on k60 (20 vs 38) and k210 (13 vs 34). The student-exceeds-teacher bar: NOT met for flappy this round — honest (met for pong in r54: 8>7).

**Honest negatives filed**: (a) the failure-mining (the sim-oracle counterfactual recovery relabels mined from the teacher's k30 death — fb10/eb24 from anchor -200 survives, margin 2.3px — and the student's k60 death) DEGRADED the closed loop at weight 3 (140->91) and weight 1 (123): the whole-tail relabels teach a second flight style that interferes; the machinery is committed, the data excluded from the champion; (b) DAgger at the student's drift states reproduces the teacher's own failing actions — the r54 pong DAgger gain did not transfer.

The offline sim lab (`scripts/r55k_sim_lab.py`, zero boots) reproduced the teacher's k30 death (sim 4394 vs recorded 4397), swept the law parameters, and served as the mining oracle. Suite 614 passed + 1 xfailed; the AST boundary scan green (numpy + stdlib only)."""

C11 = """**R55-learn — pong untouched this round; the flappy perception breakthrough recorded here for the mission ledger**

Issue #12's round (see that thread for the full report): five small-frame perception death mechanisms fixed at the source; the same-sensor teacher (small frames + own action history ONLY) now flies **194 pipes with 4/5 lives ALIVE AT BUDGET** — matching the full-res teacher tier within-boot. The pong P4 bar (the student exceeding its teacher, 8>7, subprocess brain, frames only) stands from r54; the v7 perception work is flappy-local (`visual_only.py`'s flappy path) and the pong feature paths are byte-unchanged (suite 614 green)."""

for num, body in ((12, C12), (11, C11)):
    s, d = req(f"/repos/{REPO}/issues/{num}/comments", "POST",
               payload={"body": body})
    assert s == 201, (num, s, d)
    cid = d["id"]
    s, back = req(f"/repos/{REPO}/issues/comments/{cid}")
    assert s == 200 and back["body"] == body
    print(f"issue #{num}: comment {cid} posted + read-back verified")
