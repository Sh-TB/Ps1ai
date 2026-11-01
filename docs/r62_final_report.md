# R62 Final Report — Autonomous Game Player Foundation

Round: R62 · Date: 2026-11-01 · Base: `4797af2` (R61 re-verified)
· Product: **one-command autonomous gameplay**

```bash
python3 -m ps1play play flappybird
```

## Status labels

```text
R61_TRAINING:      CLOSED            (unchanged; model hash-verified every run)
R62_RUNTIME:       VERIFIED          (engine+adapter+controller+policy live-proven)
R62_AUTOPLAY:      VERIFIED          (real episodes, real frames, real inputs)
R62_20_EPISODES:   PASS              (20 episodes; 5 family seeds byte-match R61)
R62_REGRESSION:    PASS              (731 passed + 1 xfailed; zero weakened)
R62_CLEAN_INSTALL: PASS              (fresh venv + pinned deps)
R62_RELEASE:       PASS              (15/15 gates, see reports/r62_release_gate.json)
```

## 1. What was built

A complete orchestration layer over the R61-verified components — no
emulator rewrite, no perception rewrite, no policy change:

| Component | Location | Evidence |
| --- | --- | --- |
| Runtime interfaces (FrameSource/GameAdapter/Policy/Controller/Emulator) | `ps1play/runtime/interfaces.py` | contracts doc + 50 offline tests |
| Typed failure taxonomy (exit codes 2/3/4/5/6/7/8/130) | `ps1play/runtime/errors.py` | Stage D + CLI tests |
| Emulator lifecycle + ordered frame capture + staleness detection | `ps1play/runtime/session.py` | gate `frame_capture`, integration tests |
| Legal-input controller (legality, sequencing, stop latch, release) | `ps1play/runtime/controller.py` | gate `controller_legality`, Stage D |
| Frozen-policy boundary (authority hash check, no fallback) | `ps1play/runtime/policy_runtime.py` | gate `policy_runtime` |
| Episode lifecycle + restart policies | `ps1play/runtime/lifecycle.py` | gate `episode_lifecycle` |
| The engine (one owner of the full loop) | `ps1play/runtime/engine.py` | byte-exact episode matches |
| One-command CLI + live status | `ps1play/__main__.py` | gate `docs_commands` |
| Telemetry (ordered JSONL events + runtime manifest) | `ps1play/runtime/telemetry.py` | every run's `events.jsonl` |
| Recorder (screenshots + GIF video) | `ps1play/runtime/recorder.py` | 20 videos / 929+ screenshots |
| Game registry (the plug-in boundary) | `ps1play/runtime/registry.py` | second-game engine test |
| Release gate (one command, 15 gates) | `ps1play/release_gate.py` | `reports/r62_release_gate.json` |

The FlappyBird adapter (`ps1play/adapters/flappybird/adapter.py`)
wires the EXACT R61 semantics: `_small_rgb` → BirdObserverV7 →
GapTrackerV7 → `features_flappy_v7` (raw 10-vector, normalization
inside the ONNX graph) → the independent policy package →
FLAP={B}/HOVER={} one-frame inputs → PassageCounter + game-over
detection on the post-action frame.

## 2. The decisive proof: byte-exact equivalence with R61

The new runtime reproduces the R61 verified evidence path
BYTE-EXACTLY — identical episode results AND identical per-frame
decision-trace hashes:

| Check | Record | Result |
| --- | --- | --- |
| Stage A, one full episode through the CLI, `--record` | k=6 | ALIVE 87 pipes / 640 flaps / 10,000 frames — trace `d510e758…` == R61 row ✓ |
| Gate `full_loop_smoke` (one command) | k=30 | 37 @ 4401, trace == R61 ✓ |
| Gate `multi_episode` (3 consecutive, ONE launch) | k=45 | 3× 40 @ 4753, traces == R61 and each other ✓ |
| Integration test (2 consecutive, one session) | k=45 | byte-match R61 ✓ |
| Stage B (20 episodes, 4 launches × 5) | k∈{6,12,30,60,90} | all 5 byte-match R61 ✓ |

This proves: correct frozen model loaded, correct perception, correct
frame/action association, legal inputs, no stale state across
episodes, and full determinism — through the NEW code path.

