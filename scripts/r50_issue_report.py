#!/usr/bin/env python3
"""r50_issue_report.py — R50 round report (the 60% track to Issues
#5/#9/#10, the 40%-track round to Issue #6).  Same post+read-back-
verify pattern as r49_issue_report.py.  No new issues opened."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY_5 = """**R50 — the controlled-corridor tap protocol (60% track): the KILL lane is CLEAN for the first time (both +100 payments = the aimed-or-pierced victim, lag 0, zero co-landing ambiguity — n=6 for the class), the controls NEVER pay (movement-inclusive churn baseline), the 0xae7c class is EXONERATED — and a PIERCING discovery: bullets pass through invulnerable-state targets (0xab94) and kill the mortal behind. The connect +500-vs-+1000 magnitude stays unsettled (now 3 vs 3, no discriminator). Boot ledger 2/2 (one DISCLOSED pre-boot-2 cap amendment for a boot-1 runner crash, zero taps fired). Evidence: `data/games/SLUS-01212/truck_evidence/r50/`. No new issues; no game bytes; `+0x8E` never in any oracle.**

## 0. Round conditions (all disclosed)

- **No sandbox rollback**: the R47 frontiers survived on disk (verified pre-boot); cap 1 disclosed pre-run (core+rom load ONLY, restore-only passes).
- **Boot 1 crashed post-restore** at the control-walk record (a runner `NameError`, **zero taps fired**, the world untouched; the partial jsonl preserved). **cap amended 1→2 DISCLOSED BEFORE boot 2** (the r47 boot-2 defect precedent); boot 2 clean, 32 s wall.
- The corridor gate was **strict** (11 gate skips per pass — the spawner zone keeps the lanes occupied); a re-derivation found **1 marginal violation** (an entity entering during the 3f approach — disclosed).

## 1. The verdict (r50_analysis_correct.py — offline, authoritative)

| finding | n | evidence |
|---|---|---|
| **Controls NEVER pay** | 4 windows | zero-input AND movement-only (walk 3f + 20f idle, no Y) all paid **0** while carrying 6+ natural corpses — the churn baseline is now **movement-inclusive**: movement alone provokes nothing |
| **The kill lane is clean** | 2 | both +100 payments co-land **EXACTLY (lag 0)** on registrations at **x 1389.2 / 1349.8** — beyond the spawner cluster, corridor-cleared pre-fire — the first **aimed-or-pierced-victim** kill payments of the campaign; **n=6 across R48/R49/R50** for the +100 registration-locked class |
| **PIERCING discovered** | 1 | the CONNECT tap at a **0xab94-state target** (invulnerable — the bullet passes through) killed the mortal **behind** it (slot18 @1389.2, +100): the corridor gate needs an **invulnerability predicate** |
| **The 0xae7c class EXONERATED** | 2 cycles | slot33 cycled (32/27 frames in-state) with **zero** co-landing payments — the R49 +1000 residual is NOT the 0xae7c kill reward |
| **The connect magnitude UNSETTLED** | 3 vs 3 | **+500 ×3 vs +1000 ×3** across R48/R49/R50, every payment landing **mid-wound-recovery of a SURVIVING target** (0x42bc→0x5b0c, 0x2b74→0x5b0c, 0x3f48→0x5b0c), no state/co-landing discriminator found — the strong class-keyed form stays **falsified** |

- Session ledger **+2700** (a: +1600 = 1000+100+500; b: +1100 = 1000+100).
- Remaining candidates for the magnitude split: an **internal wound accumulator** (a hidden HP word **outside** the bounded R45 net 0x88..0xA8) or a **hit-geometry-dependent damage model**.

## 2. Harness lessons (measured, disclosed)

1. **The corridor gate works but needs an invulnerability predicate** — a "target" in an invulnerable state is not a target: the bullet pierces and the true victim is behind it. States 0xab94 (and the burning family) are bullet-transparent.
2. **The runner-defect amendment discipline held**: boot 1 crashed with zero protocol actions; the cap amendment was disclosed BEFORE boot 2 ran, with the partial jsonl preserved.
3. **Movement-only controls are now mandatory** in every payment round — the movement-inclusive baseline closes the "did the approach pay?" question permanently.

## 3. Capsule + next_experiment

msx capsule +2 events (48 total, provenance-complete). `next_experiment` = **R51**: the wound-accumulator hunt — the extended wide-net (u16 0x60..0x88 + 0xA8..0xE0) on dedicated 1-bullet connect targets, hunting the word whose delta co-moves with the +500-vs-+1000 magnitude; plus the invulnerability census to close the piercing hole. The INTERACTIVE M2 entry remains gated on a deep deaths=0 source (unchanged)."""

BODY_9 = """**R50 addendum (decision loop) — the round's rules: a gate must model the physics it gates (invulnerability pierces); controls must include every input channel the protocol uses.**

Commit at HEAD · evidence `data/games/SLUS-01212/truck_evidence/r50/`; capsule +2 events (48).

