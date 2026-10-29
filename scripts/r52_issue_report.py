#!/usr/bin/env python3
"""r52_issue_report.py — R52 round report (the 60% track to Issues
#5/#9/#10, the 40%-track round to Issue #6).  Same post+read-back-
verify pattern as r51_issue_report.py.  No new issues opened."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY_5 = """**R52 — the pay-frame union-net wound hunt (60% track): the pay-frame telemetry lever is ARMED AND PROVEN (11 offline contract checks before the first capture boot), two MORE +1000 connects captured AT the pay frame (the magnitude table now +500 ×3 vs +1000 ×7 across R48–R52), the PIERCING mechanism replicated again (n=2, total n=4) — and the honest shortfall: the +500 class was NOT captured (the corridor gate starved), so the pay-frame discriminator stays PENDING. Boot ledger 4/4: the THIRD sandbox rollback disclosed (scratch/ reset — the r47 frontiers LOST, `issue5_m1_start` SURVIVED), the frontier rebuild deterministic for the 5th time (px 1224.9 / 1254.8, 6/6 tainted), THREE disclosed ZERO-TAP runner-code defect amendments + two refunded phantom ledger entries, an offline contract dry-run proving the telemetry path before boot 4. Evidence: `data/games/SLUS-01212/truck_evidence/r52/`. No new issues; no game bytes; `+0x8E` never in any oracle.**

## 0. Round conditions (all disclosed)

- **THIRD sandbox rollback**: the sandbox reset `scratch/` — the r47_frontier_a/b states and the r47b gs1 checkpoint are LOST (never committed — no-game-bytes). The session-5 anchor `issue5_m1_start` (Oct 20) SURVIVED (verified pre-run). The capsule contingency applied verbatim: cap 2 disclosed pre-run (boot 1 = the tainted frontier rebuild, boot 2 = the experiment).
- **Stage 1 reproduced the frontiers deterministically for the 5th time**: `r52_frontier_a` px **1224.9** census 13, `r52_frontier_b` px **1254.8** census 14 — the same postures as R45/R47, restore score 6702, 6 deaths / 6 continue-rescues counted, TAINTED lineage (48 s wall).
- **Three defect amendments, all disclosed, all ZERO-TAP runner-code defects** (the protocol never fired a bullet in them): boot 2 crashed at the first CONNECT pick (the hunt rows dropped the R48 `direct` key the R50 helpers read) → cap 2→3; boot 3 crashed in the control walk (a missing import, same family) → cap 3→4 with the **offline contract dry-run (`r52_dryrun.py`) passing ALL 11 checks BEFORE boot 4 was spent** (the r51 gate-dry-run precedent applied to the telemetry layer). Two phantom ledger entries (cap-check crashes that incremented AFTER the check) were REFUNDED disclosed and the cap gate moved BEFORE the increment — the phantom-entry class is eliminated. Boot 4 clean.
- **The R52 lever (disclosed pre-run)**: `frame_walk_hunt` records the union-net u16 states (0x60..0xE0, 65 offsets) for every live slot EVERY frame of the tap+flight window — rows are a strict superset of the R48 format (the R48–R51 joins stay intact).

## 1. The verdict (r52_analysis_correct.py — offline, authoritative)

| finding | n | evidence |
|---|---|---|
| **Two MORE +1000 connects, captured AT the pay frame** | 2 | slot20 st_pre **0x42bc** (path 0x42bc→0x17f8→0x4008→0x3f48→0x5b0c, pay f_rel 3) AND st_pre **0x3f48** (path 0x3f48→0x5b0c, pay f_rel 4) — the R51 +1000 family REPLICATED under pay-frame telemetry |
| **PIERCING replicated again** | 2 (total 4) | both 0xab94-state slot30 taps paid **+100** with the transparent target NEVER reacting (state path returns to 0xab94; no 0x42bc entry); no corpse in-window — the victim is beyond the 60px window |
| **Controls NEVER pay** | 6 windows | zero-input AND movement-only all **0** — the movement-inclusive churn baseline, FIFTH round |
| **The pay-frame candidate pool** | 123 | the two +1000 pay-frame word vectors DIFFER in 123 slot/offsets — the pool the +500 contrast will filter (committed: `r52_wound_table.json`) |
| **The wound-shape batch** | 546 raw | incl. **slot12 +0xa0 257→2 with 4-frame recovery** (the closest accumulator signature); the camera-churn families (0x8c/0x94) and 1-tick countdowns dominate the rest |
| **HONEST SHORTFALL** | — | the **+500 class was NOT captured**: the corridor gate starved (11 skips per frontier) and the wall guard ended both passes before a +500 connect or a KILL landed → **the +500-vs-+1000 pay-frame discriminator stays PENDING** |

