#!/usr/bin/env python3
"""r57_issue_report.py — R57 round: create the autonomous-student workstream
issue and cross-link it from Issue #12 (parent thread, content NOT duplicated).

Owner directive (2026-10-31): open ONE new issue for the R57 MASTER MISSION
and review it line by line. PART 17 of the mission forbids duplicate Flappy
issues "unless a genuinely separate root problem exists" — the autonomous-
learning workstream (teacher cutoff <= 20 pipes, teacher-off training,
unseen-seed evaluation) is that separate root workstream; #12 stays the
parent evidence thread.

Run:  python3 scripts/r57_issue_report.py            # create + cross-link
      python3 scripts/r57_issue_report.py --verify   # read back
"""
import json
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

ISSUE_TITLE = ("[R57] FlappyBirdPSX — Autonomous Student Learning Beyond the "
               "Teacher (20-pipe bootstrap → teacher-off self-improvement)")

ISSUE_BODY = r"""
**Workstream issue, split from #12 by owner directive (2026-10-31).**
Issue #12 remains the parent visual-learning thread and keeps all
historical evidence (teacher tier **194** aggregate; R56 C1 = **173**;
the honest negatives). This issue owns the R57 autonomous-learning
workstream. Canonical texts committed this round:
**`docs/r57_mission.md`** (verbatim mission) and
**`docs/r57_mission_review.md`** (line-by-line audit: **22 findings,
0 blockers** — 9 GAPs with proposed resolutions, 5 RISKs with
mitigations, 8 OK-with-notes; all headline numbers recomputed).

---

## Verified starting point (`f5a47a6`)

| Reference | k6 | k30 | k60 | k90 | k210 | Total | Artifact |
|---|---|---|---|---|---|---|---|
| Teacher (law-on-v7, frames-only) | 51 | 37 | 38 | 34 | 34 | **194** | — |
| R55 BC champion | 51 | 37 | 20 | 34 | 13 | 155 | `flappy_student_feat_p6v7h128.npz` (7,101 B) |
| R56 C1 (current best) | 51 | 37 | 38 | 34 | 13 | **173** | `flappy_student_feat_r56_c1.npz` (7,080 B) |

The 155→173 jump is **not proven autonomous learning** (trace-sample
variance, R56 verdict). Known hard cases carried into R57: C2≈111 /
C3≈107 / C4=119 mining regressions; **k210 = 13 vs 34** (the single
generalization deficit); the **pipe-overlap centroid latch** (bird
frozen ~95–105 px while the true bird falls 77→139; every color mask
fails in-regime); teacher-DAgger at student drift states reproduced the
teacher's own failing actions.

## Product definition

A small visual student that (1) gets limited initial instruction,
(2) learns the basic visual rules, (3) **stops receiving teacher actions
and labels entirely**, (4) plays the real game independently, (5–6)
discovers strategies and learns from its own successes/failures, (7–8)
keeps improving **beyond the teacher's demonstrated skill** toward
30/40/50+ pipes. The teacher is a starting point, not a limit. The
student is the product.

## Hard rules (non-negotiable, test-enforced)

1. **Teacher cutoff ≤ 20 pipes.** Labels only up to `cutoff_frame` =
   the frame of the 20th visually confirmed passage per teacher
   episode; frames ≥ cutoff excluded including the cutoff action.
   Hard test: NO TEACHER LABEL AFTER PIPE 20.
2. **Teacher-off learning.** After bootstrap the student pipeline runs
   with `ps1play.learn.teacher` **import impossible** — three
   enforcement layers: AST denylist scan + import-hook crash in the
   brain subprocess + hashed `no_teacher_trace.jsonl` runtime proof.
   No DAgger, no teacher recovery, no teacher-tail relabels.
3. **Visual-only everything.** Policy inputs and rewards both
   frames-only (the existing `visual_only.py` boundary + AST scan).
   Reward = +1 per visually confirmed passage, dedup key
   `(episode_id, pipe_index)`, crossing-transition only; no RAM-derived
   reward; truncation ≠ death.
4. **Real-game authority.** The emulator decides; simulators only
   propose. Every selected candidate passes real emulator evaluation.
5. **Full episodes.** Student frame budget **10,000 frames** (≈ 2× the
   measured 50-pipe estimate ≈ 7,300 f); no passage-count-based
   termination; evaluation from the authentic game start.
6. **Splits.** TRAIN/VAL/TEST seed list committed **before**
   collection; all R55/R56 seeds (k6/k30/k60/k90/k210) are VAL;
   **≥ 20 unseen TEST seeds, n=3 boots each, fixed in advance**; TEST
   retired after the final evaluation.
7. **Champion gate.** VAL median not worse by >2 pipes AND no dev seed
   worse by >5 AND 10-pipe survival not down >10 points (n=3) before
   any champion replacement; trade-offs documented and explicit.
8. **Small model.** ~7 KB reference; numpy+stdlib deployment;
   ONNX optional with a stated acceptance bar (native vs ONNX
   agreement + a real consumer), else PENDING.

## Work plan (execution order from the review)

- **P0 audit + splits** — checkpoint/dataset provenance sweep
  (p6v7h128, C1–C4, p7v7 family), manifest schema
  (+`cutoff_frame`, `boot_id`, `feature_version`, `action_contract_id`,
  emulator version), C1 reproduction protocol (3 boots/seed, spread
  reported), seed-list commit.
- **P1 bootstrap** — 15 capped teacher episodes (≥10 boots, TRAIN
  seeds only, ≥5 reaching 20) recorded with the *same* passage
  detector the reward uses; clean `r57_bootstrap_bc` selected on VAL
  closed-loop median; immutable from birth; honest expectation 10–15.
- **P2 teacher-off machinery** — the three enforcement layers + trace
  integrity test; the runner works with teacher import impossible.
- **P3 learner bake-off** — fixed per-arm boot budgets, interleaved
  paired seeds:
  **C: ES/ARS/CEM first** (episodic directly-measured objective, tiny
  parameter count, CPU-only, immune to the saturated-logit pathology
  that broke prior PPO) → **B: correct PPO** (real sampling, exact old
  log-prob = **log p_behavior including the ε-mixture**, GAE, KL/entropy
  monitoring, conservative updates) → **A: confidence-aware ε(s)**
  exploration layer on the winner (ε concentrated in uncertain
  gate-approach states, per-episode exploration cap) → **D: self-
  imitation** last, student successes only, gated like mining.
- **P4 perception** — the pipe-overlap latch fix (per-column
  green-profile template matching or a tiny learned CNN observer,
  frames-only), with observer acceptance thresholds incl. the overlap
  regime; low-confidence rows dropped from training.
- **P5 promotion + final evaluation** — numeric gate, 20 TEST seeds ×
  3 boots, five-way comparison (bootstrap BC / R55 ref / R56 C1 ref /
  best independent candidate / teacher-capped-20), full evidence pack,
  worklog + verified push.

## Success ladder (goals, not permission to fabricate)

Median ≥ **20** pipes on new seeds → median ≥ **30** with ≥75% of
episodes ≥20 → stretch ≈ **40** → long-term repeated **50+**. Every
rung requires evidence that *post-bootstrap learning* caused it. If 30
is not reached, the blocker is named from: exploration / reward /
perception / physics / policy capacity / training budget /
generalization / emulator nondeterminism — a failed attempt that
establishes the exact blocker still counts as progress.

## Test matrix (extends, never forks, the existing suite)

`test_r57_teacher_cutoff.py` · `test_r57_no_teacher.py` ·
`test_r57_reward.py` · `test_r57_exploration.py` · `test_r57_splits.py`
+ `test_learning_boundary` extended to the student training runner.
The existing 629-passed + 1-xfailed suite, Pong regression and full
Flappy integration must stay green. Passing tests alone does not prove
learning — real-game performance is required.

## Deliverables (29 items — see the mission for the full list)

Starting/final commits · checkpoint provenance · qualified bootstrap ·
cutoff proof · teacher-off proof · RAM audit · observation/reward audit ·
algorithm + exact config · student-episode count · update count ·
checkpoint history · per-seed train/val/test results · mean/median/P25/
P75/min/max/std · counts ≥20/30/40/50 · comparisons vs bootstrap, R55,
C1 · CPU perf + model size · ONNX status · full test results ·
screenshots + traces · #12 update · R57 worklog · reproduction command ·
**boot-variance record** (review item 29) · honest unresolved
limitations.

## Status labels

IMPLEMENTED / TESTED / OBSERVED / PARTIAL / BLOCKED / PENDING /
SUPERSEDED — implementation is never reported as observed behavior.

---

*Reproduction: see `docs/r57_mission_review.md` §4 for the P0–P5 order
with the evidence that motivates it; `docs/r57_mission.md` is the
canonical owner text. Parent thread: #12.*
"""

