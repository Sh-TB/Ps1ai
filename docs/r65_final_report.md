# R65 Final Report — the universal PS1 game platform

Round: **R65** · Base `c449819` · Date 2026-11-01 · Gate **15/15 PASS** ·
Suite **821 passed + 2 skipped + 1 xfailed** (baseline 782+2+1 preserved).

## 1. Executive summary

R65 turns PS1Play from "one runtime, two games" into the platform the
mission asked for: **every game owns an isolated, downloadable knowledge
package** (`.ps1game`), the runtime drives **three** games, the Tetrade
policy got its evidence-backed gameplay fix (a **~24× improvement**), and
the primary Metal Slug X objective keeps its honest OPEN status with the
knowledge made distributable. Zero memory writes anywhere; the R61
champion untouched; training stays closed; no issue closed; no duplicate
issues; no claim without a verified artifact.

## 2. Part-by-part

* **A — Audit** (`docs/r65_baseline_audit.md`): the five open issues
  (#4/#5/#6/#9/#10) audited against their latest comments; every R52
  outstanding item preserved; three pieces of stale evidence identified
  (the pad-defect diagnosis; the BuzzyBee score-cap UNKNOWN — resolved
  by this round's measurement; the Tetrade placement model — corrected).
* **B — Packages** (`ps1play/knowledge/package.py` + CLI): the
  `.ps1game` format with hash-pinned manifests, the honest maturity
  ladder, path-safety, tamper detection, isolated installation, and the
  `knowledge list|export|validate|install|show` commands.
* **C — FlappyBird** (`docs/r65_flappybird_report.md`): fresh
  product-path run on the 10 never-used R61 reserve seeds — mean 45.70,
  median 40, **87 pipes reproduced on 3 fresh seeds** (all ALIVE at the
  10,000-frame budget); cross-process determinism exact; champion sha
  unchanged; limitations documented; `flappybird.ps1game` shipped.
* **D — Plugin contract** (`docs/r65_universal_plugin_contract.md`):
  contract v2 as implemented by three games + one diagnostic package;
  the isolation rule enforced by test.
* **E — Small games** (`docs/r65_small_game_pipeline.md`): BuzzyBee
  taken through the FULL pipeline (license → artifact → isolated plugin
  → own knowledge → runtime integration → autonomous test → objective →
  package). Candidate catalog re-verified; Nortis stays REFUSED
  (license), hello_pong stays BLOCKED (no artifact); PSX-Minecraft is
  the next candidate pending an objective definition.
* **F — Tetrade** (`docs/r65_universal_plugin_contract.md` §1 +
  `data/r65/r65_tetrade_*.json`): fresh benchmark (0/1/2/1 lines),
  limitation root-caused by three probes (diag → lockprobe → 28/28
  anchor table), the ANCHOR_DELTA fix in policy v1.1.0, challenger
  verified (mean **23.83 lines/life**, max 36, 2/6 alive at budget),
  known-good regression preserved, `tetrade.ps1game` v1.1.0 shipped.
* **G — Metal Slug X** (`docs/r65_metal_slug_x_report.md`): NO new boot
  experiments (stated plainly); the outstanding ledger preserved; the
  smallest decisive next experiment specified; `metal_slug_x.ps1game`
  shipped at INPUT_VERIFIED with no play claim.
* **H — User experience**: the full download→validate→install→test→play
  workflow exercised through the actual CLI; clean-environment install
  proven twice (package-level tests + the release gate's fresh-venv
  check); Linux/x86-64-only honesty stated.
* **I — Quality**: the full suite (821 tests) and the release gate
  (15/15, flappy R61 records byte-exact) — no weakened tests (the one
  widened expectation is documented in-test).
* **J/K — Deliverables & gates**: all 8 documents, `reports/r65_summary.json`,
  four packages with SHA-256 sidecars, the README game table, and the
  gate checklist (see `reports/r65_summary.json` §quality).

## 3. The packages

| package | version | maturity | sha256 |
|---|---|---|---|
| flappybird.ps1game | 1.0.0 | PARTIAL_AUTONOMOUS_PLAYER | `7221641d…bad73`→ see summary JSON |
| tetrade.ps1game | 1.1.0 | PARTIAL_AUTONOMOUS_PLAYER | `5d6de98a…db3f1` |
| buzzybee.ps1game | 1.0.0 | PARTIAL_AUTONOMOUS_PLAYER | `7ad89f0a…bad73` |
| metal_slug_x.ps1game | 0.1.0 | INPUT_VERIFIED | `e36d60ca…49405` |

Full hashes + release links: `reports/r65_summary.json` and the `r65`
GitHub release (`SHA256SUMS.txt` uploaded with the assets).

## 4. What was learned this round

1. **The Tetrade anchor lesson**: a "verified" perception contract can
   still be wrong in a way no unit test catches — only decoding actual
   locked placements against the model did. The fix is measured, not
   guessed.
2. **The BuzzyBee pad lesson**: input causality at the pad-word level
   does not imply the game acts on a 1-frame press — timing traps are
   game knowledge and belong in the game's adapter.
3. **The package lesson**: the exporter must re-validate its own output
   (it caught two spec mistakes before any test did).

## 5. Remaining blockers (next round, in order)

1. **MSX**: the +500 pay-frame capture (corridor-gate de-starve) — the
   smallest decisive experiment is fully specified.
2. **PSX-Minecraft**: define a verifiable objective from verified RAM
   state before any plugin work.
3. **BuzzyBee waves**: the deterministic hit-waves are now measurable
   through the product path (the R52-B margin-floor question).
4. **FlappyBird tail**: any challenger work requires a new
   pre-registered protocol (the champion stays frozen).