- Session ledger **+2200** (a: +1100 = 1000+100; b: +1100 = 1000+100). Magnitude: **+500 ×3 vs +1000 ×7 across R48–R52**.

## 2. Harness lessons (measured, disclosed)

1. **New telemetry layers get the dry-run treatment**: two boots were spent proving the same defect family (row-contract breaks) that a 30-second offline mock test would have caught — the contract dry-run is now a pre-boot gate for any telemetry change.
2. **Ledger counting must be atomic with the boot**: a cap check after the increment creates phantom entries; the gate now fires before the increment and over-cap calls consume nothing.
3. **The frontier rebuild determinism held through a third rollback** — the tainted-lineage pipeline reproduces px 1224.9/1254.8 exactly, five for five.

## 3. Capsule + next_experiment

msx capsule +2 events (52 total, provenance-complete). `next_experiment` = **R53**: gate diagnostics first (per-skip blocking-occupant dump — the R52 starvation is undiagnosed), then the **+500 capture under the same pay-frame telemetry** with a freshness spread (fresh 0x4054 soft targets paid +500 in R48; the wound-state family paid +1000 in R50–R52 — freshness is the discriminator candidate), then the zero-overlap discriminator test; the slot12 +0xa0 shape is the named accumulator candidate to test first. The INTERACTIVE M2 entry remains gated on a deep deaths=0 source (unchanged)."""

BODY_9 = """**R52 addendum (decision loop) — the rules the round added: telemetry changes earn their boot offline; ledger counting is atomic with the boot; determinism survives rollbacks.**

Commit at HEAD · evidence `data/games/SLUS-01212/truck_evidence/r52/`; capsule +2 events (52).

1. **The contract dry-run extends from gates to telemetry**: R51 proved a repaired gate offline before re-booting; R52 spent two boots discovering the same rule applies to NEW TELEMETRY LAYERS (row-contract breaks invisible until the helpers read them). Rule: **any new recording layer proves its row contract against a mock before a boot is spent.**
2. **Ledger atomicity**: two phantom entries were created by cap checks that ran after the increment. Rule: **a boot ledger entry is consumed only by a core load** — the gate moved before the increment, over-cap calls now consume nothing.
3. **Determinism dividend, third rollback**: the tainted frontier rebuild reproduced px 1224.9/1254.8 exactly (five for five across R45/R47/R52 + the rollbacks between). The rebuild protocol is a stable instrument, not a one-off.
4. The defect discipline held: three amendments disclosed same-entry, zero unaccounted boots, the partials preserved, the refunds disclosed."""

BODY_10 = """**R52 addendum (knowledge/provenance) — the +1000 family replicated under pay-frame telemetry, the piercing class reaches n=4, the magnitude table 3-vs-7, and the discriminator waits on a +500 capture.**