CROSS_LINK_COMMENT_12 = """**R57 workstream split out** (owner directive, 2026-10-31): the
autonomous-learning track now has its own issue — the 20-pipe teacher
cutoff, teacher-off training (import-impossible, trace-proven), the
ES/ARS-vs-PPO bake-off, and the 20-unseen-seed evaluation. This thread
(#12) stays the parent evidence thread; nothing is duplicated.

Intake artifacts committed at the R57 round commit:
- `docs/r57_mission.md` — the canonical verbatim R57 mission text.
- `docs/r57_mission_review.md` — the line-by-line audit: 22 findings,
  0 blockers (9 GAPs with resolutions, 5 RISKs with mitigations);
  recomputed C1 = 173 / teacher = 194; the audit corrects the header's
  "C2 and C4" summary (C3 ≈ 107 also regressed).

Historical facts here are untouched: teacher 51/37/38/34/34 = 194;
C1 = 173 [51,37,38,34,13]; k210 the single deficit; three mining
mechanisms honestly filed as failures. R57 results will be posted in
both threads per convention."""


def create_issue():
    s, d = req(f"/repos/{REPO}/issues", method="POST", payload={
        "title": ISSUE_TITLE,
        "body": ISSUE_BODY,
        "labels": [],
    })
    print("create issue: HTTP", s)
    if s == 201:
        print("  #", d.get("number"), d.get("html_url"))
        return d.get("number")
    print("  ", json.dumps(d)[:400])
    return None


def cross_link(issue_number):
    s, d = req(f"/repos/{REPO}/issues/12/comments", method="POST",
               payload={"body": CROSS_LINK_COMMENT_12})
    print("cross-link comment on #12: HTTP", s)
    if s == 201:
        print("  ", d.get("html_url"))
    else:
        print("  ", json.dumps(d)[:400])
    return s


def verify(issue_number):
    s, d = req(f"/repos/{REPO}/issues/{issue_number}")
    print("read back issue:", s, "| title:", d.get("title", "")[:80])
    print("  body chars:", len(d.get("body", "")), "| state:", d.get("state"))
    return s


if __name__ == "__main__":
    if "--verify" in sys.argv:
        n = int(sys.argv[sys.argv.index("--verify") + 1])
        verify(n)
    else:
        n = create_issue()
        if n:
            cross_link(n)
            verify(n)
