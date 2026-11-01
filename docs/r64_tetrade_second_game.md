# R64 — Tetrade, the Second Runtime Game

**Status: EXECUTED** (2026-11-01) · **Tracking: Issue #15** · **Training: CLOSED** (nothing retrains; the Tetrade policy is hand-written)

`python3 -m ps1play play tetrade` now works exactly like `play flappybird` —
the same engine, controller, telemetry, lifecycle, CLI and exit-code
vocabulary, a second registered game, zero runtime-core game knowledge.

## 1. What shipped

| Piece | Where | Notes |
| --- | --- | --- |
| GameAdapter | `ps1play/adapters/tetrade/adapter.py` | the full `GameAdapter` contract; RAM-read perception over the `TetradeGame` struct; the R63-proven entry/restart sequences |
| Policy | `ps1play/adapters/tetrade/policy.py` | the R63 Dellacherie 2-ply planner ported verbatim behind the runtime `Policy` contract; per-frame realization; identity = sha256 of the policy source |
| Registry entry | `ps1play/runtime/registry.py` | `tetrade` = env factory + adapter + **policy factory** + `progress_label="lines"` |
| Disc pin | `ps1play/runtime/session.py` | default cue `patched/tetrade_lic.cue`; sha256 `7eb38eda…` hard-checked at preflight |
| Config | `ps1play/runtime/config.py` | the game whitelist is now **registry-driven** (`registered_games()`) |
| Engine seam | `ps1play/runtime/engine.py` | `policy_for_game()` (built-in heuristic vs frozen model) + **boot retry** |
| CLI | `ps1play/__main__.py` | `play tetrade`; the summary prints the game's progress label (`lines`) |

## 2. The two generic runtime amendments (R64)

The R62 recipe ("a new game implements ONE class") needed exactly two
generic extensions — both game-agnostic, both in the written-once layer:

1. **Per-game policy factory** (`registry.policy_for_game`). Tetrade's
   policy is a built-in hand-written heuristic, not a frozen ONNX
   package; when a registered game ships no factory, the engine falls
   back to `RuntimePolicy` exactly as R62 did. No game names appear in
   the engine.
