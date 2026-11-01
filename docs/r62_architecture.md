# R62 Architecture — the Autonomous Game-Playing Runtime

## The product

```bash
python3 -m ps1play play flappybird
```

One command boots the emulator, loads the frozen R61 policy, plays the
game autonomously, shows live status, records evidence, and shuts down
safely. No manual orchestration, no scripts to glue.

## The loop (who owns what)

```text
User command (ps1play.__main__ "play")
  └─ RuntimeEngine  (ps1play/runtime/engine.py)  — THE orchestrator
       ├─ preflight: assets + hashes (session.preflight)
       ├─ runtime manifest (telemetry.build_manifest)
       ├─ EnvSession (session.py)   — emulator lifecycle
       │    ├─ boots the proven FlappyEnv (beetle core, OpenBIOS)
       │    ├─ EnvFrameSource: ordered captures, staleness flag
       │    └─ advance() / serialize / close (idempotent)
       ├─ FlappyBirdAdapter (adapters/flappybird/adapter.py)
       │    ├─ wait_ready / start_episode (the r15 seed-press flow)
       │    ├─ observe: _small_rgb -> BirdObserverV7 + GapTrackerV7
       │    │   -> features_flappy_v7 (the RAW 10-vector)
       │    ├─ note_action: the exact deployed history update
       │    ├─ action_to_buttons: FLAP={B}, HOVER={} (legal input)
       │    └─ post_advance: PassageCounter + beige game_over
       ├─ RuntimePolicy (policy_runtime.py) — the ONLY policy path
       │    └─ deployment/flappybird_policy (independent ONNX
       │        consumer; authority-manifest hash check BEFORE use)
       ├─ SafetyController (controller.py) — the ONLY input sender
       │    └─ legality + one-frame pulses + sequencing + stop latch
       │       + release_all on every failure/shutdown
       ├─ Lifecycle + RestartPolicy (lifecycle.py)
       │    └─ INIT→BOOTING→READY→EPISODE_ACTIVE→EPISODE_END→…
       │       restart: fixed count / time budget / failure cap
       ├─ Recorder (recorder.py, optional): screenshots + GIF video
       └─ TelemetryLog (telemetry.py): ordered JSONL events + the
           runtime manifest + latency percentiles
```

## Design decisions (and why)

1. **Wrap, don't rewrite.** The emulator core (beetle via ctypes),
   the game boot flow, the perception (BirdObserverV7/GapTrackerV7),
   and the policy consumer are the R61-verified components. The
   runtime adds contracts and an owner around them; it duplicates
   none of them. `runtime/scoring.PassageCounter` is the one vendored
   exception, equivalence-tested against `scripts/r57_lib` on 200
   randomized sequences (tests/test_r62_runtime.py).

2. **One capture per emulator frame.** `frame_rgb()` returns the last
   RENDERED frame. The loop therefore reuses the post-advance frame
   as the next decision's observation — decision N sees exactly the
   frame its action N-1 produced (the mission's frame/action
   association contract), and staleness is detectable: the core's
   `frames_run` counter must advance between captures, else the frame
   is stale (`FrameError` on require_fresh). This is also why the
   runtime reproduces R61 traces byte-exactly.

3. **The policy boundary is hard.** RuntimePolicy refuses invalid
   observations, verifies the model hash against the AUTHORITY
   manifest (`data/learn/FINAL_MODEL_MANIFEST.json`) before the first
   decision, and there is NO fallback path — a policy failure stops
   the run (typed `RuntimePolicyError`, exit 6). Training/teacher
   modules are never imported.

4. **The controller is the only input sender.** Legal actions come
   from the adapter; a send names its frame; duplicates and
   post-terminal sends raise; `release_all()` emits one empty-input
   frame on every failure/shutdown so no button latches.

5. **Failures are typed and always cleaned up.** Every failure mode
   maps to a `Ps1RuntimeError` subclass with a shell exit code
   (config 2, assets 3, emulator 4, controller 5, policy 6, adapter
   7, lifecycle 8, emergency stop 130). The engine persists an error
   episode record, releases inputs, closes the core, flushes
   telemetry, and returns a nonzero exit code. `stop_on_error` (the
   default) means a broken environment ends the run; the restart
   policy additionally caps consecutive failures.

6. **Determinism is measured, not assumed.** Same seed k ⇒ identical
   episode records (the emulator is deterministic; R61 proved it,
   R62 re-proves it through the new runtime: three consecutive k=45
   episodes byte-match each other AND the R61 record). The runtime
   manifest + per-episode `trace_sha256` make any divergence visible.

## Adding a second game (the reuse boundary)

Generic (written once, game-independent): `runtime/engine.py`,
`session.py`, `controller.py`, `policy_runtime.py` (per policy
artifact), `lifecycle.py`, `telemetry.py`, `recorder.py`,
`config.py`, `registry.py`, `errors.py`, the CLI, and the release
gate.

A new game implements ONE class — a `GameAdapter`:

```python
from ps1play.runtime.interfaces import GameAdapter

class MyGameAdapter(GameAdapter):
    game_id = "mygame"
    # wait_ready:      drive boot -> "press start" state
    # start_episode(k): begin a deterministic episode from a known state
    # observe(frame):  frame -> GameObservation(values=your_vector)
    # legal_actions:   ("IDLE", "MOVE", ...)
    # action_to_buttons: action -> frozenset of buttons for 1 frame
    # post_advance:    score + terminal detection on the post-frame
    # reset_episode:   drop ALL per-episode state
    # snapshot / episode_stats: live status + generic counters
```

then register it:

```python
from ps1play.runtime import registry
registry.register_game("mygame",
                       env_factory=my_env_factory,
                       adapter=MyGameAdapter)
```

The engine, CLI, telemetry, lifecycle, fault handling and release gate
pick it up unchanged. `ScriptedGameAdapter`
(tests/test_r62_runtime.py) is a working example: a fake 3-feature
game driven by the REAL `RuntimeEngine` loop — the same code path that
plays FlappyBird. A second real game still needs its own perception
(e.g. its own observer) — the FlappyBird model does NOT generalize.

## What the runtime is NOT

- Not a training system: training is CLOSED (R61). No optimizer, no
  teacher, no dataset code exists on this path.
- Not a universal AI framework: one registry entry per game, no
  plugin market, no auto-discovery.
- Not cross-platform yet: Linux/x86-64 CPU-only (the core is a
  Linux .so; Windows is an untested secondary investigation — see
  docs/r62_installation.md).
