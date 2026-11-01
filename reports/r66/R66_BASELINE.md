# R66 BASELINE — the actual repository and evidence state at round start

Round: **R66** · Date: 2026-11-01 · Mission: *Metal Slug X Mission 1
gameplay breakthrough, runtime validation & knowledge package delivery*.

## 1. Git state (reconciled before any change)

* Remote `origin/main` HEAD at round start: **`4357fce`** (the R65
  follow-up-2 commit; tag `r65` present).
* The sandbox's local checkout was STALE at `6b97fbe` (the Issue-6-era
  round) with a clean working tree; it was fast-forwarded to `4357fce`
  with `git pull --ff-only` (no user changes existed to preserve —
  verified by `git status` before the pull).
* After the reconciliation the tree was clean and byte-identical to the
  remote.

## 2. Environment (this sandbox)

| component | value |
|---|---|
| Python | 3.12.16 |
| numpy / PIL | 2.1.3 / 11.3.0 |
| capstone | MISSING at round start (installed 5.0.9 — the overlay tests import it) |
| onnxruntime | MISSING at round start (installed 1.31.1 CPU — the R62 dependency) |
| core | `mednafen_psx_libretro.so` (beetle PSX 0.9.44.1 df2b53b), sha256 `effff7bb…` |
| firmware | OpenBIOS override (MIT, `third_party/openbios`, md5-verified) — mode recorded, never silent |
| disc | `Metal Slug X (USA).cue/bin` — sha256 `45cde149878fe945…` = the committed pin (verified this round) |

## 3. The R65 release artifacts (verified, not assumed)

* Release `r65` carries `flappybird.ps1game` (1.0.0,
  PARTIAL_AUTONOMOUS_PLAYER), `tetrade.ps1game` (1.1.0),
  `buzzybee.ps1game` (1.0.0), `metal_slug_x.ps1game` (0.1.0,
  INPUT_VERIFIED) + `SHA256SUMS.txt`.
* The R65 suite baseline: **821 passed + 2 skipped + 1 xfailed**;
  release gate 15/15 PASS (historical comparison for Phase 13).

## 4. The surviving evidence tree

* `data/games/SLUS-01212/truck_evidence/r38..r52/` — complete.
* `data/knowledge/msx/capsule.json` — 52 events, complete; its
  `next_experiment` is exactly the R53 lever R66 executed (gate
  diagnostics FIRST, then the +500 capture under pay-frame telemetry).
* The r52 experiment FRONTIER STATES ARE LOST (they lived in the
  gitignored `scratch/r52`, wiped by the sandbox recycle — the FOURTH
  rollback; disclosed in the R66 boot ledger).
* `issue5_m1_start` (Oct 20) SURVIVED in
  `/home/z/my-project/emu/ws/states/` and was RE-VALIDATED by R66 boot 1
  (`data/games/SLUS-01212/truck_evidence/r66/r66_env_probe.json`:
  restores alive at px 258.6, survives 60 idle frames).
* The deterministic frontier rebuild was re-proven for the SIXTH time:
  r66_frontier_a px **1224.9** (census 13) / r66_frontier_b px
  **1254.8** (census 14), 6 deaths / 6 continue-rescues, 48 s push —
  byte-for-byte the R52 numbers across an independent boot and a
  sandbox rollback.

## 5. Open issues ownership (no duplicates created)

| issue | owns the R66 task |
|---|---|
| #4 | Mission-1 clear (the product-path progress + the truck blocker) |
| #5 | the corridor-gate starvation + the +500 pay-frame capture (the master RE task) |
| #6 | architecture (the fourth runtime game registration) |
| #9 | the decision-loop discipline (the offline dry-run rule, the ledger) |
| #10 | the capsule / the accumulator discriminator + the pay-frame law |

## 6. R66 boot ledger (the disclosed authority)

All boots are in `scratch/r66/boots_used.json` (gitignored, mirrored
into the reports). Plan (disclosed pre-run): cap 5. Actual: boot 1 =
`r66_env_probe.py` (environment + checkpoint validation); boot 2 =
stage-1 frontier rebuild; boot 3 = stage-2 pass A (diagnostics);
boot 4 = stage-2 pass B (de-starve). One disclosed ledger-pollution
refund (the offline dry-run harness wrote 2 phantom entries; zero core
loads; harness fixed). The product-path runs (`ps1play play
metal_slug_x`) are runtime runs, not experiment boots — they go through
the engine's own lifecycle and are recorded separately.

## 7. What the baseline did NOT have (the R66 gap)

1. **No MSX runtime adapter at all** — `metal_slug_x` was not
   registered; `play metal_slug_x` failed; the package shipped
   knowledge only (INPUT_VERIFIED).
2. The corridor-gate starvation was UNDIAGNOSED (13+ skips with no
   per-skip dump).
3. The +500 class had ZERO pay-frame captures (magnitude table
   +500 ×3 vs +1000 ×7).
4. No test file covered any MSX runtime path (there was none).
