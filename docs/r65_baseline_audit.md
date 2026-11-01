# R65 Baseline Audit — the actual repository state and every unresolved task

Round: **R65** · Date: 2026-11-01 · Base: remote `main` HEAD at round start,
`c449819` (the R64 follow-up commit; local tree fast-forwarded to it and
verified identical before any change).

This audit is the R65 Part A deliverable. It was written AFTER inspecting the
actual remote HEAD, the full `ps1play/` runtime, every game adapter, the open
issues (#4, #5, #6, #9, #10) with their latest comments, the R52/R62/R63/R64
reports and evidence, and the test suites (782 passed + 2 skipped + 1 xfailed
at baseline, reproduced exactly in this sandbox before any R65 change).

---

## 0. What the baseline actually is

* **Runtime (R62 architecture, extended by R64):** one headless engine
  (`ps1play/runtime/engine.py`) over the registry (`registry.py`);
  registered games at baseline: `flappybird` (frozen-model RuntimePolicy)
  and `tetrade` (built-in Dellacherie policy factory). CLI:
  `python3 -m ps1play play|verify`.
* **Frozen achievements verified intact at baseline:**
  * R61 FlappyBird champion — ONNX model + authority manifest, sha
    `4dd592a7…`, untouched; the R61 family records byte-exact in the
    release gate.
  * R62 autonomous runtime — release gate 15/15 at baseline.
  * R63/R64 Tetrade integration — 782-test suite green.
  * Existing MSX/RE evidence — `data/games/SLUS-01212/`,
    `data/knowledge/msx/capsule.json` (52 events), zero rewrites.
* **Environment findings (this sandbox):** the FlappyBird disc was missing
  after the sandbox recycle and was re-fetched by the committed
  `scripts/r53_fetch_flappy.py` — sha256 `b45871d3…` matched the committed
  record byte-for-byte. The BuzzyBee wrapped disc was rebuilt by the
  committed `scripts/r30t0_buzzybee_asset.py` — sha256 `042b94bb…` matched
  the R52 record byte-for-byte. Both are evidence of the round's
  reproducibility discipline holding across sandboxes.

## 1. Issue #4 — First Real Mission Clear (MSX)

* **Root problem remaining:** Mission 1 clear through legitimate
  interactive play. The controller v1 layer is superseded (see the issue's
  addendum: `0x0CA2E0` is NOT a progress meter — saturated near 255,
  resets per life; the working game-over sensor is u32 `0x0EE518`, 4/4
  live correlation, OBSERVED in telemetry v3).
* **Current implementation:** real-play traces, telemetry v3 with the
  verified game-over sensor, corridor work on the truck encounter.
* **Evidence:** `data/games/SLUS-01212/truck_evidence/` (r38–r52).
* **Reproduce:** the issue-5 toolchain (boot ledger discipline);
  see Issue #5's latest comment for the exact commands.
* **Proposed path (R65):** do NOT restart experiments with verified
  answers; carry the R52 outstanding list (below) forward inside the
  Issue-5 workstream; R65's knowledge packaging makes the verified
  subset user-inspectable (`metal_slug_x.ps1game`, INPUT_VERIFIED).
* **Required regression test:** the existing MSX regression suite
  (`tests/test_msx_*`, `tests/test_issue5_*`) stays green.
* **Acceptance:** unchanged from the issue text (a real interactive
  Mission 1 clear with control ownership, legal input, reproducible
  evidence, no hidden writes).
* **Status:** OPEN (correctly — not touched by R65's closure of anything).

## 2. Issue #5 — Source-First Reverse Engineering of Metal Slug X

* **Root problem remaining (the R52 outstanding list, verbatim):**
  1. Corridor-gate starvation diagnostics (the +500 class was never
     captured because the gate starved).
  2. The missing +500 payment capture (the pay-frame discriminator
     stays PENDING — magnitude table +500 ×3 vs +1000 ×7).
  3. Same pay-frame telemetry (armed and proven; two more +1000
     connects captured AT the pay frame).
  4. Freshness-spread hypothesis (unresolved).
  5. The unresolved accumulator discriminator (wound accumulator;
     named candidate: slot12 +0xa0, 257→2, 4-frame recovery).
  6. The deep clean deaths=0 source required before interactive M2
     entry can be claimed.
* **Current implementation:** pay-frame telemetry (offline contract
  checks before every boot), boot ledger with atomicity, the r47
  frontier rebuild protocol (deterministic 5-for-5 across rollbacks).
* **Evidence:** `data/games/SLUS-01212/truck_evidence/r52/`; the issue's
  49th comment.
* **Reproduce:** the R52 ledger flow (the comment lists every command).
* **Proposed path:** the smallest decisive experiment is still the
  +500 capture at the pay frame with the corridor gate de-starved;
  R65 does not fake progress on this (see
  `docs/r65_metal_slug_x_report.md` §2 for the honest status).
* **Required regression test:** the +1000 pay-frame telemetry contract
  tests stay green.
* **Acceptance:** a +500 capture with full 65-offset word vectors at
  the pay frame, or a proven-empty result with the same rigor.
* **Status:** OPEN.

## 3. Issue #6 — Master Mission v1.0 (plugin-first architecture)

* **Root problem remaining:** the tiny-game ladder beyond BuzzyBee's
  verified track — the R52-B dominance recipe scaled to CAP_F 2400
  (score = f − 99 EXACT, 9th pass) but the five-round hits-zero streak
  BROKE (both arms took 1 hit at the same deterministic wave; the
  margin floor was filed: GM 8 AND GM 12 both hit).
* **Current implementation:** the BuzzyBee RAM anchors (14 VERIFIED
  capsule fields), the dominance arms, the gs1 checkpoint rebuild.
* **Evidence:** `scratch/r52b/` + `data/knowledge/buzzybee/capsule.json`.
* **Reproduce:** the R52-B arm flow (`scripts/r52b_capf2400.py`).
* **Proposed path (executed by R65):** BuzzyBee was promoted INTO the
  product runtime as the third registered game with the proven planner
  behind the Policy contract (`ps1play/adapters/buzzybee/`), and its
  knowledge became downloadable (`buzzybee.ps1game`). The wave-hit
  problem remains open as future policy work (now measurable through
  the product path).
* **Required regression test:** `tests/test_r65_buzzybee.py` (21
  offline) + `tests/test_r65_integration.py` (2 real-emulator).
* **Acceptance:** the product-path acceptance recorded in
  `data/r65/r65_buzzybee_acceptance.json` (score law EXACT, natural
  game overs, restart flow).
* **Status:** OPEN (the master mission is long-horizon); the R65
  increment is delivered and verifiable.

## 4. Issue #9 — Decision-loop research / tool benchmarking

* **Root problem remaining:** the R52 addendum rules (telemetry earns
  boots offline; ledger atomicity; determinism dividends) are recorded
  but the decision-loop research itself (game-changer benchmarks) is a
  standing workstream.
* **Current implementation:** the rules are INSTITUTIONALIZED by R65 in
  the runtime + package system: new telemetry layers still prove row
  contracts offline first (unchanged), and the R65 BuzzyBee/Tetrade
  work followed the offline-checks-before-boot discipline.
* **Evidence:** the issue's R52 addendum (17 comments).
* **Reproduce:** n/a (research workstream).
* **Proposed path:** keep; no duplicate issue.
* **Status:** OPEN.

## 5. Issue #10 — Recover game logic from closed-source games

* **Root problem remaining:** the +500 pay-frame capture (same as #5's
  discriminator) and the general closed-source recovery benchmarking.
* **Current implementation:** the capsule system with contradiction
  guards (R38) — extended by R65 into the downloadable packages: the
  MSX capsule ships inside `metal_slug_x.ps1game` and the BuzzyBee
  capsule inside `buzzybee.ps1game`.
* **Evidence:** `data/knowledge/msx/capsule.json` (52 events).
* **Reproduce:** the R52 wound-table flow.
* **Proposed path:** the discriminator experiment remains the gate.
* **Status:** OPEN.

## 6. Duplicate / stale-evidence check

* **No duplicate issues** exist for any of the above (verified against
  the full issue list: #1–#3, #7, #8, #11–#15 are CLOSED with evidence
  closures; #4, #5, #6, #9, #10 are the only OPEN ones).
* **Stale evidence identified this round:**
  1. The "OpenBIOS kernel pad defect" diagnosis is SUPERSEDED (already
     recorded in the homebrew manifest; R65's BuzzyBee work confirms
     pad delivery is fine when the game actually runs).
  2. The BuzzyBee "score cap 1000 residual" UNKNOWN is RESOLVED by
     R65's product-path measurement: gs=5 is the hp-depletion game
     over; the "cap" was the game-over score of hit-taking runs. The
     capsule update is recorded in `data/r65/r65_buzzybee_gs5.json`
     and the acceptance record (the capsule file itself is preserved —
     the correction lives in the R65 evidence, cross-referenced).
  3. The Tetrade policy's placement model was measured WRONG for
     rotations 1–2 of the 3-wide pieces (the R64 "weak but legal"
     heuristic buried 39 holes/life) — corrected this round with the
     28/28 anchor table; the R64 records keep their historical value
     and the R65 evidence documents the delta
     (`data/r65/r65_tetrade_anchor.json`,
     `data/r65/r65_tetrade_improvement.json`).
* **No existing achievement damaged:** the R61 champion sha is
  unchanged; the R62 release gate re-runs at the end of the round;
  the R64 Tetrade contract tests are preserved (one expectation
  widened with an in-test comment: the registry GREW — the
  game-list pin became a superset assertion, documented in-test).

## 7. R65 work this audit precedes

Parts B–K of the R65 mission were executed on top of this baseline:

* Part B/C/D/E/F/G/H deliverables (see `docs/r65_final_report.md`).
* No issue was closed by R65. No issue was reopened. The five open
  issues stay open with their real blockers.
