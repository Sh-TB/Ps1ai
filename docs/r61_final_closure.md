# R61 Final Closure Report — the FlappyBirdPSX training phase ends

> Round R61, 2026-10-31 → 11-01, Issue #13 (the R57 workstream).
> Base `d8bcbd3` (the R60 head). Primary: FlappyBirdPSX final closure,
> deployment, validation, handoff. hello_pong regression re-verified.
> Every gameplay number in this report is a REAL emulator measurement
> (Beetle PSX 0.9.44-class libretro core + OpenBIOS; the
> FlappyBirdPSX v0.1.0 ISO re-fetched this round, sha256 `b45871d3…`
> verified; hello_pong bin sha256 `a592f7ed…` verified through the
> documented r12 procedure).

```
TRAINING_STATUS:  CLOSED
DEPLOYMENT_STATUS: VERIFIED
EMULATOR_STATUS:   VERIFIED
REGRESSION_STATUS: PASS
RELEASE_STATUS:    PASS
```

## 1. What this round did

The mission's 17 sections were executed end-to-end: baseline
verification (§0), model freeze + provenance audit (§2), the training
closure record (§3), an INDEPENDENT inference consumer (§4), the
perception-to-action contract (§5), a 220k-vector 3-way parity suite
(§6), emulator-in-the-loop validation — 7 family seeds byte-exact +
30 fresh pre-registered seeds with the champion at n=2 and two
references (§7), the baseline comparison statistics (§8), fault
injection + robustness tests (§9), the sustained performance profile
(§10), a clean-room installation (§11), the reuse boundary note (§12),
the full suite + hello_pong regression (§13), and the one-command
release gate (§14).

## 2. The frozen final model (all hashes verified this round)

| artifact | sha256 | bytes |
|---|---|---|
| champion checkpoint `data/learn/r59_soup_e6a010.npz` | `72c79f3091ed14e8dd497ddc52570bb4660bfc6367e6b50eb8a8aa1eff8a28f4` | 7,372 |
| ONNX artifact `data/learn/r60_soup_e6a010.onnx` | `4dd592a7118a5c4de7b44166b42b8d09d53fbb59330d36d0ba2746393dc11044` | 7,182 |
| manifest `data/learn/FINAL_MODEL_MANIFEST.json` | `10d9ec7f9ee96373927d6b006d0569a2f3083c10d2f035f0d7657dbd6133352b` | 5,793 |

Provenance chain VERIFIED (script `r61a_model_audit.py`, 14/14 PASS):
the champion npz is BITWISE re-derivable as `r58_dir2p_true +
0.10·(r58_si_v2_e6 − r58_dir2p_true)` (float64 math → float32 cast,
the exact R59 procedure); every ONNX initializer is bitwise-equal to
the champion weights/norm (ε folded); topology `Sub→Div→Gemm→Relu→
Gemm→ArgMax(first-max)`; opset 17 / IR 8 / float32; classes
`[HOVER, FLAP]`; no earlier checkpoint swapped in. The manifest is
read-only (0444) and is copied byte-identically into the deployment
package. The model was NOT retrained and the champion is UNCHANGED.

## 3. The independent deployment package (§4)

`deployment/flappybird_policy/` — numpy + onnxruntime ONLY; zero
imports of training, teacher, dataset or replay code (AST-scanned and
fresh-subprocess-proven with `ps1play` unreachable:
`tests/test_r61_deployment.py`). API: `load_policy(model_path,
manifest_path)` → `predict` / `predict_batch` / `logits_batch` /
`reset` / `close`; identity (model + manifest sha256) exposed; strict
input validation (shape, dtype==float32, finiteness, documented
per-feature ranges — reject, never coerce); CLI smoke
(`python3 -m flappybird_policy`); pinned `requirements.txt`
(onnxruntime==1.19.2, numpy==2.1.3); docs: README / INSTALL /
INTERFACE / MODEL_CARD / KNOWN_LIMITATIONS / TROUBLESHOOTING /
REUSE_BOUNDARY.

## 4. The perception-to-action contract (§5)

