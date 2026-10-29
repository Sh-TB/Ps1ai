#!/usr/bin/env python3
"""r51_issue_report.py — R51 round report (the 60% track to Issues
#5/#9/#10, the 40%-track round to Issue #6).  Same post+read-back-
verify pattern as r50_issue_report.py.  No new issues opened."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY_5 = """**R51 — the wound-accumulator hunt (60% track): the PIERCING mechanism is frame-exact REPLICATED n=2 in one round (the 0xab94 target never reacts; the +100 co-lands lag-0 on the mortal BEHIND — slot18 @1357.2, KILL_REG), two MORE +1000 connects (the magnitude table is now +500 ×3 vs +1000 ×5 across R48–R51), the wound-word hunt is NEGATIVE at tap-window granularity (no separating word in the union net 0x60..0xE0 — the pay-frame method is the R52 lever). Boot ledger 3/3 (TWO disclosed gate-defect amendments, zero bullets in boots 1–2; an offline gate dry-run proved taps flow before boot 3 was spent). Evidence: `data/games/SLUS-01212/truck_evidence/r51/`. No new issues; no game bytes; `+0x8E` never in any oracle.**

## 0. Round conditions (all disclosed)

- **No sandbox rollback**: the R47 frontiers survived on disk (verified pre-boot); cap 1 disclosed pre-run (core+rom load ONLY, restore-only passes).
- **The word net was widened pre-run (disclosed)**: `read_words` now reads the union `0x60..0xE0` even (the R48 bounded net + the capsule's extended net 0x60..0x88 + 0xA8..0xE0 = 65 offsets).
- **Two gate-defect amendments, both DISCLOSED, zero unaccounted boots**: boot 1 (29 s wall) and boot 2 (29 s wall) both STARVED — the +60 px beyond-margin first put every candidate inside its own corridor, then still blocked MORTAL targets (the bullet is absorbed by a mortal target; only a TRANSPARENT target continues). **cap 1→2→3 DISCLOSED**, and before boot 3 an **offline gate dry-run** (`r51_gate_dryrun.py`) replayed the boot-2 census through the fixed gate and PROVED taps flow (CONNECT/KILL admitted on both frontiers). Boot 3 clean, 30 s wall, ledger 3/3.
- **Gate lesson (the R50 gate-physics rule, applied twice)**: the corridor extends BEYOND the target **only** for a bullet-transparent target.

## 1. The verdict (r51_analysis_correct.py — offline, authoritative)

| finding | n | evidence |
|---|---|---|
| **PIERCING replicated** | 2 | both PIERCE taps (0xab94-state slot30) paid **+100** with the transparent target **never reacting**; pass-a's +100 co-lands **lag-0** on slot18's 0x515c registration at **x 1357.2 behind** the transparent slot (class KILL_REG, holder_invul=30 at the pay frame) |
| **Controls NEVER pay** | 4 windows | zero-input AND movement-only all **0** — the movement-inclusive churn baseline replicated a fourth round |
| **Two MORE +1000 connects** | 2 | slot20 st_pre **0x42bc** AND st_pre **0x3f48** both paid +1000 (deterministic across both frontiers: a +1100, b +1100) — the 0x42bc entry state alone is **NOT** the discriminator (the same entry paid +500 in R48/R49) |
| **Wound-word hunt NEGATIVE (tap-window)** | 100+ candidates | the union-net delta intersection holds 100+ words (walk/animation churn fills the window); the bounded-net cross-join vs R50 shows **no separating word** (the +500 shares 5 candidates, the +1000s share 51) |
| **The 0xae7c exonerated status holds** | 2 registrations | zero co-landing payments again; the invul census recorded 4 dwell entries (0xab94/0xae7c) |

- Session ledger **+2200** (a: +1100 = 1000+100; b: +1100 = 1000+100).

## 2. Harness lessons (measured, disclosed)

1. **A gate predicate must distinguish what the projectile sees**: mortal = absorb, transparent = pass-through. Applying the pass-through corridor to mortal targets starves the gate (measured twice, cheaply, and proven offline before the third boot).
2. **The offline dry-run before a boot is now the standard**: the boot-2 census replayed through the fixed gate predicted boot-3 behavior exactly.
3. **Tap-window word deltas are too coarse for the accumulator hunt** — the window churn drowns the signal; the discriminator must be read AT the pay frame (the frame-exact method that settled the payment classes in R48).

## 3. Capsule + next_experiment

msx capsule +2 events (50 total, provenance-complete). `next_experiment` = **R52**: the FRAME-EXACT union-net wound hunt — per-frame u16 reads (0x60..0xE0, slots 1..39) across the tap+flight window on dedicated connects; the discriminator test runs on the **pay-frame word state** (any word whose pay-frame value separates +500 from +1000 with zero overlap) → the magnitude model refined to payment = f(wound_state). The INTERACTIVE M2 entry remains gated on a deep deaths=0 source (unchanged)."""

BODY_9 = """**R51 addendum (decision loop) — the round's rules: the gate models what the projectile sees (absorb vs pass-through); a boot is never spent without an offline dry-run proving the gate admits actions; window deltas are not pay-frame state.**

Commit at HEAD · evidence `data/games/SLUS-01212/truck_evidence/r51/`; capsule +2 events (50).

1. **The gate-physics rule got its second clause**: R50 said "a gate must model the physics it gates" (invulnerability pierces). R51 measured the converse failure: applying the pass-through corridor to MORTAL targets starves the gate (two boots, zero bullets). Rule: **the corridor extends beyond the target only for the class of target the bullet actually passes through.**
2. **The offline dry-run gate-proof**: before boot 3, the recorded boot-2 census was replayed through the fixed gate offline (`r51_gate_dryrun.py`) and taps were PROVEN to flow. Rule: **a repaired gate earns its boot by replaying the failure's own data first** — the cheapest possible falsification before spending budget.
3. **Window granularity falsified for the accumulator hunt**: the union-net pre/post delta intersection holds 100+ words (churn) and separates nothing. Rule: **a co-mover claimed from a window must survive the pay-frame test** — the R52 lever reads the word state AT the registration frame, the same frame-exact discipline that settled the payment classes in R48.
4. The defect discipline held again: two starved boots, two same-entry disclosed amendments, the partials preserved, and the ledger never counted a bullet that was not fired."""

BODY_10 = """**R51 addendum (knowledge/provenance) — the piercing class is frame-exact knowledge, the magnitude table grows to 3-vs-5, and the accumulator hunt moves to the pay frame.**

- **The piercing mechanism is now measured twice in one round** (a + b, both +100, the 0xab94 target never reacting, the behind-mortal's 0x515c registration co-landing lag-0 at x 1357.2): the knowledge record upgrades "discovery" to "replicated mechanism" — invulnerable-state targets are bullet-transparent and the corridor gate carries the predicate.
- **The connect magnitude table is now +500 ×3 vs +1000 ×5 across R48–R51**, with the 0x42bc entry state itself split across both magnitudes — the state-keyed form is dead; the live hypothesis is the wound accumulator, now hunted AT the pay frame (the tap-window method measured NEGATIVE and was closed honestly).
- **The 0xae7c exonerated status holds** (2 more registrations, 0 payments); the invul census (4 dwell entries) enters the knowledge base with the round's jsonl.
- Provenance discipline held: two defect amendments disclosed same-entry; an offline dry-run preceded the third boot; both capsule events VERIFIED with `{source, evidence}`; no game bytes; `+0x8E` never in any oracle."""

BODY_6 = """**R51-B — the dominance recipe SCALES to CAP_F 2200 (40% track): arm B (bot_policy8) 2101 / 0 hits / 8-of-8 / caused 2 — the FOURTH caused-replication and the FULL ORACLE true for the FOURTH consecutive round, score = f − 99 EXACT. Arm A = 2102/0/8/caused 1 = the 9th independent policy5 reproduction — AND THE 8TH PASS FINALLY ARRIVED (the density watch paid off). Restore-only arms; boot 1 = core+rom load only (the r47b gs1 checkpoint survived, READ-ONLY); environment re-verified internet-first sha-verified (0 boots); 9 offline policy checks BEFORE the boot; 12.8 s wall. Evidence: `scratch/r51b/`. No new issues; no game bytes; no RAM writes.**

## Arms (2000 → 2200 f, protocol parity)

| arm | frames | score | hits | dodges | caused |
|---|---|---|---|---|---|
| A2200 (control) | 2201 | **2102** | **0** | 8/8 | 1 |
| **B2200 (bot_policy8)** | 2200 | **2101** | **0** | 8/8 | **2** |

## What this decides

- **The 8th pass arrived in BOTH arms** (6 @1500 → 7 @1700 → 7 @1800 → 7 @2000 → 8 @2200) — the capsule's wasp-density question resolved exactly as the cap scaled.
- **The commitment mechanism visible again**: the decisive pickup attributes **seek_dur 134** in flower mode (the R48/R49 signature) plus one seek_dur 8 — commitment remains the caused bottleneck, now across four caps.
- **Honest notes**: (1) **the score tie is RESTORED** (A 2102 vs B 2101 — the R50 +2 B-edge did NOT replicate; the positioning side-effect label holds); (2) no margin floor (B took 0 hits, **GM 8 safe a FIFTH time**); (3) the score = f − 99 prediction is EXACT in both arms (2201−99=2102, 2200−99=2101).
- The mechanism table: 1401 @1500f → 1601 @1700f → 1701 @1800f → 1901/1903 @2000f → 2102/2101 @2200f — **score = survival-frames − 99 predicts across five caps**.

## R52 (from the mechanism)

Scale to **CAP_F 2400** (the fifth extension): arm A = policy5 verbatim (the 10th reproduction check), arm B = bot_policy8 — hypothesis: hits 0 AND caused ≥ 2 (the fifth replication) with score ≥ 2301 predicted; the 9th-pass density watch continues (8 → ? @2400). A B hit files the margin floor (the R45-B revert protocol). Offline checks before any boot."""


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
