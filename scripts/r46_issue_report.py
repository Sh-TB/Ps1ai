#!/usr/bin/env python3
"""r46_issue_report.py — R46 round report (the 60% track to Issues
#5/#9/#10, the 40%-track round to Issue #6).  Same post+read-back-
verify pattern as r45_issue_report.py.  No new issues opened (the
standing constraint)."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY_5 = """**R46 — the one-hit replication round (60% track, Issues #5/#9/#10). Boot cap 1/1, restore-only from the SAVED r45 frontiers (verified on disk pre-boot — the R45 rollback watch). The in-runner verdict was WITHDRAWN same-round by the offline corrected analysis (corrected-filings precedent); the corrected reading below. Evidence: `data/games/SLUS-01212/truck_evidence/r46/`. No new issues; no game bytes; `+0x8E` never in any oracle.**

## 1. Execution (31 s wall, one boot, two restore-only passes)

- restore `r45_frontier_b` (px 1254.8 — the ground-only census holds **2**; the R45 13-entity census was mostly airborne shells) → zero-input control tap → ground-only aimed taps (`kind=='enemy'` — the R45 protocol note applied);
- restore `r45_frontier_a` in the same boot → same protocol; 34 taps total.

## 2. The corrected verdict — the slot-20 signature REPLICATES 3/3; the class-wide reading stays UNPROVEN

The in-runner kill table printed **REFUTED** — **withdrawn** by `r46_analysis_correct.py` (no boot): the verdict had counted **position churn** as HP chip (0x8C/0x94/0x8E/0x96 move even in the zero-input control tap) and ignored the attribution evidence.

**What survives (VERIFIED)**: the slot-20 soft soldier died with the **flat +100 at the death tap** in **ALL THREE readouts** (R45-a tap 2, R46-b tap 2, R46-a tap 2 — two rounds, three boots) with **NO 0x9E/0xA4 movement while alive** and no decrementing word anywhere in 0x88..0xA8. The one-hit **signature** is deterministic.

**What does not (UNPROVEN)**: the ≥ 3 **distinct-kill** bar was not met — the frontier worlds hold ~2 ground soldiers each, and the second soldier died with **dscore 0** (R45 tap 11 killed TWO ground entities with +0 = the **environmental-kill signature**, likely falling-shell ground bursts crediting nothing). Score events also include **+100 with NO tracked death** (R45 taps 3/9) and deaths with NO score — score-to-death attribution remains the open problem, and it is exactly what keeps the HP-word hunt un-closable.

## 3. Harness lessons (measured, disclosed)

1. **The wreck/fire filter (0xA44C only) missed the evolved burning states** `0xa264`/`0xa414` — a landed shell burns on the ground and passes the ground filter: **12/16 frontier_b taps were wasted on an unkillable ground fire** (dscore 0 ×12).
2. **The ground-only census filter over-pruned**: it discarded the air-corpse evidence that attributes the first-tap +500/+1000 events (R45's full census shows slots 33+23 entering the `0x4be4` corpse state exactly at the +500 tap — the +500 is air kills, NOT damage to the targeted soldier).
3. **The st word is a STATE HANDLER, not identity**: the same soldier reads `0x4054`/`0x42bc`/`0x5b0c`/`0x6730` across taps — class labels must use the pre-death row.
4. **Churn is not chip**: any verdict that treats wide-net movement as damage without the zero-input control baseline is invalid.

## 4. Capsule + next_experiment

msx capsule +2 events (40 total): the execution + the corrected verdict (both VERIFIED, provenance-complete). `next_experiment` = **R47**: the **single-bullet tap protocol** (TAP_FRAMES ≈ 3 ≈ one bullet/tap) with a **FULL-kind census per tap** (air included — the R46 ground-only filter discarded the attribution evidence), restore-only cap 1: if bullet CONNECTS pay +100 each (surviving hits included), the "one-hit" reading is reclassified as **PER-HIT SCORING** (the two models agree at the death tap and diverge on surviving hits); if connects score 0 and only the death pays +100, the one-hit reading stands. The INTERACTIVE M2 entry remains gated on a deep deaths=0 source (unchanged)."""

BODY_9 = """**R46 addendum (decision loop) — the verdict pipeline earned two rules: the control baseline outranks the delta table, and the target filter is part of the probe's validity.**

Commit at HEAD · evidence `data/games/SLUS-01212/truck_evidence/r46/`; capsule +2 events (40).

1. **The in-runner verdict was wrong and the offline correction caught it — the pipeline worked as designed, but late.** The kill table counted wide-net word movement as "chip"; the zero-input control tap (which shows the same words moving with NO input) was already in the data and would have falsified the chip reading automatically. Rule going forward: **any delta-based verdict must first subtract the control-tap baseline** — churn words are identified by the control, not by intuition.
2. **The ground-only filter (applied per the R45 protocol note) removed the evidence needed to attribute the +500/+1000 events.** The R45 full-kind census is what proved the +500 = air kills. Rule: **a filter that shrinks the target set must not shrink the RECORDING set** — record all kinds, act on the filtered subset.
3. **The st word is a state handler, not an identity** — the same soldier cycled 0x4054→0x42bc→0x5b0c across three taps. Identity claims in kill tables must anchor on the pre-death row plus the corpse transition, never on a mid-tap state read.
4. The R47 protocol already encodes all three rules: single-bullet taps, full-kind recording, control-baseline subtraction."""

BODY_10 = """**R46 addendum (knowledge/provenance) — a same-round verdict withdrawal executed per the corrected-filings precedent; the capsule event carries the correction chain end-to-end.**

- The in-runner kill table printed **REFUTED**; `r46_analysis_correct.py` (offline, **no boot**) rebuilt the kill table from the committed jsonl + the R45 jsonl as the attribution key and **withdrew** the verdict: position churn (words that move in the zero-input control tap) had been counted as HP damage, and the R45 air-corpse evidence (slots 33+23 corpse at the +500 tap) attributes the confound events.
- The boot ledger entry 1 carries the same-entry `outcome_corrected` amendment (fourth round running); the corrected table is committed evidence (`truck_evidence/r46/corrected_kill_table.json`) with the rules inline (death = corpse transition; candidates = 0x9E/0xA4 only; attribution = the R45 corpse key).
- Capsule discipline held: both new events are VERIFIED with provenance `{source, evidence}` non-empty (the schema validator passes; the suite is green at 611 + 1 xfail).
- The knowledge record now distinguishes three things it previously conflated: the **death-tap signature** (flat +100, replicated 3/3, deterministic), the **class-wide one-hit claim** (unproven — the ≥ 3 distinct-kill bar failed), and **score attribution** (open — +100-no-death and death-no-score events exist). R47's single-bullet protocol is designed to separate the remaining two."""

BODY_6 = """**R46-B — the score mechanism is TIME: every delta is +1/frame (40% track). Restore-only, the preserved r45b gs1 checkpoint READ-ONLY; boot ledger cap amended 1→2 disclosed (boot 1 = operator shell-timeout kill at f≈268, runner healthy; the re-run's one-boot timing probe measured 407 fps — the slowness never reproduced). Report: `docs/issue6_r46b_report.md`. Evidence: `scratch/r46b/`. No new issues; no game bytes; no RAM writes.**

## The mechanism — PER_FRAME_TIME

Per-frame u32 reads at `0x8005883C` for one `bot_policy5` arm (1500 f, the R45-B arm-A protocol verbatim):

| quantity | value |
|---|---|
| score 0 → 1401 | **1401 delta frames, ALL +1, zero jumps** |
| non-climb windows | one 32 f ready phase at the start |
| 6 wasp passes (0 hits) | **contribute 0 score** |
| 2 flower pickups (+997 HP ×2, 1 caused) | **contribute 0 score** |

The **1401 invariant across four policy families** (A recipe, policy5, policy6, policy7) is now EXPLAINED: the score is **survival time** (the climb-frame count of the 1500 f window), not a reward structure and not a policy deficit. The r23 manifest note ("+1/frame during play") is measured end-to-end.

**Determinism**: the exact policy5 line (score 1401 / hp 5666 / 6 passes / 0 hits) reproduced for the **third independent time** across processes (R43-B arm B, R45-B arm A, R46-T) — cross-process restore determinism re-confirmed.

## The R47 lever (from the mechanism, not from another policy variant)

Score is time ⇒ ≥ 1550 = **survive the climb past ~1550 frames**: `bot_policy5` verbatim at `CAP_F 1700` (extend to 1800 only if 1700 finishes with 0 hits), restore-only, cap 1, the oracle line unchanged (score ≥ 1550 AND hits 0 AND caused ≥ 2). The real risk is **late-game wasp density vs the guarantee planner** — the first hit past the 1500 f frontier would be the finding."""


def main():
    posted = []
    for num, body in ((5, BODY_5), (9, BODY_9), (10, BODY_10),
                      (6, BODY_6)):
        s, r = req(f"/repos/{REPO}/issues/{num}/comments", method="POST",
                   payload={"body": body})
        assert s == 201, (num, s, r)
        n = r["number"]
        s2, got = req(f"/repos/{REPO}/issues/comments/{n}")
        assert s2 == 200 and got["body"] == body, (num, s2)
        posted.append((num, n, len(body)))
        print(f"posted + read-back verified: #{num} comment {n} "
              f"({len(body)} chars)")
    print("ALL POSTED:", posted)


if __name__ == "__main__":
    main()
