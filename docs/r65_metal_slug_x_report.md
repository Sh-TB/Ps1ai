# R65 Metal Slug X Report — primary-priority status, honest increment, next experiment

Round: **R65** · Date: 2026-11-01 · Issue anchors: #4 (mission clear),
#5 (RE master task), #6/#9/#10 (architecture / decision loop / knowledge).

## 1. What R65 actually did for Metal Slug X — and what it deliberately did NOT do

**Done this round:**

1. **The knowledge became distributable.** `metal_slug_x.ps1game`
   (v0.1.0, maturity **INPUT_VERIFIED**) packages the provenance-grade
   capsule (52 evidence events, 8 memory fields with statuses and
   provenance), the verified entity table (0x800CA268, stride 0x14C,
   HP @+0x8E, damage entry enemy_800A41D8), the death-path analysis
   (three paths incl. mission-timer expiry), the Mission 1 map/route
   knowledge, the truck-blocker resolution record and the disc identity
   pin (SLUS-01212, disc sha `45cde149…`). A user with a legal copy can
   install the knowledge and check their disc against the exact bytes
   every committed record was made with. The package EXPLICITLY
   ships no runtime adapter, no autonomous play, and says so.
2. **The outstanding-task ledger was audited and preserved** (see
   `docs/r65_baseline_audit.md` §2): corridor-gate starvation
   diagnostics; the missing +500 payment capture; same pay-frame
   telemetry (armed and proven); the freshness-spread hypothesis; the
   accumulator discriminator (named candidate: slot12 +0xa0, 257→2,
   4-frame recovery); the deep clean deaths=0 source. NOTHING was
   silently marked resolved.
3. **The disc and evidence are intact in this sandbox:** the retail
   image hashes to the committed `45cde149…`; the r38–r52 evidence
   tree is present; the capsule contradiction guards pass.

**NOT done this round (stated plainly):**

* **No new MSX boot experiments were executed.** The R52 workstream's
  own rules (boot ledger atomicity, offline contract checks before
  every boot, no phantom ledger entries) mean a boot spent without the
  full ledger discipline is worse than no boot. This round's budget
  went to the platform deliverables (the package system, the third
  runtime game, the Tetrade anchor correction) — all of which the MSX
  workstream itself will consume next round. No gameplay progress is
  claimed. No experiment was marked resolved.

## 2. The outstanding blockers (unchanged, in priority order)

1. **The +500 pay-frame capture** — the pay-frame telemetry is armed
   and proven (11 offline contract checks; two +1000 connects captured
   AT the pay frame); the +500 class was never captured because the
   corridor gate starved. This is the discriminator's raw-material gap
   (magnitude table +500 ×3 vs +1000 ×7).
2. **Corridor-gate starvation diagnostics** — why the gate produced no
   capture windows on the R52 runs; feeds directly into (1).
3. **The accumulator discriminator** — the wound accumulator remains
   the live hypothesis with a NAMED first candidate (slot12 +0xa0,
   257→2, 4-frame recovery).
4. **Freshness-spread hypothesis** — unresolved.
5. **Deep clean deaths=0 source** — required before interactive M2
   entry can be claimed (the mission-timer expiry death path is part
   of this).
6. **Boss HP** — BLOCKED (standing): slots 14/17/18/5 immune to all
   tested weapons/positions; HP outside the 0x14C table or
   phase-gated.

## 3. The smallest decisive experiment (specified for next round)

**Experiment: de-starve the corridor gate and capture +500 at the pay
frame.**

* **Hypothesis:** the +500 payment class connects at the same pay frame
  as the captured +1000 connects, and the corridor gate starved only
  because the R52 runs entered the gate with the wasp-window
  invulnerability predicate unresolved (n=4 piercing taps).
* **Method (the R52 discipline, verbatim):** offline contract dry-run of
  the telemetry layer first; boot ledger 1 = core+disc load; replay the
  deterministic frontier rebuild (px 1224.9 / 1254.8, 5-for-5 across
  rollbacks) to the gate; run the gate with the piercing taps withheld
  (the n=4 evidence says taps inside the window pierce without
  reaction — withhold them and let the gate body pass); capture every
  pay frame with the 65-offset word vector; classify by magnitude.
* **Budget:** 1 boot + restores (restore-only arms are not boots).
* **Success signal:** ≥1 capture whose word-vector family matches the
  +500 class (the R48–R52 table cross-check).
* **Failure signal:** zero connects at the pay frame across the gate
  body — which itself is the starvation diagnostic data point (2).
* **Recovery:** if the gate starves again, the freshness-spread
  hypothesis (4) becomes the next probe with the same captures.

## 4. Mission 1 acceptance status

**Not completed.** Per Issue #4's own gate: a real interactive clear
with control ownership, legal input, a genuine completion indicator
correctly distinguished from attract/demo, reproducible evidence, an
independent repeat, zero hidden writes, no stage bypass. None of these
are claimable today, and R65 claims none.

## 5. Package facts

* `metal_slug_x.ps1game` v0.1.0 — INPUT_VERIFIED — 8 files — disc pin
  `45cde149…` — capabilities: `autonomous_play: false`, diagnostics =
  disc identity check / capsule provenance review / generic harness
  compatibility. Release link + SHA-256 in
  `docs/r65_downloadable_knowledge_packages.md`.
