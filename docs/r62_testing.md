# R62 Testing Guide

## The layered suite (mission Section 12)

```
tests/test_r62_runtime.py      A unit + B adapter + C policy +
                               D controller + G fault injection +
                               the second-game example   (offline, 50 tests)
tests/test_r62_integration.py  E emulator + F full-loop byte-match
                               (real emulator, ~90 s, skips honestly
                               without assets)
tests/test_r62_cli.py          the one-command UX + exit codes
tests/… (pre-existing)         the complete R61 regression suite
```

Run everything:

```bash
python3 -m pytest tests/ -q
```

Current status at the R62 head: **731 passed + 1 xfailed**
(R61 baseline 668+1 preserved; 63 new R62 tests, zero regressions,
zero weakened tests, zero new skips).

## What each layer proves

- **A unit** — config validation (fail-early, safety caps, the
  no-unbounded-run rule), the lifecycle state machine (illegal
  transitions raise), the restart policy (episode/time/failure
  caps), telemetry ordering + idempotent close, error exit codes.
- **B adapter** — frame→observation contract: shape/dtype/finiteness,
  sentinels-are-valid (no pipe / no bird are DATA, not errors),
  invalid frames never reach the policy, exact history-update
  semantics, reset drops everything, terminal detection.
- **C policy** — authority-manifest hash check, invalid-observation
  rejection, out-of-contract vector rejection, wrong-model rejection.
- **D controller** — legal mapping, one-frame advances, duplicate
  sends rejected, stop latch, release-all behavior.
- **E emulator** — real boot, ordered capture, the staleness flag,
  input→frame progression, cleanup + same-process re-boot.
- **F full loop** — the decisive test: TWO consecutive REAL episodes
  through the engine+adapter+frozen policy BYTE-MATCH the R61 k=45
  family record (40 pipes @ 4753 frames, identical `trace_sha256`) —
  the new runtime is behavior-identical to the R61 verified path.
- **G fault injection** — capture death, policy explosion, emergency
  stop mid-episode, close idempotence, missing ISO, wrong ISO hash,
  cue→image resolution — all typed, all persisted, all cleaned up.
- **Second-game example** — `ScriptedGameAdapter` (3 features, A/B
  buttons) driven by the REAL engine loop to terminal + identical
  traces across episodes: the core is game-agnostic.

## The release gate (the always-current proof)

```bash
python3 -m ps1play verify --profile final
```

15 gates, machine-readable JSON at `reports/r62_release_gate.json`
(+ `.log`), nonzero exit on any required failure. It re-runs the
offline contract gates, a REAL k=30 episode byte-matched to R61,
THREE consecutive REAL episodes byte-matched to R61, the full pytest
suite, the documented CLI commands, and the clean-room install.

## Skips policy

The only skips are environment-honest: emulator-asset absence
(runs on every machine this project uses) and the owner-local exe
test inherited from R61. Failures are NEVER converted to skips.
