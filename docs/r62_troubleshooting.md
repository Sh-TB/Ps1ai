# R62 Troubleshooting

Exit codes are the diagnostic: **2** config · **3** assets ·
**4** emulator · **5** controller · **6** policy · **7** adapter ·
**8** lifecycle · **130** interrupted · 0 = clean run.

## Exit 3 — "game disc not found / ISO hash mismatch"

The disc path is resolved from `--config iso_path` or the default
`/home/z/my-project/emu/games_homebrew/flappybird.cue`. Fix:

```bash
python3 scripts/r53_fetch_flappy.py    # re-fetch + hash-verify the ISO
```

The runtime hard-verifies SHA256 `b45871d3…` (the exact FlappyBirdPSX
v0.1.0 build every historical record used). A different build is
refused — that is a feature: results stay comparable.

## Exit 3 — "model hash mismatch"

The ONNX artifact does not match `data/learn/FINAL_MODEL_MANIFEST.json`
(the R61 authority). Restore it:

```bash
git checkout -- deployment/flappybird_policy/models/r60_soup_e6a010.onnx
```

The runtime NEVER runs an unverified model.

## Exit 4 — emulator boot failed / died

- Check the core path: `python3 -c "from ps1play.api import DEFAULT_CORE; print(DEFAULT_CORE)"`.
- Check OpenBIOS: `third_party/openbios/openbios.bin` must exist.
- Look at `events.jsonl` (`emulator_boot`, `episode_error`) for the
  exact core message.
- Re-run: every boot is fresh; there is no stale state to clean.

## Exit 6 — policy rejected the observation

The package's strict input contract caught an out-of-range/NaN
vector. This indicates an adapter/frame problem, not something to
bypass. Check the observation diagnostics in `events.jsonl` and file
the frame id (`seqN@emuM`).

## "stale frame" FrameError

The emulator rendered nothing new between two captures — either a
wedged core (re-run) or a bug in a custom adapter's frame flow. The
normal loop captures once per advance and cannot hit this.

## The run is slower than expected

~20–25 frames/s is the expected CPU-only closed-loop speed
(emulation dominates; inference is ~0.04 ms — see
`docs/r62_final_report.md` §profile). Use `--max-runtime` to bound
wall time; the episode record shows its own `wall_s`.

## Ctrl+C left something running?

It cannot: the core is in-process, `SIGINT` triggers release+close,
and the test suite verifies cleanup. If the terminal is wedged by a
`--verbose` status line, just press Enter.

## Disk full / log dir unavailable

Telemetry writes are best-effort: a failed write is recorded as a
warning and the run CONTINUES (the control loop never dies from
logging). Episode records persist to `episodes.jsonl` — if that
fails too, the failure is in the events and the exit code still
reflects the run.

## Where to look first

1. the process stderr (typed error + message),
2. `<output>/events.jsonl` (the ordered story),
3. `<output>/episode_00N.json` (the failing episode's record),
4. `docs/r62_runtime_contracts.md` (what each error type means).