`deployment/flappybird_policy/INTERFACE.md` specifies the full chain
(frame ingest → BirdObserverV7 → gap finder v3 → GapTrackerV7 → the
10-feature v7 vector → in-graph normalization → argmax → legal pad1
input), every unit and sentinel (−1.0 missing-bird/gap; init counters
since_flap=99, since_gap=40, last_gc=−1), tie-breaking (first-max →
HOVER), episode lifecycle (fresh perception per episode), no-pipe /
occlusion / terminal behavior, and the frame-timing assumption
(decision t applies during [t, t+1)). The contract is ENFORCED at
runtime by `schema.py`; 24+ boundary tests cover wrong counts, NaN/Inf,
wrong dtype/shape/order, out-of-range per feature, sentinel states,
reset and repeated-init behavior.

## 5. Independent parity (§6) — `data/learn/r61_parity_evidence.json`

Corpus **220,522 deterministic vectors** (seeded rng(61)): realistic +
real-vector mixture + every range endpoint/sentinel + perturbed REAL
closed-loop vectors + tie-pressing walks. Three paths compared — the
inline numpy reference (from the npz bytes), a bare onnxruntime CPU
session, and the INDEPENDENT package (external consumer, validation
on):

- argmax agreement **3-way 100%**; max |Δlogit| **0.0** on every pair;
  min top-2 margin 4.23e-4 (no knife-edge ambiguity).
- Malformed-input rejection: 6/6 classes rejected with precise errors.
- R60's 4,200 REAL vectors: package argmax == recorded 4200/4200;
  ORT vs recorded logits max Δ 0.0.

## 6. Emulator-in-the-loop (§7) — real game, deployed path

**Family reproduction through the deployment package** (one boot, 7
episodes, 50,813 decision frames; `data/learn/r61_family_rows.jsonl`):
k6 **87-alive/640 flaps**, k12 76@8798/560, k30 37@4401/281,
k45 40@4753/302, k60 **87-alive/640**, k90 68@7895/512, k210 42@4966/322
— **the exact R59/R60 record, byte-for-byte on every (pipes, frames,
flaps) triple.** (The R60 report's 51,773 total additionally counted
the 13-frame episode-start sequences; the per-episode decision-frame
count here is 50,813.)

**Fresh pre-registered validation** (`data/learn/r61_validation_split.json`,
mtime 20:28:26 UTC; first episode 20:37:53 UTC — the split was
committed-to-disk BEFORE any collection; the split, its rule, the
exclusion union and the retirement clause are in the committed file):

- 30 unseen seeds (k % 7 == 0 rule; disjoint from every prior use:
  r53–r56 history, R57 TRAIN/VAL/TEST, R58 TEST+dev, R59 TEST, family,
  and the prior split residues) × champion n=2 + base n=1 + C1 n=1 =
  **180 episodes, 719,714 frames, 8,464 s of emulator time**.
- Per-episode records (seed, policy sha, emulator tag, result, death
  reason, pipes, frames, flaps, decisions, errors, trace sha256):
  `data/learn/r61_validation_rows.jsonl`.
- **Determinism VERIFIED**: champion reps byte-identical on all 30
  seeds (identical trace hashes); 37 cross-process duplicate groups
  (parallel workers) all byte-identical; no nondeterminism found, no
  tolerance needed.

## 7. Baseline comparison (§8) — same split, same configuration

| policy | mean | median | stdev | min | max | IQR | alive@10k |
|---|---|---|---|---|---|---|---|
| **champion (deploy pkg)** | 52.30 | 48.0 | 26.29 | 10 | 87 | 32–85 | 6/30 |
| base `r58_dir2p_true` | 46.87 | 38.0 | 28.06 | 10 | 87 | 0–39.75 | 2/30 |
| C1 `flappy_student_feat_r56_c1` | 53.37 | 50.0 | 24.83 | 12 | 87 | 33–79.75 | 5/30 |

W/T/L (per-seed pipes): champion vs base **6/23/1**; champion vs C1
**7/11/12**. Honest reading:

- The champion is strictly better than its own base on this split
  (and byte-dominant: 23 ties, 6 wins, 1 loss).
- **C1 and the champion are statistically comparable here** (C1 +1.07
  mean, +2.0 median, W/T/L 12/11/7 in C1's favor — well within the
  heavy-tailed seed variance; no significance is claimed in either
  direction). This matches the R59 disclosure that C1 keeps the
  alive-depth count on some splits. The R59 TEST aggregate win stands
  as published; this fresh split measures the same three policies
  again and reports the actual trade-off — **no retraining was
  triggered** (§16 stop rule): the differences are within the
  documented per-seed divergence, and the mission forbids cosmetic
  weight changes.