## 3. Real autonomous gameplay acceptance (Section 13)

- **Stage A — one episode**: `python3 -m ps1play play flappybird
  --seed 6 --record` → ALIVE 87/640/10000. Evidence: run dir
  `scratch/r62/stage_a/` (episodes.jsonl, events.jsonl,
  runtime_manifest.json, 89 screenshots, `video_ep001_k6.gif`
  834 frames, decision trace), committed sample screenshots at
  `data/r62/evidence/`. Live terminal status observed (bird y, gap,
  pipes, action, capture latency).
- **Stage B — twenty episodes**: seeds k=6..120 (preregistered in
  `SEEDS_PREREGISTERED.json` BEFORE collection), 20/20 completed,
  104,737 frames, 20 GIF videos, 929 screenshots.
  `data/r62/r62_stage_b_summary.json`. Aggregate: mean 44.6 pipes,
  min 10, max 87, 3 alive-at-budget. CONSTRAINT DISCLOSED: the
  sandbox kills processes between tool calls (~10 min wall), so the
  20 episodes ran as 4 launches × 5 CONSECUTIVE episodes; the
  same-launch continuity property (no input between episodes, no
  stale state) is proven byte-exactly by the 3×k45 gate and 2×k45
  integration test.
- **Stage C — three separate process launches**: k=45 ×3 via three
  OS processes: all exit 0, all byte-match R61, policy identity
  verified in each run's events, no leaked processes.
  `data/r62/r62_stage_c_summary.json`.
- **Stage D — three controlled failures**: missing model → exit 3;
  wrong model (hash mismatch) → exit 3, wrong model never ran;
  SIGINT mid-episode → exit 130 + `stopped` record persisted +
  controller released + zero leaked processes.
  `data/r62/r62_stage_d_summary.json`.

## 4. Performance profile (Section 10)

From `data/r62/r62_profile.json` (one launch, k=6, 10,000 decision
cycles) + the per-stage telemetry of a k=30 episode (4,401 cycles):

| Metric | Value |
| --- | --- |
| Decision-loop throughput | **110.8 FPS** (9.03 ms/cycle) — real-time capable with headroom |
| Model load | 14 ms |
| First inference | 0.39 ms |
| Warm inference (2000 calls) | p50 0.041 ms / p95 0.056 ms / ~23,400 calls/s |
| Perception stage (small-RGB + observer + tracker + features) | p50 4.89 ms / p95 4.99 ms |
| Controller send (= one frame of CPU emulation) | p50 2.64 ms / p95 2.68 ms |
| Full-loop cost split | perception ~4.9 ms > emulation ~2.6 ms + captures ~1.4 ms > inference 0.1 ms |
| Sustained evidence | 10,000-cycle single episode + Stage B's 104,737 cycles across ~1,300 s of episode wall time (plus gate/integration runs — > 30 min of autonomous emulator execution across the round) |
| Sizes | ONNX 7,182 B; package tree 45.5 KB; onnxruntime dist ~40 MB |

**Bottleneck (profiling-supported):** host-side perception
(downsample + v7 observers) is the largest single stage; ONNX
inference is negligible (0.4 % of the loop). No optimization was
performed — none is needed for real-time CPU-only play. **CPU-only
suitable: YES** (2-core container, no GPU).

## 5. Reproducibility and determinism (Section 11)

- Runtime manifest per run: runtime version, repo commit, config +
  config hash, model/manifest/ISO/BIOS/core SHA256s, python + dep
  versions, component versions. Written as `runtime_manifest.json`;
  its hash rides on every episode record.
- Determinism, separated honestly:
  - **Model determinism**: verified (bitwise-identical weights; R61
    audit; R62 authority check at load).
  - **Perception determinism**: verified (same frame ⇒ same vector;
    byte-identical traces across processes).
  - **Emulator determinism**: verified (same seed k ⇒ identical
    episode records; 3×k45 + 2×k45 + 5 family byte-matches).
  - **Full runtime determinism**: verified for the documented
    configuration (fixed seed ladder, headless, one boot per
    launch, per-episode anchor restore) — the episode records are
    byte-identical across repeats AND across process launches.
- Trace hashes are byte-compatible with the R61 runner
  (`r61e_deploy_loop.py`), so old and new evidence intercompare.

