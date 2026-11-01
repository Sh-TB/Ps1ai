# R62 User Guide — Watch the AI Play

## The one command

```bash
python3 -m ps1play play flappybird
```

What you see: a preflight banner (asset hashes verified), the boot,
live status lines (with `--verbose`), an episode summary when the
episode ends, and a final RUN SUMMARY. The process exits 0 and every
artifact lands in the output directory.

## The options that matter

| Option | What it does | Default |
| --- | --- | --- |
| `--episodes N` | N consecutive autonomous episodes, no input between them | 1 |
| `--seed K` | the episode seed (the start-press timing that seeds the game RNG) | ladder 6, 12, 18, … |
| `--record` | screenshots + GIF video of the actual gameplay | off |
| `--screenshot` | episode-end screenshots only | off |
| `--max-frames N` | per-episode frame budget | 10000 |
| `--max-runtime S` | wall-clock budget for the whole run | 300 s |
| `--config PATH` | JSON config file (CLI flags override it) | — |
| `--output PATH` | where results/videos/screenshots go | `scratch/r62/run_<UTC>` |
| `--verbose` | live status lines every 600 frames | off |

`--headless` is the default and only mode. `--show-window` is
deliberately NOT supported (the libretro core is headless); the CLI
rejects it with an actionable message — to WATCH the gameplay use
`--record` and open the GIF.

## Typical sessions

```bash
# a single bounded demo (safe default)
python3 -m ps1play play flappybird

# watch it play: record a 3-episode session with video
python3 -m ps1play play flappybird --episodes 3 --record --verbose

# a specific seed, one episode
python3 -m ps1play play flappybird --seed 45

# long evening run: as many 10k-frame episodes as fit in 30 minutes
python3 -m ps1play play flappybird --episodes 40 --max-runtime 1800 --record
```

## Stopping the runtime

`Ctrl+C` at any time: the runtime stops accepting decisions,
releases the controller, closes the emulator, persists a
`stopped` episode record and exits with code 130. There is no
orphaned process to kill (the core runs in-process).

## Where everything lands

Inside the output directory (`--output`, default
`scratch/r62/run_<UTC timestamp>/`):

| File | Content |
| --- | --- |
| `episodes.jsonl` | one line per episode: the full Stage-B record |
| `episode_001.json` | pretty per-episode summary |
| `events.jsonl` | the ordered event stream (boot, ready, episode_start/end, terminal, errors, manifest…) |
| `runtime_manifest.json` | the full environment identity (hashes, versions, config) |
| `shots/*.png` | gameplay screenshots (start, pipes, end) |
| `video_ep*_k*.gif` | the episode's animated gameplay |
| `trace_ep*_k*.jsonl` | per-frame decision trace (vector + action) |

## Reading the results

`result` is `alive` (survived the whole frame budget), `death` (the
game ended), `stopped` (a limit or Ctrl+C), or `error` (a typed
failure — see `errors` in the record and `docs/r62_troubleshooting.md`).
`pipes` counts pipe passages; `trace_sha256` identifies the exact
decision sequence (byte-comparable with the R61 evidence records).

## When the emulator crashes

The loop converts any core failure into a typed `EmulatorError`,
releases the controller, closes the session, writes the failure
episode record + event, and exits nonzero. Re-running the command
starts a fresh boot — no state survives, nothing to clean up by hand.

## Adding another game later

Implement one `GameAdapter` for the new game and register it (see
"Adding a second game" in `docs/r62_architecture.md`). The engine,
CLI, telemetry and gate are game-independent. The FlappyBird policy
itself does NOT generalize to other games — each game needs its own
perception and (eventually) its own trained policy.