- Heavy-tail explanation: on ~3/4 of seeds the soup's trajectory is
  byte-identical to its base (the soup direction is nearly invisible
  there); on the divergent seeds the outcome swings hard both ways
  (e.g. this split: k70 85 vs base 0; k259 10 vs base 0; and C1's
  k161 69 vs champion 34-class flips). Aggregates therefore inherit
  high variance; per-seed records are the honest currency.

## 8. Robustness and fault handling (§9)

`tests/test_r61_deployment.py` (24 tests): clean startup, repeated
init (5×), close/reopen, context manager, missing model, corrupt
model (bit-flip → hash mismatch rejected; truncated → session-init
error), garbage manifest, wrong class order, missing onnxruntime
(simulated) → actionable error, NaN/Inf/short/long/wrong-dtype/list
inputs rejected, out-of-range per feature rejected, boundary values
accepted, determinism across calls/instances/batch-vs-single, runner
fault injection (start failure, mid-episode core death, instant game
over — all surfaced as typed `LoopError`, never swallowed), and the
stale-perception regression test (below). No silent fallbacks exist;
no teacher/training import is reachable from the package.

**Incident, disclosed**: the R61 runner initially skipped
`reset_obs()` for numpy-path reference policies — stale perception
produced 60-frame flap-spam deaths on 16 base episodes. Detected by
the mechanically-impossible signature, fixed in the runner, pinned by
a regression test, and ALL affected episodes re-run. The champion's
60 deploy episodes were unaffected (fresh perception per episode; all
7 family seeds byte-exact). Record: `data/learn/r61_runner_incident.json`.
A second infrastructure fault (two parallel workers sharing one
emulator workspace raced on savestate files, one loud IndexError) was
fixed by per-worker workspace isolation and the affected leg re-run.

## 9. Performance profile (§10) — `data/learn/r61_profile.json`

Model load 14 ms; first inference 0.39 ms; **sustained 10,000 calls:
p50 0.037 ms, p95 0.048 ms, p99 0.052 ms (≈22,500 calls/s)**; batch
4,096 in 2.1 ms; peak RSS delta 18.2 MB for the whole sustained run.
The perception adapter costs ≈1.11 ms/frame — **the host perception,
not inference, dominates per-frame cost (~30×)**. Package 45.5 KB +
model 7.2 KB; runtime deps ≈70 MB (onnxruntime 40.5 MB, numpy 29.3
MB). Verdict: **suitable for ordinary CPU-only deployment**.

## 10. Clean-room installation (§11) — PASS

`scripts/r61_cleanroom.sh`: fresh venv (no training tree on sys.path),
ONLY the pinned requirements installed, then (1) CLI smoke SMOKE
PASS, (2) minimal example runs, (3) API/batch/lifecycle assertions
PASS, (4) version reporting shows the verified sha. A user needs
nothing from the training environment.

## 11. Reuse boundary (§12)

`deployment/flappybird_policy/REUSE_BOUNDARY.md` separates the
game-agnostic layer (manifest/hash-verified policy loading, enforced
schemas, episode lifecycle, evidence discipline, runner pattern) from
the game-specific adapters (observer, gap finder/tracker, feature
schema, action mapping, terminal detector), with the plug-in shape for
a next game. No universal framework was built; no cross-game
generalization is claimed.

## 12. Regression gates (§13)

- Full suite: **667 passed, 1 skipped, 1 xfailed** (R60 baseline 641+1s
  +1x + 24 new R61 tests + 1 restored R57 manifest test pair — the
  untracked `tb_manifest.json` was reconstructed deterministically
  from the COMMITTED dataset meta by `r61_restore_tb_manifest.py`, so
  those tests now verify committed data instead of skipping; the one
  remaining skip is the pre-existing owner-local-exe test).
- **hello_pong regression PASS** (the R54 protocol, verbatim, one boot
  per invocation): teachers v1/v2 **7 scored / 0 conceded** each;
  student `pong_student_feat_p4d4` **8 scored / 2 conceded**, gameAI
  returns [19,19] — the exact R54/R59/R60 record
  (`data/learn/r61_pong_regression.json`). No test was deleted,
  weakened or skipped to make this pass.