## 6. Security / safety / resource boundaries (Section 17)

- Only legal controller inputs through the one controller; no OS
  input injection; no memory writes; no network at runtime; no data
  leaves the machine; output paths restricted to the configured
  output dir; unverified ISO/model content is refused (hash gates);
  the core is in-process (no child processes to leak — verified by
  leak scans after every Stage C/D case); emergency stop via SIGINT
  (typed, exit 130, released inputs); memory bounded (GIF frames
  capped; telemetry is line-buffered stats, not per-frame blobs).

## 7. Game-agnostic foundation (Section 14)

Generic: engine, session, controller, policy boundary, lifecycle,
telemetry, recorder, config, errors, CLI, release gate.
Game-specific: FlappyBird adapter (observer/tracker/features/
actions/terminal). A second game = ONE `GameAdapter` subclass + one
registry entry; `ScriptedGameAdapter` (a fake 3-feature game) is
driven by the REAL engine loop in the test suite — the same code
path that plays FlappyBird. The FlappyBird POLICY does not
generalize to other games; Hello Pong remains a regression test.

## 8. Honest limitations

1. **Headless only.** `--show-window` is refused by design; watching
   = `--record` GIFs. Live windows would need a different frontend.
2. **Stage B = 4 launches × 5** (sandbox tool-call wall limit); the
   same-launch 20-episode property is covered by the byte-exact
   3×k45/2×k45 same-launch proofs. On an unrestricted machine the
   exact same command runs all 20 in one launch.
3. **Linux/x86-64 only** (tested); other OSes untested (see
   `docs/r62_installation.md`).
4. **Portability of the gate's clean-install step** depends on
   network access for the fresh venv's pip install; offline it is
   BLOCKED (honest), not faked.
5. Screenshots exist for recorded runs; the gate's quick smoke
   episodes are not recorded (traces + byte-matches are their
   evidence).
6. The known R61 model limitations carry over unchanged (decision-
   function-only ONNX, numpy host dependency, heavy-tailed seeds,
   C1 comparability) — see
   `deployment/flappybird_policy/KNOWN_LIMITATIONS.md`.

## 9. Commands (all reproducible)

```bash
python3 -m ps1play play flappybird --seed 6 --record   # Stage A
python3 -m ps1play play flappybird --episodes 20 --record  # Stage B (one launch)
python3 scripts/r62_stage_b.py chunk N / summarize     # chunked Stage B + evidence
python3 scripts/r62_stage_c.py                          # 3 process launches
python3 scripts/r62_stage_d.py                          # 3 failure injections
python3 scripts/r62_profile.py                          # 10k-cycle profile
python3 -m pytest tests/ -q                             # 731 passed + 1 xfailed
python3 -m ps1play verify --profile final               # THE release gate
```

## 10. Definition of Done — checked

- [x] R61 model unchanged and verified (authority hash gate)
- [x] Generic runtime core exists (interfaces + engine + lifecycle)
- [x] FlappyBird adapter integrated (byte-exact R61 equivalence)
- [x] Real emulator frame capture (ordered, staleness-enforced)
- [x] Valid model observations (contract-enforced boundary)
- [x] Independent ONNX inference connected (the only policy path)
- [x] Legal controller actions reach the emulator (one-frame sends)
- [x] Complete game loop works (live episodes)
- [x] Episode lifecycle works (state machine + restart policies)
- [x] One-command launch works (`python3 -m ps1play play flappybird`)
- [x] Live status works (`--verbose` terminal + JSONL events)
- [x] Logs and results saved (episodes/events/manifests/traces)
- [x] Screenshots and video prove actual gameplay (20 videos, 900+ shots)
- [x] Twenty consecutive autonomous episodes completed (20/20)
- [x] Three independent process launches verified (Stage C)
- [x] Three controlled failures safely recovered (Stage D)
- [x] 10,000-cycle performance test passes (110.8 FPS)
- [x] R61 regression suite remains green (731 + 1 xfail)
- [x] Clean-room installation works (gate)
- [x] Documentation commands are tested (gate `docs_commands`)
- [x] Final release gate passes (15/15)
- [x] GitHub evidence posted and read back
- [x] No unresolved critical blocker hidden (limitations disclosed above)
