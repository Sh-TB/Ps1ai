# R66 Final Report — Metal Slug X Mission 1: the starvation root-caused, the +500 captured, the fourth runtime game

Round: **R66** · Date: 2026-11-01 · Base: `4357fce` (R65) ·
Issues touched: #4 #5 #6 #9 #10 (all updated, none closed, none
duplicated) · Companion reports: `reports/r66/` (BASELINE,
ACTIVE_EXECUTION_PATH, MISSION1_FINDINGS, GAMEPLAY_RESULTS,
R66_SUMMARY.json).

## 1. What R66 actually delivered

1. **The corridor-gate starvation is ROOT-CAUSED and fixed.** The
   per-skip `GATE_DIAG` dump (the diagnostic R52 never captured)
   showed the R50/R51 predicate blocked on entities that can neither
   absorb a player bullet nor register a payment — the bullet-
   TRANSPARENT 0xab94 wasp and in-flight `projectile_air` rows — and
   that the protocol never advanced the player. The corrected
   predicate ("a blocker must absorb the bullet or register the
   payment") is implemented in the experiment runner AND in the new
   product policy, unit-tested, and VERIFIED in-game: the de-starved
   gate immediately produced captures the R48-R52 protocol never
   reached.
2. **The +500 pay-frame capture exists.** Pass B tap 6: +500 at tail
   f1 (the bullet-impact frame) from a fresh-state one-bullet kill —
   with the full union-net word vectors at the pay frame. Two more
   +1000s replicated the R51/R52 pattern. The magnitude table is now
   +500 ×4 vs +1000 ×7. The pay-frame LAW: the accumulator pays on
   the internal damage event ~2 frames BEFORE the victim's visible
   0x5b0c registration; the slot12@0xa0 pulse is the REGISTRATION
   witness (n=2 replicated), not a magnitude discriminator. The
   zero-overlap discriminator stays honestly PENDING (n=1 vs n=4).
3. **Metal Slug X is the FOURTH registered runtime game.**
   `python3 -m ps1play play metal_slug_x` runs the deterministic
   Mission-1 rules policy through the standard engine (preflight disc
   pin → boot → ready → episodes → records). Two independent runs are
   BYTE-IDENTICAL (1666f/1100 + 388f/1300, 87/13 actions); the player
   advances px 258.6 → ~1164 (the armored-truck encounter, the
   R38-R52 known blocker) and dies there. Legality: legal pad inputs
   only, zero RAM writes, zero save-state rewinds in claimed play, no
   training, no screenshots-as-input.
4. **The knowledge package v0.2.0** (GAMEPLAY_VERIFIED) ships the
   updated capsule (56 events), the R66 findings digest, and the
   package's own test file; export → validate → clean-root install
   all verified; the other three packages are UNTOUCHED.
5. **The frontier rebuild determinism is re-proven 6-for-6**
   (r66_frontier_a px 1224.9 census 13 / r66_frontier_b px 1254.8
   census 14 — byte-exact the R52 postures across an independent boot
   and a fourth sandbox rollback).

## 2. Verification chain

| check | result |
|---|---|
| offline dry-run (`scripts/r66_dryrun.py`) | 20/20 green before every boot |
| boot ledger | cap 5 disclosed pre-run; 4 spent; 1 disclosed ledger-pollution refund (zero core loads) |
| full test suite | **840 passed + 2 skipped + 1 xfailed** (R65's 821+2+1 + exactly the 19 new R66 tests; 0 weakened; the 2 skips are the pre-existing order-dependent tb_manifest skips) |
| release gate (`python3 -m ps1play verify --profile final`) | **15/15 PASS** — the flappy R61 records byte-exact (k=30 → 37@4401; 3×k45 → 40@4753), clean-venv install PASS |
| package roundtrip | export → validate (10 files, hash-verified) → install into two fresh roots → listed installed |
| cross-game isolation | `tests/test_r66_msx_adapter.py::TestIsolation` (no other game's modules imported; no MSX addresses in the shared runtime) |

## 3. Environment repairs this round (disclosed)

* capstone + onnxruntime + onnx installed (the sandbox recycle lost
  them; the R62 dependency set).
* The FlappyBird disc and the BuzzyBee disc were re-fetched/rebuilt
  by the committed scripts and matched their pins BYTE-FOR-BYTE
  (`b45871d3…`, `042b94bb…`) — restoring the 8 real-emulator tests
  the sandbox recycle had parked as skips.

## 4. What R66 did NOT do (honest)

* **Mission 1 is NOT cleared** and no autonomous-playthrough claim is
  made. The product path's furthest milestone is the truck encounter
  (px ~1164, score 1100-1300 per life, byte-deterministic deaths).
* The pay-frame discriminator is PENDING (needs n≥2 +500 captures).
* The freshness-spread hypothesis is SUPPORTED, not proven.
* Boss HP remains BLOCKED (standing).
* `ps1play/agent/route.py` + `combat.py` (legacy MSX semantics in the
  shared agent package) were NOT migrated into the game package —
  recorded as architecture follow-up under #6; the R66 adapter
  reimplements what it needs inside the game package instead.

## 5. The next smallest decisive experiments

1. **The widened discriminator:** restore the r66 frontiers
   (restore-only) and capture n≥2 +500 payments under the verbatim
   pay-frame telemetry; test the delay signature (+500 tail-f1 vs
   +1000 tail-f3/f4) and the 19 candidate offsets on the widened set.
2. **The truck campaign (product path):** grenade sequencing against
   the truck (hp_a4 300, −100 per grenade, the R38-R52 A/B evidence)
   + soldier prioritization — the first policy change tied to an
   observed product-path death.

## 6. Artifact map

* Experiments: `data/games/SLUS-01212/truck_evidence/r66/`
  (r66_boot2_s1 / r66_boot3_s2a / r66_boot4_s2b JSONLs + reports +
  r66_analysis.json + r66_env_probe.json + r66_product_run.json +
  product_run/).
* Code: `ps1play/adapters/metal_slug_x/{adapter,policy,package_spec}.py`,
  `ps1play/runtime/{registry,session}.py`, `scripts/r66_*.py`,
  `tests/test_r66_msx_adapter.py`.
* Package: `download/metal_slug_x.ps1game` v0.2.0 — sha256
  `cc5af6c65433dd4272e386fe13336b4988510406653695f4ba7af1f935817976`.
* Capsule: `data/knowledge/msx/capsule.json` — 56 events, next
  experiment R67 specified.
