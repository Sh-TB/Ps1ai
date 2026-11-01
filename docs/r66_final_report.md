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
| full test suite | **841 passed + 2 skipped + 1 xfailed** (R65's 821+2+1 + the 19 new R66 tests + 1 R66 final-mile exporter regression test; 0 weakened; the 2 skips are the pre-existing order-dependent tb_manifest skips) |
| release gate (`python3 -m ps1play verify --profile final`) | **15/15 PASS, re-run after the final-mile fix** — the flappy R61 records byte-exact (k=30 → 37@4401; 3×k45 → 40@4753), clean-venv install PASS |
| package roundtrip | export → validate → install into fresh roots → **installed CONTENT read back** (`scripts/r66_content_verify.py`: capsule 56/15 events, adapters/policies/tables real bytes) |
| cross-game isolation | `tests/test_r66_msx_adapter.py::TestIsolation` (no other game's modules imported; no MSX addresses in the shared runtime) |

## 3. Environment repairs this round (disclosed)

* capstone + onnxruntime + onnx installed (the sandbox recycle lost
  them; the R62 dependency set).
* The FlappyBird disc and the BuzzyBee disc were re-fetched/rebuilt
  by the committed scripts and matched their pins BYTE-FOR-BYTE
  (`b45871d3…`, `042b94bb…`) — restoring the 8 real-emulator tests
  the sandbox recycle had parked as skips.

## 3b. The final-mile fix (found by the independent re-run, disclosed)

The R66 session committed its last edits AFTER the release gate had
run, and the shipped state broke its own validation. The
continuation session re-ran the full suite independently and found
it, then fixed it at the root:

1. **The shipped msx capsule was invalid twice over.** Event 56
   carried the status `TESTED` (not in the capsule schema's
   VERIFIED/OBSERVED/INFERRED/UNKNOWN/CONTRADICTED/BLOCKED set) and
   the four R66 events pushed the canonical size to 67,448 B > the
   64 KiB design cap (2 shipped-validation tests failed). Fix: the
   event status honestly relabeled `OBSERVED` (consistent with the
   other four R66 events), R66-owned prose compacted with every
   number/address/evidence pointer preserved, and two stale
   round-bookkeeping meta notes dropped (kept in git history and in
   each round's own report). Capsule now 65,302 B canonical, all 20
   capsule/knowledge tests green. Full narratives live in
   `reports/r66/`, the worklog and `truck_evidence/r66/`.
2. **The ps1game exporter shipped path-string stubs, not content —
   all four packages, since r65.** `build_package` treated a 3-tuple
   str first element as INLINE content, so every standard
   `(repo_path, arcpath, role)` entry archived the literal string
   "/home/z/..." (50-65 B) instead of the file's bytes. Packages were
   structurally valid (manifest hashes matched the stubs) and every
   earlier verification checked structure + hashes only — the R65
   "clean-user install" never read content back. Fix (shared runtime,
   per the round's own ownership rule): dict first element = inline
   JSON, str = source path; regression test
   `test_package_carries_real_content_not_path_stubs` pins byte
   equality in the archive + a stub detector. ALL FOUR packages were
   regenerated by the fixed exporter and their installed content was
   read back in fresh roots (`scripts/r66_content_verify.py`). The
   r65 release assets are superseded by the r66 release (which now
   ships all four corrected packages).
3. **`SHA256SUMS.txt` was committed stale** (the r65 metal_slug_x
   hash) — the working-tree fix had never been committed; now
   regenerated for the four corrected packages.

After the fix the FULL suite and the release gate were re-run:
**841 passed + 2 skipped + 1 xfailed, gate 15/15 PASS.**

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
* Packages (all four regenerated by the fixed exporter, content
  verified): `download/metal_slug_x.ps1game` v0.2.0 — sha256
  `54fdacc10130833823e171ccf55e6467b3154a5bb602c93c61fac88b78fbff0c`;
  flappybird
  `3b659f0ca1d7baa3b71c451cbfc8bf08882c123974131027f09616ca219dd588`;
  tetrade
  `4362a5b8d174ed9ef79d9926545c40b5b7a8541777eb0768c08fbab8c89ea1ec`;
  buzzybee
  `3286aa179fcedf5284fe1e066221acaeb889c8b08f6f15ce02322c610d8703ac`.
  Same knowledge versions as r65 for the three non-MSX games — only
  the archive now carries the real bytes.
* Capsule: `data/knowledge/msx/capsule.json` — 56 events, next
  experiment R67 specified.
