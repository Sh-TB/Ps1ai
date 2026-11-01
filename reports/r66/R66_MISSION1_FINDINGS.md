# R66 MISSION 1 FINDINGS — the +500 payout, the accumulator, the corridor gate

Round: **R66** · Evidence:
`data/games/SLUS-01212/truck_evidence/r66/` (boot JSONLs + analysis),
`scripts/r66t1_payframe_destarve.py` (the runner),
`scripts/r66_analysis_correct.py` (the offline verdict),
`reports/r66/R66_ACTIVE_EXECUTION_PATH.md` (the product path).

## 1. Experiment discipline (Issue #9 rules, followed)

* Offline contract dry-run BEFORE any experiment boot
  (`scripts/r66_dryrun.py`: 20 checks — the union net, the frame-row
  format, the gate_diag classification, the ledger gate, the disclosed
  goals). One harness defect found and fixed BY the dry-run (the
  ledger patching) plus one disclosed ledger-pollution refund.
* Boot ledger cap 5, disclosed pre-run; 4 boots spent, each with its
  pre-stated purpose; the frontier rebuild disclosed as the capsule
  contingency (the r52 frontiers were lost to the sandbox rollback).
* Oracle unchanged from R52: walker words + verified score gains +
  alive 0x0EE518; never +0x8E in any oracle.

## 2. The corridor gate starvation — ROOT CAUSE (OBSERVED)

The R65 blocker: 11 skips/frontier in R52 with NO diagnostic. R66 pass
A added the per-skip `GATE_DIAG` dump (every live entity + every
rejected candidate + its reason). Result (13 skips on r66_frontier_a):

* the player NEVER advanced (a single px value, 1255.2, across all
  skips) — the protocol only moved ±8 px toward an already-chosen
  target;
* the top corridor blockers were entities that CANNOT absorb a player
  bullet or register a payment:
  - **slot30 st 0xab94** (the bullet-TRANSPARENT wasp; the n=4 R50/R51
    piercing evidence) — 8 rejections;
  - **in-flight `projectile_air` rows** (st 0xbdf8 / 0x1be0 / 0x2950 /
    0x9558 / 0xac64) — the next-highest blockers;
* verdict: the R50/R51 predicate ("no live entity between player and
  target") is WRONG at the semantics layer — the gate starves on
  non-interactive entities. NOT an observer defect, NOT a runtime
  defect, NOT a timeout problem.

**The fix (game-semantic, MSX-owned):** a blocker must be able to
ABSORB the bullet or REGISTER the payment — mortal ground rows only;
corpses, airborne projectiles and the transparent 0xab94 never block;
0xae7c still blocks (it registered kills in R48-R51). Implemented in
`scripts/r66t1_payframe_destarve.py::corridor_occupants_r66` (the
experiment) and `ps1play/adapters/metal_slug_x/policy.py` (the
product policy) with unit tests
(`tests/test_r66_msx_adapter.py::TestCorridorPredicate`).

**Verification:** pass B (the corrected gate + the bounded forward
advance, 180 frames) immediately found targets and captured the +500
the R48-R52 protocol never reached.

## 3. The +500 pay-frame capture (OBSERVED, n=1)

Pass B tap 6: target slot16, st_pre 0x1e38 (a NON-wound-recovery
state), dx +20.3 — **score 7702 → 8202 (+500) at tail frame 1**, the
bullet-impact frame, with the victim still in its pre-hit state; the
0x5b0c death registration arrives at tail f3 and the slot12@0xa0 pulse
(257 → 2, 4-frame recovery — the R52 wound shape, replicated) lands
co-timed with the registration.

* Causal chain established: `bullet impact (tail f1) → score
  accumulator +500 (tail f1) → death registration 0x5b0c (tail f3) →
  registration witness slot12@0xa0 pulse`. The payout PRECEDES the
  visible state transition in EVERY capture this round (also true for
  both +1000s).
* The +500 class is NOT confined to surviving 0x42bc connects (the
  R48-R52 assumption): R66's +500 is a ONE-BULLET KILL from a fresh
  state. The freshness-spread hypothesis is SUPPORTED (every +1000
  came from wound-recovery st_pre 0x42bc/0x3f48/0x2b74; both +500
  observations came from non-recovery states) — not proven.
* The magnitude table updates to **+500 ×4 vs +1000 ×7**
  (`r66_analysis.json::magnitude_table`; R66 added +500 ×1 and
  +1000 ×2 — pass A tap 2 slot20 0x42bc path …→0x5b0c paying at tail
  f3, pass B tap 2 slot20 0x3f48 paying at tail f4 — the R51/R52
  pattern replicated).

## 4. The score accumulator discriminator (the named candidate resolved)

The R52 candidate "slot12 +0xa0 (257→2, rec 4)" is **a REGISTRATION
witness, not a payment discriminator**: the word pulses 257/258/1/2
continuously (zone churn) and dips to 2 co-timed with EVERY kill
registration (replicated n=2 this round). Its INSTANT value at the pay
frame is churn phase — one of the BANKED +1000 pay frames also shows
257, so the zero-overlap property fails on the wider set.

The target-slot pay-frame vectors DO separate this round (19 offsets
with zero overlap, +500 n=1 vs +1000 n=4) but the +500 capture is a
different entity/state class, so identity words dominate — the
discriminator stays **PENDING** until n≥2 +500 captures exist. The
delay signature (+500 at tail f1 vs +1000 at tail f3/f4) is the most
promising lead.

## 5. Kills do not always pay (OBSERVED)

Pass B tap 15: slot30 st 0xa718 → 0xa61c → 0x515c (a one-bullet kill
registration) with **dscore=0**. Payment is not a fixed kill reward —
the accumulator/freshness model stands.

## 6. Honest status ledger

| item | status |
|---|---|
| starvation root cause | OBSERVED (diagnosed from the game, n=13+13 skips) |
| the gate fix | TESTED in-game (pass B captured the +500) |
| the +500 capture at pay-frame granularity | OBSERVED (n=1) |
| the pay-frame discriminator | PENDING (needs n≥2 +500) |
| freshness-spread hypothesis | SUPPORTED, not proven |
| zero-payment kills | OBSERVED (n=1) |
| frontier rebuild determinism | VERIFIED 6-for-6 (px 1224.9/1254.8 byte-exact again) |
| Mission 1 clear | NOT achieved (see R66_GAMEPLAY_RESULTS) |

## 7. The smallest decisive next experiment

Capture n≥2 +500 payments under the SAME pay-frame telemetry (the
corrected gate makes the frontier reachable; pass B already banked
one) and test the delay signature + the 19 candidate offsets against
the widened set. Then point the corrected policy at the truck
encounter (grenade sequencing: hp_a4 300, −100 per grenade, the R38-R52
A/B evidence).
