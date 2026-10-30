#!/usr/bin/env python3
"""r56_issue_report.py — post the R56-learn round report to Issues
#11 (hello_pong) and #12 (FlappyBirdPSX), then single-GET verify."""
import json
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

C12 = """**R56-learn — the surgical-mining round: the flappy student 155 -> 173, 4/5 seeds = the teacher's exact numbers; the exceed bar still open (honest)**

Environment rebuilt internet-first after the sandbox recycle (the flappy ISO sha `b45871d3...` + the hello_pong bin sha `a592f7ed...` verified; the r53 silent-background-launch death REPRODUCED — foreground-only boots enforced). Five boots spent, all in the ledger (`data/learn/r56_flappy_evidence.json`).

**What was tried (the r55-declared open lever: the step-level surgical mining + the widened coverage):**

1. **The trace sweep (boots A-B)**: the law-on-v7 teacher re-recorded on 8 lives — the 5 protocol seeds reproduce r55 EXACTLY ([51,37,38,34,34] = 194; the k30 death @4398; the k6 382 flaps) + 3 new TRAIN seeds (k12=38 alive, k45=30 death @3620, k120=34 alive).
2. **The miner v2 (zero boots)**: the REAL-anchored architecture — the labels' features = the real recorded frames through the EXACT `Brain._vector` mirror (**the mirror gate: 0.0000 px error on all 8 lives**); the simulator = LOCAL physics lookaheads only (the r55k pads re-verified by the local death-reproduction gate, 8/8 PASS). The v1 synthetic-frame pipeline (erase+paste + the phase calibration, fidelity 0.5-3.3 px) was abandoned: its closed-loop sim-student died at the first pipe — "the lab proposes, the boot disposes" held again.
3. **The one-lever ladder (boots C-D)**: the coverage lever (BC + the k12/k120 lives) = **73, catastrophic** — the extra seeds' EARLY-phase data blurs the first-pipe behavior; the champion recipe's narrow data (k6+k60) is LOAD-BEARING. The all-levers candidates regressed (111/107).
4. **Boot E**: **C1 = the r55 champion recipe VERBATIM on the fresh traces = 173 [51,37,38,34,13]** — +18 (+11.6%); the per-seed numbers equal the teacher's on 4/5 seeds: k6 51 budget-exact (@384 ≈ 382 flaps), k30 37 death @4394 ≈ the teacher's 4398, **k60 38 BUDGET-ALIVE — the first student through the 2488 death basin**, k90 34 budget. The held-out k210 (13 vs 34) is the single remaining deficit.

**Honest negatives filed (three mining mechanisms, three failures):** (a) the r55 whole-tail relabels; (b) the r56 risky-lookahead labels on the teacher's own SURVIVED lives = spurious (a crude law continuation "kills" really-surviving flights — the lookahead mining is only meaningful on lives that actually died); (c) the surgical flips (the teacher-death walkbacks k30/k45 + 4 real-basin flips from the RECORDED student lives, jitter-regioned so they stick offline: the acceptance 0.000 -> 1.000) — C4 = 119 vs C1's 173: the corrections BREAK the exact-clone behavior. All machinery + data committed, all excluded from the champion.

**The variance finding**: C1's recipe is byte-identical to the r55 champion's (verified from the committed train report) — the 155 -> 173 delta is trace-sample variance (the r53 per-boot seed-timing variation acting through the recorded data); the k60 "basin" is a sample-level phenomenon, not a fixed property of the seed.

**Verdict**: the flappy exceeds bar (the cap arithmetic 195 > 194) NOT met — C1 MEETS the teacher on 4/5 seeds within-boot and +18 absolute, but 173 < 194. Champion: `data/learn/flappy_student_feat_r56_c1.npz` (7,080 B, feature_version 7, subprocess brain, frames only). Suite 629 passed + 1 xfailed; `test_learning_boundary` green (the AST scan, the subprocess selfcheck, the <=4 MiB artifacts)."""

C11 = """**R56-learn — pong untouched this round; the flappy mining round recorded here for the mission ledger**

Issue #12's round (see that thread): the surgical-mining round — the miner v2 (the REAL-anchored labels through the exact `Brain._vector` mirror, 0.0000 px; the local physics lookaheads only), the one-lever ladder, and the flappy student at **173 [51,37,38,34,13]** = the teacher's exact per-seed numbers on 4/5 seeds (+18 over r55). Three mining mechanisms filed as honest negatives. The pong P4 bar (the student exceeding its teacher, 8>7, subprocess brain, frames only) STANDS from r54; the pong feature paths are byte-unchanged (suite 629 green, `test_learning_boundary` green)."""

for num, body in ((12, C12), (11, C11)):
    s, d = req(f"/repos/{REPO}/issues/{num}/comments", "POST",
               payload={"body": body})
    assert s == 201, (num, s, d)
    cid = d["id"]
    s, back = req(f"/repos/{REPO}/issues/comments/{cid}")
    assert s == 200 and back["body"] == body
    print(f"issue #{num}: comment {cid} posted + read-back verified")