1. **A corridor gate that only counts mortals is falsified by the piercing shot** — the bullet passed an invulnerable-state "target" and killed the mortal behind. Rule: **a gate must encode the mechanism's bypass paths, not just its direct path** (the same family as R46's filter-blindness and R48's corpse-blindness).
2. **The movement-only control closed a standing confound**: every earlier round moved the player before firing; nobody had measured movement-without-firing. It pays 0. Rule: **each input channel used by the protocol gets its own zero baseline.**
3. **The magnitude question was protected from force-fitting**: +500 ×3 vs +1000 ×3 with no discriminator stays UNSETTLED — the capsule carries named candidates (a wound accumulator word outside the bounded net / hit-geometry damage), not a verdict. Rule: **a 50/50 split with no covariate is a measurement request, not a classification decision.**
4. The defect discipline held: boot 1's crash (zero taps) was amended into the ledger BEFORE boot 2 — the ledger never counts a boot it cannot account for."""

BODY_10 = """**R50 addendum (knowledge/provenance) — the kill class reaches clean-victim status, the 0xae7c lead is closed, and the piercing hazard enters the knowledge base.**

- **The +100 kill class now has 6/6 lag-0 registration-locked payments** — and for the first time the corridor evidence makes the victim identity unambiguous (x 1389.2 / 1349.8, beyond the spawner cluster). The "aimed vs bullet-victim" distinction from R49 is now measured *positively*, not just by exclusion.
- **The 0xae7c lead is CLOSED as a payment source** (2 cycles, 0 payments) — an open candidate from R49 eliminated by census. The knowledge record shrinks honestly.
- **The piercing hazard is recorded with its state (0xab94)** — future corridor gates and target selectors must treat invulnerable states as bullet-transparent; the R51 round carries the full invulnerability census.
- **The connect magnitude remains an open measurement** (+500 ×3 vs +1000 ×3, no covariate) with the R51 lever pre-registered (the extended wide-net wound-accumulator hunt). Provenance discipline held: the boot-1 crash amendment disclosed same-entry; both capsule events VERIFIED with `{source, evidence}`; the suite green; the push read-back verified; no game bytes; `+0x8E` never in any oracle."""

BODY_6 = """**R50-B — the dominance recipe SCALES to CAP_F 2000 (40% track): arm B (bot_policy8) 1903 / 0 hits / 7-of-7 / caused 2 — the THIRD caused-replication and the FULL ORACLE true for the THIRD consecutive round. Arm A = 1901/0/7/caused 1 = the 8th independent policy5 reproduction, score = f − 99 EXACT. Restore-only arms; boot 1 = core+rom load only (the r47b gs1 checkpoint survived, READ-ONLY); environment re-verified internet-first sha-verified (0 boots); 9 offline policy checks BEFORE the boot; 11.6 s wall. Evidence: `scratch/r50b/`. No new issues; no game bytes; no RAM writes.**

## Arms (1800 → 2000 f, protocol parity)

| arm | frames | score | hits | dodges | caused |
|---|---|---|---|---|---|
| A2000 (control) | 2000 | **1901** | **0** | 7/7 | 1 |
| **B2000 (bot_policy8)** | 2002 | **1903** | **0** | 7/7 | **2** |

## What this decides

- **The third caused-replication**: the decisive pickup again attributes **seek_dur 134** in flower mode (the R48/R49 signature) plus one opportunistic — **commitment remains the caused bottleneck, by name, now across three caps**.
- **Honest notes**: (1) **the score axis BROKE ITS TIE by +2 frames** for the first time (B survived 2002f — 1903 = 2002 − 99 exact; the committed-seek positioning shifted a landing frame; a positioning side-effect, not a mechanism change); (2) **the 8th/9th wasp passes never arrived** (7 passes at 2000f — the capsule's density risk did not materialize at this cap); (3) no margin floor needed (GM 8 safe a fourth time).
- The mechanism table: 1401 @1500f → 1601 @1700f → 1701 @1800f → 1901/1903 @2000f — **score = survival-frames − 99 predicts across four caps**.

## R51 (from the mechanism)

Scale to **CAP_F 2200** (the fourth extension): arm A = policy5 verbatim (the 9th reproduction check), arm B = bot_policy8 — hypothesis: hits 0 AND caused ≥ 2 (the fourth replication) with score ≥ 2101 predicted; the wasp-density risk RE-OPENS with the cap (the 8th pass watch: 6→7→7→7→?). A B hit files the margin floor (the R45-B revert protocol). Offline checks before any boot."""


def main():
    posted = []
    for num, body in ((5, BODY_5), (9, BODY_9), (10, BODY_10),
                      (6, BODY_6)):
        s, r = req(f"/repos/{REPO}/issues/{num}/comments", method="POST",
                   payload={"body": body})
        assert s == 201, (num, s, r)
        n = r["id"]
        s2, got = req(f"/repos/{REPO}/issues/comments/{n}")
        assert s2 == 200 and got["body"] == body, (num, s2)
        posted.append((num, n, len(body)))
        print(f"posted + read-back verified: #{num} comment {n} "
              f"({len(body)} chars)")
    print("ALL POSTED:", posted)


if __name__ == "__main__":
    sys.exit(main())
