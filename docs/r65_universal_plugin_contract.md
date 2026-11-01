# R65 Universal Plugin Contract — one game, one isolated plugin, one knowledge package

Round: **R65** · Part D deliverable.

## 0. The rule

**The runtime is shared. The game intelligence is not.**

Every game integrates as ONE isolated module (`ps1play/adapters/<game_id>/`)
that registers into the generic registry. The shared runtime (`ps1play/runtime/`,
`ps1play/knowledge/package.py`, the CLI, the release gate) contains ZERO
game-specific semantics: no game's memory addresses, no gameplay action
meanings, no objective detectors, no observation schemas, no policies.
Cross-game knowledge transfer is prohibited by construction and by test
(`tests/test_r65_packages.py::test_no_cross_game_references`).

Shared (generic) infrastructure — allowed and declared: emulator lifecycle,
controller delivery, frame capture, telemetry/logging, CLI, package
export/install machinery, the test runner, plugin registration, error
recovery, generic evidence verification.

## 1. The contract (v2 — as implemented by the three runtime games)

A game plugin is a Python package `ps1play/adapters/<game_id>/` providing:

### 1.1 The adapter (`adapter.py`, class `*Adapter(GameAdapter)`)

| contract method | obligation |
|---|---|
| `wait_ready(deadline_s)` | drive boot → the game's VERIFIED ready state; raise `EmulatorError` on timeout; success is the verdict that marks READY (the engine re-boots a fresh core on failure — boot retry, R64) |
| `start_episode(seed_k)` | begin one episode from a known state (seed labeling-only under zero-writes); state-driven recovery from every reachable resting state (menu/game-over) using LEGAL input only; return frames consumed |
| `observe(frame)` | build the game's `GameObservation` (the vector layout is documented in the module docstring and cross-checked by tests); legitimate game states are IN-vector sentinels; invalid is only a hard failure |
| `legal_actions()` | the complete legal action vocabulary |
| `action_to_buttons(action)` | the exact button frame semantics (per-game timing traps are owned HERE — e.g. Tetrade's ≤4-frame START taps, BuzzyBee's 2-frame flap press pipeline) |
| `note_action(decision, obs)` | per-decision history update (exact deployed semantics) |
| `post_advance(frame)` | progress + terminal detection; returns the generic record keys (`pipe_passed`/`pipes`/`terminal`/`death_reason`) plus game diagnostics |
| `reset_episode()` | drop ALL per-episode state |
| `snapshot()` | human-readable state (never raises) |
| `episode_stats()` | the generic counters (`pipes` = the game's progress label, `actions`, `decisions`) |

Identity class attributes: `game_id`, `version`.

### 1.2 The policy (`policy.py`, class `*Policy(Policy)`)

`predict` / `legal_actions` / `reset` / `identity` / `close`. Either:
* a **built-in heuristic** (hand-written, no model, no training —
  Tetrade's Dellacherie 2-ply, BuzzyBee's bot_policy8), registered via a
  `policy_factory`; or
* the **frozen-model RuntimePolicy** (FlappyBird's ONNX champion with the
  authority-manifest verification).

`identity()["model_sha256"]` MUST pin the policy source file's sha256
(hand-written case) or the model artifact's sha256 (frozen case). No
policy may import another game's module.

### 1.3 Registration (`ps1play/runtime/registry.py`)

ONE `register_game(...)` call: `env_factory` (disc/workspace wiring via
`GAME_DEFAULT_ISO`), the adapter class, the optional policy factory, and
the game's `progress_label` (the ONE human name of the generic progress
counter: pipes / lines / score). Adding a game requires NO runtime-core
edits (R64's two generic seams — `policy_factory` and boot retry — are
the only core hooks; both are game-agnostic).

### 1.4 Disc pins (`ps1play/runtime/session.py`)

`GAME_DEFAULT_ISO[game_id]` + `EXPECTED_ISO_SHA[game_id]`: the exact disc
bytes every record was made with, verified at preflight. User-supplied
discs are honored via `config.iso_path` (the user's own legal copy).

### 1.5 The knowledge package (`package_spec.py`, `build_spec()`)

The game's OWN descriptor for its downloadable `.ps1game`: identity,
maturity, file list (plugin sources, RE knowledge, evidence, tests, disc
pin), runtime compatibility, capabilities, legal notes, README. The
package machinery (`ps1play/knowledge/package.py`) is generic; the
content is per-game and isolated.

## 2. The required validation ladder (per plugin)

The generic test harness (`pytest`) executes every layer; all game-specific
test data and semantics live in the game's own test files:

1. **Offline contract tests** — observation layout, action legality and
   button mapping, terminal detection, episode counters, press-timing
   traps, policy invariants (FakeEnv RAM fixtures; no emulator).
2. **Identity tests** — game registration, progress label, disc pin,
   policy source sha.
3. **Boot / ready-state tests** — state-machine recovery sequences
   (fake-env).
4. **Real-emulator integration tests** — through the REAL RuntimeEngine
   (the product path), module-scoped boot, honest skip when the disc is
   absent (the R61/R62/R64/R65 convention).
5. **Knowledge-package tests** — the game's spec exports, validates,
   installs; its tests ship inside the package and run via
   `python3 -m ps1play test <game>`.

Current conformance: flappybird (5 shipped test files), tetrade (2),
buzzybee (2), metal_slug_x (diagnostic package, no tests — honestly
declared `test_command: None`).

## 3. What a new game's integration must NOT do

* No game-specific conditional branches in the shared core.
* No cross-imports between adapter packages.
* No shared "gameplay knowledge" files (a generic constant that happens
  to equal another game's constant is not knowledge transfer; a copied
  policy, address table, observation schema or action semantic IS).
* No new issue claims, no weakened regression expectations — when the
  product legitimately grows, the pinning test is widened WITH an
  in-test explanation (done once this round for the registry list).

## 4. The worked examples

* `ps1play/adapters/flappybird/` — the frozen-model pattern (R62).
* `ps1play/adapters/tetrade/` — the built-in-policy pattern (R64) +
  the R65 measured-anchor correction (policy v1.1.0).
* `ps1play/adapters/buzzybee/` — the R65 end-to-end example: third
  runtime game, proven-planner port, press-pipeline timing trap,
  state-driven recovery, package with disc-build tools.
* `ps1play/adapters/metal_slug_x/` — the diagnostic-knowledge pattern:
  package WITHOUT a runtime adapter (no overclaim).
