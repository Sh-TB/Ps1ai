# R62 Baseline Audit — Independent Repository Inspection (Section 0)

Date: 2026-11-01 (UTC). Auditor: the R62 mission itself (no trust in any
prior summary; every hash below re-computed from the actual checkout).

## Current HEAD and relevant commits

- Local HEAD == `origin/main` == `4797af2e16c5…`
  ("R61 RE-VERIFIED post-recycle: the full closure re-proven on a fresh
  sandbox…"). The sandbox had reverted the local branch ref to
  `14be0cd`; the working tree still held the re-verification content
  and was fast-forwarded after a byte-identity check against the
  pushed blobs.
- Relevant commit chain:
  - `6949ed4` — R61 EXECUTED — FINAL CLOSURE (frozen model, deployment
    package, 220k parity, 30-seed validation, release gate 9/9).
  - `14be0cd` — R61 follow-up (issue-update script; #13 closed).
  - `4797af2` — R61 RE-VERIFIED post-recycle (all gates re-run live).
- Regression baseline re-measured at this HEAD, this session:
  `python3 -m pytest tests/ -q` → **668 passed, 1 xfailed in 24.9 s**
  (matches the recorded R61 baseline of 669 collected).

## R61 frozen artifacts re-verified (re-computed SHA256)

| Artifact | SHA256 (first 16) | Bytes | Check |
| --- | --- | --- | --- |
| `data/learn/r59_soup_e6a010.npz` (champion checkpoint) | `72c79f3091ed14e8` | — | == `FINAL_MODEL_MANIFEST.json` |
| `data/learn/r60_soup_e6a010.onnx` | `4dd592a7118a5c4d` | 7,182 | == manifest + package copy |
| `deployment/flappybird_policy/models/r60_soup_e6a010.onnx` | `4dd592a7118a5c4d` | 7,182 | byte-identical to data/ copy |
| `FINAL_MODEL_MANIFEST.json` (both copies) | — | — | read-only 0444, 14/14 audit steps recorded |
| FlappyBirdPSX v0.1.0 ISO (re-fetched this session) | `b45871d32c791078` | 571,536 | == `data/homebrew/manifest.json` + R56/R58/R59 evidence |

Issue #13 re-read from the GitHub API: `state: closed`,
`state_reason: completed`, final R61 evidence comment + the
post-recycle re-verification comment both present (read back
byte-identical at post time). It stays closed (no R61 integrity defect
found).

## Existing architecture (what is actually there)

### Emulator layer (REUSABLE — proven)

- `ps1play.api.PS1Play` — the one-class frontend: fail-early config
  contract, `boot()`, profile/plugin discovery, journal, states.
- `ps1play.core.host.LibretroCore` — headless beetle PSX core via
  ctypes: `run(frames, buttons)` (advances + sets pad), `frame_rgb()`
  (latest rendered frame, in-memory, zero disk), `serialize()/
  unserialize()` (savestates), `frames_run` counter, `shutdown()`.
  No GPU/X11 needed; CPU-only.
- Firmware trust check (`labconfig`) runs on every boot; OpenBIOS is
  committed at `third_party/openbios/openbios.bin`.

### Game/episode layer (REUSABLE)

- `ps1play.learn.games.FlappyEnv` — boot→GET-READY anchor
  (`reach_ready()`), the r15 seed-press start sequence
  (`start_episode(k)`), the beige-panel `game_over(fr)` detector.
  Episodes start from a restored anchor: no boot per episode.
- Episode determinism was proven in R61 (byte-identical reps, 37
  cross-process dup groups) — the anchor + fixed press timing k is the
  seed mechanism.

### Perception layer (REUSABLE — frozen semantics)

- `ps1play.learn.visual_only` — `BirdObserverV7`, `GapTrackerV7`,
  `features_flappy_v7` (the exact 10-feature v7 layout), all
  numpy+stdlib only, AST-guarded by `tests/test_learning_boundary.py`.
- `ps1play.learn.perception` — `flappy_bird_y`, `flappy_gap_target_r15`,
  `flappy_green_mask` (full-res readers used for passage counting).
- Frame format: `_small_rgb` area-average 320×240 → 60×80×3 uint8.

### Policy layer (REUSABLE — independent)

- `deployment/flappybird_policy` — the R61 independent ONNX consumer:
  `load_policy(model_path, manifest_path)` → `predict / predict_batch /
  logits_batch / reset / close`, strict input contract (shape, dtype,
  finiteness, per-feature ranges), `identity()` (model+manifest
  SHA256), CLI smoke. Zero training/teacher imports (AST + subprocess
  proven). This is the ONLY policy the R62 runtime will load.

### Scoring / runner (REUSABLE, validation-flavored)

- `scripts/r57_lib.PassageCounter` — strictly-increasing visual pipe
  passage detector.
- `scripts/r61e_deploy_loop.py` — the R61 closed-loop validator:
  `build_vector` / `advance_history` / `fresh_perception` (the exact
  deployed state machine), `run_episode` (per-episode record +
  trace hashing). It is validation-focused (fixed budget, JSONL rows
  for the stats merge) and lives in `scripts/` with sys.path surgery.

### Plugin contract (EXISTING, different policy path)

- `ps1play.plugins.base.GamePlugin` + `plugins.contract` v1 — a
  RAM-feature-based agent contract (Metal Slug X / Tetrade / PSX-MC).
  It is NOT the frame-perception path and does not fit the learned
  FlappyBird policy; R62 builds the runtime on its own interface set
  but follows the same capability-negotiation philosophy.

## Current execution path for "AI plays FlappyBird" (as of R61)

```
scripts/r61e_deploy_loop.py (validation CLI)
  → FlappyEnv(workspace) → boot() → reach_ready()
  → for each (seed k, rep): start_episode(k)  [anchor restore + press]
  → loop: frame() → _small_rgb → build_vector → package.predict
          → advance_history → run(1, {B} | {})
          → passage fire + game_over check
  → episode JSONL row + trace hash
```

This works and is verified — but it is an evaluation harness: fixed
10,000-frame budget, no user-facing CLI, no live status, no
screenshots/video, no restart policies, no failure recovery UX, no
runtime manifest, and the glue lives in `scripts/`.

## Exact technical gaps (what R62 must add)

1. **No orchestration layer**: nothing owns boot→ready→episode→
   terminal→restart→shutdown as a first-class lifecycle with safety
   limits and cleanup guarantees.
2. **No interfaces**: GameAdapter / FrameSource / Policy / Controller /
   Emulator are implicit in the validation script, not documented
   contracts with tests.
3. **No one-command UX**: no `python3 -m ps1play play …` entry point,
   no live status, no `--episodes/--seed/--record/…` options.
4. **No observability**: no JSONL event stream, no episode summary
   files, no screenshots/video from the loop.
5. **No failure-recovery UX**: failures raise LoopError (good) but
   nothing guarantees controller release, emulator cleanup, exit codes,
   or persisted failure reports.
6. **No runtime manifest**: R61 pins model/ONNX hashes; the runtime
   (emulator build, ISO hash, python/deps, adapter versions,
   config hash) is recorded ad hoc per evidence file.
7. **No release gate for the runtime** (`ps1play verify`).
8. **No second-game adapter example** demonstrating the game-agnostic
   boundary.

## Reusable vs training-only dependency map

| Component | Reusable as-is | Notes |
| --- | --- | --- |
| `ps1play.api` / `core.host` | YES | emulator + capture + input |
| `FlappyEnv` boot/episode/game_over | YES | wrapped by the adapter |
| `visual_only` perception | YES | frozen semantics; AST-guarded |
| `deployment/flappybird_policy` | YES | the only policy path |
| `r57_lib.PassageCounter` | YES | scoring (import from scripts/ or vendored) |
| `r61e_deploy_loop` helpers | YES (logic) | re-implemented behind contracts with the same byte-exact behavior; the script itself stays untouched |
| Training modules (`r57f_es_ars`, dataset builders, teacher) | NOT imported by the runtime | training is CLOSED (R61) |
| `ps1play.plugins` (RAM-path) | NOT part of R62 loop | separate contract family |

## Environment (this session)

- Python 3.12.16 (uv cpython), numpy 2.1.3, onnxruntime 1.19.2,
  onnx 1.23.x, capstone (test-env), PIL 11.3.0, imageio (GIF).
- 2-core x86-64 container, CPU-only. Beetle PSX libretro core +
  OpenBIOS; FlappyBirdPSX v0.1.0 ISO (Unlicense homebrew) verified.
- Sandbox-recycle note: deps reinstalled this session (pinned
  versions); ISO re-fetched and hash-verified; the regression suite
  re-measured green at this exact HEAD.

## Conclusion

Everything R61 delivered is intact and verified. The R62 work is a
**runtime integration layer over proven components** — no emulator
rewrite, no perception rewrite, no policy change, no retraining. The
gaps are exactly: contracts, lifecycle, CLI/UX, observability,
recovery, manifest, gate, tests, docs.
