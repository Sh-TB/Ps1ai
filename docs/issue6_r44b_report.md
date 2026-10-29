# Issue #6 report — R44 (buzzybee, the 40% track): score superiority NEGATIVE

**Round**: R44 · **Track**: 40% (Issue #6) · **Runner**: `scripts/r44b_flower_superiority.py`
**Protocol**: restore-only from the **preserved** R43-B gs1 checkpoint
(`scratch/r43b/state_r43b_gs1.bin`, restore ≠ boot per the r35 precedent;
1 disclosed core+rom load, ledger cap 1/1), 1500 frames per arm, both arms
through the SAME runner (the R43-B `run_arm` verbatim + a bail-shape
capture; no behavior change).

## The lever executed

The R43-B capsule lever: dominance reached, the next step was **score
superiority** — widen the flower seek INTO the guarantee safe phases.
`bot_policy6` keeps `bot_policy5`'s candidate enumeration + guarantee
filter byte-for-byte and changes ONLY the selection among guaranteed
candidates: pick the hold-y **nearest the reachable flower**
(0 < fx ≤ flower_hi) instead of nearest the bee's current y.  The
guarantee filter (whole danger window ex ∈ [−36, 32], 12 px margin) is
untouched, so a flower-seeking hold can never sacrifice safety; the
closed-loop per-frame replanning absorbs model error.  Bail unchanged.

## Result (honest NEGATIVE)

| metric | arm A (bot-A recipe verbatim) | arm B (bot_policy6) |
|---|---|---|
| enemy hits | 2 | **0** |
| dodges | 3/5 | **6/6** |
| score | 1401 | **1401 (TIE — not > A; ≥1500 missed)** |
| caused-pickups | 0 | **1 (< 2 target)** |
| flaps | — | 81 |
| replans / bails | — | 717 / 100 (14%) |

`SCORE_SUPERIOR: false` (hits==0 ✓, score>A ✗, score≥1500 ✗, caused≥2 ✗).
Dominance **stands** (0 hits / 6-of-6 / score ≥ A / caused ≥ A).

## Secondary: the bail geometry is NAMED

0 of 100 bails are full-column sweeps — the shape is **partial-column,
positionable**: a guaranteed exit fails to exist among the enumerated
(side, target) holds while the predicted band does NOT cover the whole
flyable column.  The bail class is a planner-reachability limit, not an
unavoidable geometry.

## Reading

The tie is a **flower-supply limit, not a dodge limit**: the guarantee
filter dominates the dodge-window opportunities — the candidate that
would reach the flower is exactly the one the filter rejects, and the
base pickups (the no-wasp-window flower mode, unchanged) already feed
both arms the same 1401.  Widening the seek *inside* the guarantee
cannot add supply; the reachable set has to grow instead.

## next_experiment (capsule, replaced)

R45 (buzzybee): **seek-timing pre-position + tiered margin** — enter the
no-wasp windows already AT the next flower's y (pre-position during the
dodge tail), and relax the guarantee margin 12 → 8 px ONLY in the
pre-danger frames (t_enter > 20) to widen the reachable set; target
score > 1401 (≥ 1550), hits 0, caused ≥ 2; any hit under the relaxed
tier ⇒ revert to GM 12 and file the margin floor as a finding.

## Discipline

No copyrighted bytes, legal inputs only, no RAM writes; restore-only
(1 disclosed core+rom load); capsule +1 event (CONTRADICTED-class
honest negative) + next_experiment replaced; metrics + frames JSONL in
`scratch/r44b/` (synced to `scratch/r35b`).