## 13. The release gate (§14)

```
python3 scripts/r61_final_verify.py
```

9 gates, each explicitly checking its condition (never trusting an
exit code): repo_state / manifest_hashes (incl. bitwise soup
re-derivation) / deployment_package / synthetic_parity / emulator_smoke
(k6 through the package must reproduce 87-alive/640 exactly) /
validation_evidence / regression_tests / pong_regression /
reports_complete → machine-readable `data/learn/r61_gate_result.json`,
exit 0 only when every required gate PASSes. Final run: **9/9 PASS,
RELEASE: PASS** (gate runtime ≈2.5 min; `--fast` skips only the
emulator gate and reports it as SKIP).

## 14. Environment (this machine)

Python 3.12.16 (uv cpython), numpy 2.1.3, onnxruntime 1.19.2, onnx
1.23.2, 2-core x86-64 container, CPU-only. Emulator: mednafen_psx
(beetle) libretro core via the repo's ctypes frontend + OpenBIOS
(`third_party/openbios/openbios.bin`); FlappyBirdPSX v0.1.0 ISO
(sha `b45871d3…`, license sector + CD001 verified on fetch);
hello_pong bin sha `a592f7ed…`. Emulator determinism re-verified this
round (two identical episodes → byte-identical frame streams).

## 15. Commands (all evidence reproducible)

```
python3 scripts/r61a_model_audit.py          # 14-step provenance audit -> manifest
python3 scripts/r61_restore_tb_manifest.py   # scratch restore from committed meta
python3 scripts/r61c_validation_split.py     # the pre-registered split
python3 scripts/r61e_deploy_loop.py --mode family --policies deploy --out ...
python3 scripts/r61e_deploy_loop.py --mode fresh --policies deploy:2,base:1,c1:1 ...
python3 scripts/r61b_parity_suite.py         # 220k 3-way parity
python3 scripts/r61d_validation_stats.py     # merge + stats
python3 scripts/r61f_profile.py              # sustained profile
bash scripts/r61_cleanroom.sh                # clean-room install
python3 scripts/r54c_pong_eval.py --agents v1,v2 --feat-art data/learn/pong_student_feat_p4d4.npz
python3 scripts/r54c_pong_eval.py --agents feat --feat-art data/learn/pong_student_feat_p4d4.npz
python3 -m pytest tests/ -q
python3 scripts/r61_final_verify.py          # THE release gate
```

## 16. Honest limitations and remaining items

- The known limitations are enumerated in
  `deployment/flappybird_policy/KNOWN_LIMITATIONS.md` (decision-only
  ONNX boundary, numpy host dependency, float32-CPU parity scope, the
  pipe-overlap latch class, heavy-tailed seeds, C1 comparability,
  razor-edge fragility, determinism scope, the documented R57 save
  incident).
- Screenshot/GIF evidence was NOT captured for the 187 grid episodes;
  the per-episode trace hashes + byte-identical reps + the exact
  family-record reproduction are the episode evidence (the gate and
  tests re-run real gameplay live).
- OS portability is claimed for Linux/x86-64 only (tested here); the
  clean-room test covers a fresh Python environment, not other
  operating systems.
- One pre-existing test remains SKIP (owner-local exe absent); it
  skipped identically in R60 on machines without that file.

## 17. Badges

- Model freeze + manifest: **IMPLEMENTED+TESTED** (14/14 audit PASS)
- Independent consumer: **IMPLEMENTED+TESTED** (24 tests, clean-room)
- Contract + boundary validation: **IMPLEMENTED+TESTED**
- 3-way parity 220k: **TESTED** (exact)
- Emulator family reproduction: **OBSERVED** (byte-exact, 7/7)
- Fresh validation 30×(2+1+1): **OBSERVED** (719,714 frames)
- Baseline comparison: **OBSERVED** (trade-off preserved, disclosed)
- Robustness/fault injection: **TESTED**
- Profiling: **OBSERVED** (10k sustained calls)
- Clean-room install: **TESTED**
- hello_pong regression: **PASS** (exact record)
- Release gate: **PASS** (9/9)
- Training closure: **CLOSED** (`docs/r61_training_record.md`)

Future work belongs to deployment and other-game integration — not to
further FlappyBird training.
