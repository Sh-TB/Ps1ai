# R62 Runtime Contracts

Every interface is an abstract class in `ps1play/runtime/interfaces.py`
with an enforcement test suite (tests/test_r62_runtime.py) and — where
the real components implement it — a byte-exact cross-check against
the R61 records (tests/test_r62_integration.py).

## Frame

| Field | Meaning |
| --- | --- |
| `seq` | monotonic capture counter per FrameSource |
| `emulator_frame_count` | the core's rendered-frame counter at capture — the ordering authority |
| `rgb` | (H, W, 3) uint8 (320×240 in-game) |
| `timestamp` | wall-clock at capture |
| `stale` | True when no new frame was rendered since the previous capture |

Contract: after `advance(1, …)`, `latest(require_fresh=True)` MUST
return a frame with a larger `emulator_frame_count`; two captures
without an advance raise `FrameError` on `require_fresh=True`.

## FrameSource

- `latest(require_fresh=True)` — the newest rendered frame; typed
  FrameError on stale/None/wrong-shape capture.
- `capture_latency_ms()` — EMA of capture cost.
- `close()` — idempotent.

## GameAdapter (per game)

| Method | Contract |
| --- | --- |
| `wait_ready(deadline_s)` | boot → ready state; `EmulatorError` on timeout |
| `start_episode(seed_k)` | deterministic episode start from a known state; resets per-episode state first |
| `observe(frame)` | frame → `GameObservation`; legitimate game situations (no pipe, no bird, occlusion) are v7 SENTINELS inside a valid vector — `valid=False` is reserved for hard failures and is NEVER sent to the policy |
| `legal_actions()` | the complete action vocabulary |
| `action_to_buttons(a)` | action → buttons held for EXACTLY one frame; unknown action ⇒ `AdapterError` |
| `note_action(d, o)` | called once per decision, AFTER decide, BEFORE next observe (history update) |
| `post_advance(frame)` | scoring + terminal on the post-action frame → `{pipe_passed, pipes, terminal, death_reason, …}` |
| `reset_episode()` | drops ALL per-episode state (observer, tracker, counters) |
| `snapshot()` | never-raising live-status dict |
| `episode_stats()` | `{pipes, actions, decisions}` for the generic result record |

### FlappyBird observation schema (frozen, v7)

`values` = float32[10], RAW (normalization lives INSIDE the ONNX
graph):

| i | name | meaning | sentinels/range |
| --- | --- | --- | --- |
| 0 | by | bird y, small-frame px | −1 = bird not detected |
| 1 | vy | bird vertical velocity px/frame | clipped [−10, 10] |
| 2 | gc | gap center y (GapTrackerV7-filtered) | raw finder value when no lock |
| 3 | dx | gap dx, small-frame px | — |
| 4 | g0 | gap top edge y | — |
| 5 | g1 | gap bottom edge y | — |
| 6 | flap_run | consecutive FLAPs by this policy | cap 9 |
| 7 | since_flap | frames since last FLAP | cap 99 |
| 8 | last_gc | last valid gap center | −1 = never locked |
| 9 | since_gap | frames since last valid gap reading | cap 40, starts 40 |

Actions: `HOVER` (no input) · `FLAP` (B / Cross for one frame — the
game's 2-frame pulse semantics are satisfied by one-frame decisions,
exactly the R61 record semantics). Terminal: the beige GAME OVER
panel detector. Ties in the model: ArgMax first-max ⇒ HOVER (inside
the graph).

## Policy

- `predict(observation) → ActionDecision` — refuses invalid
  observations (`RuntimePolicyError`); latency measured; identity
  exposed.
- `identity()` — name, package version, model_sha256, manifest_sha256.
- `reset()` / `close()` — per-episode + shutdown.
- The ONLY implementation used in production is `RuntimePolicy`
  wrapping `deployment/flappybird_policy` (the R61 independent
  consumer, numpy+onnxruntime, zero training imports). The model hash
  is verified against `data/learn/FINAL_MODEL_MANIFEST.json` BEFORE
  the first decision; a mismatch is `AssetError` (exit 3), never a
  warning.

## Controller

- `apply(decision, obs_frame)` — sends the input for exactly one
  frame; rejects illegal actions (`ControllerError`), duplicate frame
  sends, and post-stop sends; returns latency; records the send for
  the audit trail.
- `release_all()` — one empty-input frame; called on EVERY failure
  path and shutdown (never mid-episode in normal operation).
- `emergency_stop()` — latch; every further send raises until
  `reset_episode()`.
- Frame/action association: `observation frame N → decision N →
  input N → emulator advances → frame N+1` (tested).

## Emulator (EnvSession)

- `boot_new(config, deadline_s)` — factory; fail-early `AssetError`
  (ISO hash, BIOS, core, model); `EmulatorError` on deadline.
- `frames()` — the FrameSource.
- `advance(n, buttons)` — forward to the core; core exceptions mark
  the session dead → `EmulatorError`.
- `alive()` / `tag()` / `serialize()` / `unserialize()` / `close()`
  (idempotent; same-process re-boot verified).
- The core is IN-PROCESS (libretro via ctypes): there are no child
  processes to leak; "emulator termination" = core exceptions +
  session death, detected and typed.

## Lifecycle

`INIT → BOOTING → READY → EPISODE_ACTIVE → EPISODE_END → READY → … →
STOPPING → STOPPED|FAILED`; every transition is checked
(`LifecycleError`). RestartPolicy: episode cap / run time budget
(buffer = min(5 s, 5 %)) / consecutive-failure cap.

## Episode record (persisted per episode)

episode, game, seed_k, result (alive|death|stopped|error),
death_reason, pipes, frames, flaps, actions, decisions, errors,
wall_s, started/ended ts, trace_sha256 (byte-compatible with the R61
runner), policy name+hash, manifest hash, emulator tag, screenshots,
video, trace file.

## Runtime manifest (per run)

runtime version, repo commit, config + config hash, model/manifest
hashes, ISO hash+bytes, core hash, BIOS hash, python + dependency
versions, component versions. Written to `runtime_manifest.json`;
its hash rides on every episode record.