2. **Boot retry** (`config.boot_retries`, default 2; `engine.boot`).
   beetle keeps global emulator state: an in-process boot may stick
   forever at the OpenBIOS cube (observed and screenshotted
   2026-11-01; the #5 worklog recorded "a second in-process boot never
   yields a clean core"). The adapter's `wait_ready` is now the
   VERIFIED ready state — for Tetrade it drives the full entry and the
   struct scan, so a wedged boot FAILS the scan — and the engine
   answers by re-booting a fresh core (up to `boot_retries`).

The manifest is now per-game (`runtime_manifest_version` 2): the
component versions come from the registry, and the policy identity in
the manifest is the policy that actually runs.

## 3. Tetrade specifics (all R63 evidence, productized)

* **Anchor map** (verified live again this round, base `0x1FECA0` —
  the round-10 prior AND the R63 observation, now three independent
  boots): matrix[20][10]@+0, tetrimino{type@+800, x@+868, y@+872,
  rot@+880}, nextTetriminos[0].type@+896, score@+2276,
  single/double/triple/tetrade @+2280..2292, level@+2304,
  isGameOver@+2312, isGamePaused@+2316.
* **Entry sequence**: boot settle 960f → START 120f (title→menu) →
  B/CROSS 12f on ">Marathon Mode<" → START taps **≤ 4f** (the R63
  key-repeat trap: a 60f hold lands PAUSED) → countdown 280f → tap →
  tail. The struct scan (full window range, transient `type=-1`
  accepted, live-piece retry) is the readiness verdict.
* **Episode ≥ 2**: the previous episode may have ended ALIVE at its
  frame budget (mid-play, no continue screen). The adapter then
  finishes the game LEGALLY — hard-drop every live piece (UP),
  unpause taps if needed — until the natural spawn-overlap game over,
  refuses the continue with CIRCLE, and re-enters. The entry retries
  up to 3 attempts with the state-driven recovery ladder (R63's
  failed-entry ledger, automated).
* **Actions** (one frame each): `IDLE`, `ROT_CW` (A/CIRCLE),
  `MOVE_L`/`MOVE_R`, `HARD_DROP` (UP), `PAUSE_TOGGLE` (START).
* **Observation**: 222 float32 values — board 200, current-piece
  one-hot 7, rot/x/y 3, NEXT one-hot 7, score/lines/level 3,
  over/paused 2. All legitimate game states (respawn transient, pause,
  game over) are IN-vector.
* **Seed honesty**: `seed_k` is recorded for labeling only — the
  zero-writes rule forbids seeding the game's internal RNG.
* **Episode record**: the generic `pipes` column carries LINES CLEARED
  for this game (registry `progress_label="lines"`); full state lives
  in the diagnostics and the trace.

## 4. Acceptance evidence (committed under `data/r64/`)

Real run: `python3 -m ps1play play tetrade --episodes 2 --record
--verbose` (one launch, boot attempt 0, ready base `0x1FECA0`):

| | ep1 (k=6) | ep2 (k=12) |
| --- | --- | --- |
| result | death (natural game over) | death (natural game over) |
| decision frames | 2,038 | 2,831 |
| real button presses | 124 | 165 |
| pieces hard-dropped | 23 | 33 |
| lines cleared | 0 | **1** (verified: `single` counter + score forensics) |

* **NEXT-promotion cross-check: 53/53 (100%)** — every piece the 2-ply
  policy planned against the NEXT piece was the piece that actually
  appeared (frame-accurate from the committed traces; the lock/respawn
  window is excluded exactly as R63's post-settle read was).
* **Score forensics on the clear**: score +26 at the clear row =
  hard-drop cells (+2/cell × 13); the SINGLE itself adds 0 at level 0,
  exactly per `SINGLE_LINE_SCORE * level` in the MIT source — the same
  finding as R63, now through the product path.
* **Restart flow exercised**: ep2 started via the recovery/restart
  path (`start_frames=1058` = forced finish + continue refusal + entry)
  and played fresh (score/lines zeroed at start).
* Evidence: `data/r64/episodes.jsonl`, `events.jsonl`,
  `trace_ep001_k6.jsonl`, `trace_ep002_k12.jsonl`,
  `r64_acceptance_summary.json` (written by `scripts/r64_verify_run.py`),
  `evidence/video_ep00{1,2}_k{6,12}.gif`, `evidence/ep001_k6_end_death.png`,
  `evidence/episode_00{1,2}.json`, `evidence/runtime_manifest.json`.

## 5. Tests

`tests/test_r64_tetrade.py` — 49 offline contracts: geometry/evaluation
vs hand-computed boards, the policy state machine (cooldowns, tap caps,
fuse, respawn/pause/over, identity hash), the adapter over a fake env
(vector layout, entry/restart budgets, the short-tap rule, legal
finish-of-budget, struct scan on synthetic RAM incl. decoys and the
paused variant), registry/config/CLI wiring.
`tests/test_r64_integration.py` — 4 real-emulator tests through the
REAL `RuntimeEngine` (boot + verified ready at `0x1FECA0`; a 450-frame
episode; two episodes in one launch proving the restart flow).

Full suite at R64 head: **782 passed + 2 skipped (owner-local exe) +
1 xfailed** — R62's 731+1 preserved, zero weakened. The R62 release
gate re-run **15/15 PASS** (`reports/r62_release_gate.json`,
342 s) including the byte-exact R61 family reproduction
(k=30 = 37@4401; 3×k45 = 40@4753) — the generic amendments changed
nothing for flappybird.

## 6. Honest limits

* Tetrade perception is **RAM-read-based** (the loop Issue #8 itself
  documents; R63 precedent). The flappy vision model does not
  generalize and is not used. No training anywhere.
* The heuristic policy is legal but weak (this run: 1 clear / 56
  pieces; R63: 1/28). The DoD bar is a verified clear + natural game
  over, not a score target.
* Piece sequences are not seed-controlled (zero-writes rule).
* The NEXT-promotion check reads frames; the lock/respawn window is
  excluded by design (three rows per piece), stated in the analyzer.
* beetle's in-process boot flakiness is MITIGATED (verified-ready +
  boot retry), not eliminated: a degraded boot costs time, not
  correctness (a third boot in one launch is bounded by
  `boot_retries=2`).
* Linux/x86-64 only; headless only (watch = `--record` GIFs).
