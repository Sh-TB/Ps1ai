# Mission 2 MSX Report (Deliverable G, Issue #9 §9)

Concrete source/runtime findings from the six §9 experiment lines, each with the
smallest justified change or the evidenced blocker, and the measured difference from
the previous method.

## A. Combat state correctness — IMPLEMENTED + UNIT_TESTED

`validate_scan()` (contract `ps1play-combat-scan/1`) now checks every entry's
slot/x_px/hp/h/kind ranges, the kind-vs-height invariant (projectile_air iff h>64),
|dx_px| = |x_px−px|, and sort order. `CombatPolicy.decide()` runs a pre-flight:
violations increment `stats["scan_schema_violations"]` and populate
`last_scan_diagnostics` — a malformed scan is a *visible diagnostic event*, never a
silent "area is safe". 7 tests (`tests/test_mission2_scan_schema.py`). No live
violation observed in this session's runs (0 increments) — the contract was already
clean; the guard makes future violations visible.

## B. Vertical targeting — INSTRUMENTATION-LIMITED (negative result recorded)

Probe `msx_vertical_probe.py` (upfire arm vs idle control, same checkpoint): **zero
airborne slots were ever sampled** in either arm — the per-chunk entity scan samples
once per 60 frames while rain shells traverse the h≥200 band in well under one chunk,
and the chopper itself never presented as an aimable slot (its height encoding does
not appear in the +0x7E ground-contact word the scan reads). Both arms died
deterministically at c16 to the rain. Prior contradictory evidence resolved: the
"Y-immune truck" (h=64 = ground contact) never was a vertical-target case; the real
gap is that flyers are invisible at scan granularity. **Next smallest experiment**:
per-frame h-trace of all 39 slots across one chopper phase to locate the chopper's
slot/height encoding, then re-run the upfire burst against a *visible* target.

## C. Projectile detection and evasion — already converged (prior sessions, re-verified)

The two-sighting decreasing-height contract (rev 2) with `FALL_MAX_PER_CHUNK` and
moving-dodge direction remains correct; 24 verified dodges / 0 bogus stand from the
session-4 live series. This session's schema guard (A) additionally classifies
static/rising/first-sighting elevated slots as unverified — never engaged or dodged.

## D. Jump timing — DEFERRED (evidence-based)

The fixed `JUMP_PERIOD` cadence is only reachable in open ground; every death in this
campaign cluster is in the clamp/truck zone where jumping is not the failure mode.
Per §11 (design each trial to answer a specific question) the jump-timing experiment
is scheduled *after* the attrition fix, on the sandbag-row obstacle where jump
decisions are the binding constraint.

## E. Combat verification — IMPLEMENTED + LIVE-TESTED

The `armor_hold` kill follow-through tracks the SAME slot's hp across chunks
(`armor_last_hp`/`armor_no_progress`) and escalates to grenades on verified
no-progress — mirroring the rear_check follow-through semantics. Ineffective-attack
repetition is bounded (budgeted grenade cadence; honest disengagement semantics
inherited from the rear campaign). Live evidence this session: truck hp 340→214 and
294→235 under standing fire in arm B (hits verified), no infinite walk-throughs.

## F. Truck / section transition — ROOT-CAUSED (see Deliverable E)

The one-shot death is **position-dependent**: holding px 950-998 = 0 deaths/5400
frames while the armored wave still approaches into firing range; pressing into the
pin zone died 4/4. The death-loop guard already exists upstream (death-episode
accounting + controller in-place recovery, Task 13); with `armor_hold` the agent
never reaches the fatal pin contact while the truck lives. The section state machine
(scroll word pins 0x048BFFFF, function-pointer flip 0xCA268/0xCA2A0 state 10→1)
remains the traversal blocker AFTER the wave is cleared — unchanged from D7.

## Measured difference vs the previous method

| Metric | Before (session-4/5 method) | This session |
|---|---|---|
| Clamp-zone outcome | one-shot −291 ram, 4/4 passes | **no ram**; attrition-only death, truck chipped 340→214 |
| Time to root cause | unexplained since session 2 (≈3 sessions) | 3 discriminating arms, one session |
| Cost per hypothesis test | full level replay (minutes) | checkpoint arms (5-15 s each) |
| Suite | 406 | 420 passed + 1 xfail (all green) |

## Honest remaining blockers

1. Attrition survival inside `armor_hold` (standing agent eats chip damage).
2. Truck kill confirmation from the hold position (needs a longer hold run).
3. Section-pin traversal (D7) — unchanged, tracked on Issue #5.
4. Vertical targeting instrumentation (per-frame h-trace) — §9-B next step.