- **The pay-frame method delivered its first captures**: the two +1000 connects' full 65-offset word vectors at the exact pay frames are committed (`r52_wound_table.json`) — the 123-word cross-connect difference pool is the discriminator's raw material.
- **The piercing mechanism is now n=4** (two more 0xab94 taps, zero reactions, +100 paid, victims beyond the window) — the invulnerability predicate in the corridor gate is settled knowledge.
- **The magnitude table is now +500 ×3 vs +1000 ×7 across R48–R52**; the R52 pair confirmed the R51 finding (0x42bc and 0x3f48 pre-states both +1000) and the state paths converge on 0x5b0c mid-wound-recovery — the wound accumulator remains the live hypothesis, now with a NAMED candidate (slot12 +0xa0, 257→2, 4-frame recovery) to test first.
- Provenance discipline held: the rollback disclosed, three zero-tap defect amendments disclosed same-entry, two phantom refunds disclosed, the offline dry-run preceded the capture boot, both capsule events carry `{source, evidence}`; no game bytes; `+0x8E` never in any oracle."""

BODY_6 = """**R52-B — the dominance recipe SCALES to CAP_F 2400 (40% track) under the THIRD sandbox rollback: score = f − 99 EXACT across the SIXTH cap (2301 = 2400 − 99 in all three arms), THE 9TH PASS ARRIVED — and the HONEST headline: the five-round hits-zero streak BROKE (both arms took 1 hit at the SAME deterministic wave), the FULL ORACLE FALSE for the first time in five rounds, the margin floor FILED (GM 8 AND GM 12 both hit). Boot 1 = core+rom load AND the gs1 checkpoint REBUILD (disclosed: the r47b checkpoint lost to the rollback; the r45b/r42b pattern verbatim); environment re-verified internet-first sha-verified 0 boots (EXE 9b0bfc08 byte-identical, disc 042b94bb byte-identical — rebuilt by r30t0 after the rollback); 9 offline policy checks BEFORE the boot; 23.1 s wall. Evidence: `scratch/r52b/`. No new issues; no game bytes; no RAM writes.**

## Arms (2200 → 2400 f, protocol parity)

| arm | frames | score | hits | dodges | caused |
|---|---|---|---|---|---|
| A2400 (control) | 2400 | **2301** | **1** | 8/8 | 1 |
| **B2400 (bot_policy8)** | 2400 | **2301** | **1** | 8/8 | **2** |
| B2400_r (tier 12/12, on the B hit) | 2400 | **2301** | **1** | 8/8 | 3 |

## What this decides

- **The 9th pass arrived in ALL arms** (6 @1500 → 7 @1700 → 7 @1800 → 7 @2000 → 8 @2200 → 9 @2400) — the density watch paid off a sixth time.
- **THE MECHANISM OF THE STREAK BREAK**: both hits land at **f_since_pass_start = 112** on the same deterministic wasp wave (e=[32, 31, 3]; A from above, B/B2 from below; `planned: false` — a reflex dodge cannot clear it). The wave is **pass-boundary-locked, not margin-locked**: GM 8 hit, GM 12 hit — the margin axis cannot fix a phase problem.
- **Honest notes**: (1) the FIFTH caused-replication held (B caused 2, B2 caused 3) — the dominance (caused) axis is intact; (2) score = f − 99 survived the sixth cap; (3) the commitment signature visible again (seek_dur 134 + 8 + 4).

## R53 (from the mechanism)

The **wave-phase pre-position**: a predictor in bot_policy8 that reads the pass-boundary phase and pre-positions the bee BEFORE the wave frame (the R45-B pre-position lever returns with a wave-phase input). Hypothesis: hits 0 AND caused ≥ 2 @2400 (the sixth caused-replication), score ≥ 2301 predicted. The control experiment: if the wave is phase-locked to the pass counter rather than the planner, the hit recurs at the same relative frame in ALL arms — the phase table decides. Offline checks before any boot."""

def main():
    posted = []
    for num, body in ((5, BODY_5), (9, BODY_9), (10, BODY_10),
                      (6, BODY_6)):
        s, r = req(f"/repos/{REPO}/issues/{num}/comments",
                   method="POST", payload={"body": body})
        assert s == 201, (num, s, r)
        n = r["id"]
        s2, got = req(f"/repos/{REPO}/issues/comments/{n}")
        assert s2 == 200 and got["body"] == body, (num, s2)
        posted.append((num, n, len(body)))
        print(f"posted + read-back verified: #{num} comment {n} "
              f"({len(body)} chars)")
    print("ALL POSTED:", posted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
