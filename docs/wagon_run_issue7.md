# Issue #7 — Wagon Run: sensor, live runs, and the honest count

Status: `PARTIAL` — sensor `IMPLEMENTED`+`TESTED`+`OBSERVED`, train
yard reached live (`OBSERVED`), the >= 50-wagon-crossed acceptance is
**NOT met** (honest). Commit: see git log (Issue 7 batch).

## What was built

- `ps1play/agent/wagon.py` — the wagon sensor: polls the VERIFIED
  entity table (base `0x800CA268`, stride `0x14C`, HP `+0x8E`) every
  10 frames; records spawn/despawn lifecycle events with full slot
  dumps (base64) for offline classification; persistent-slot tracking
  for wagon candidates. Observational only (no writes).
- `tests/test_wagon_sensor.py` — 6 unit tests (spawn/despawn,
  no-double-count, rate limit, persistence threshold, slot reuse,
  summary shape). Suite: **321 passed + 1 xfailed**.
- `scripts/wagon_run.py` — runner (nocheat + explore modes, continue
  rescue, pit-cadence explore).
- `scripts/wagon_v1.py` — the Task-12 v1 controller loop (the only
  flow that ever reached the train yard live) + sensor + disclosed
  continue counting + resume checkpoints + optional VERIFIED-freeze
  explore mode.
- `scripts/issue5_explore_invuln.py` — flag-gated `--wagon` sensor
  integration into the proven explore runner.
- Workspace probes: `scripts/wagon_scan_probe.py` (entity spawn-variant
  static scan), `scripts/arena_probe.py` / `arena_diag.py`
  (camera-gate diagnostics), `scripts/demo_replay.py` (attract-demo
  input recorder), `scripts/wagon_label.py` (offline periodic-sequence
  labeling).

## Live results (all OBSERVED with evidence)

| run | mode | chunks | continues | spawns recorded | notes |
|---|---|---|---|---|---|
| smoke_noc2 | nocheat | 30 | 0 | 96 | sensor pipeline validated |
| inv1 / inv2 | explore (pit cadence always-on) | 252 / 1200 | 0 / 1 | 170 / 1884 | pit cadence pins the run in the town arena |
| inv4 | explore + AA ladder + continue rescue | 1500 | 2 | 2326 | still gated by the town arena |
| v1a | no-cheat v1 loop | 700 | 0 | 649 | **reached the TRAIN YARD at ~c650** |
| v1b | no-cheat v1 loop | 1400 | 2 | 1323 | yard again, then continue -> menu slide -> attract reset |
| v1c | explore freeze + v1 loop | 1400 | 3 | 2452 | freeze changes traversal; town arena still gates |

Determinism evidence: v1a and v1b replay **bit-identically** until the
first continue (identical spawn-event fingerprints/cadence across the
first 48k frames) — the core + input stack is deterministic.

Train yard reached (photo evidence):
`work/msx_recomp/evidence/issue7_wagon_v1a/progress_c0650.png` — green
flatcars with POWs, armored soldier, water tower.

## Why the >= 50-wagon acceptance is NOT met (blocker chain)

1. **Town arena camera gate**: the truck + chopper set-piece hard-locks
   the camera until its scripted encounter resolves; the agent's fire
   cadences (burst, sustained UP+Y anti-air, grenades) did not resolve
   it in any run (frames: `issue7_arena_diag/`, `issue7_arena_probe/`).
   Web reference (arcadequartermaster, MS2 M1): the chopper squadron
   falls with its RED leader — targeted leader-kill is untested live.
2. **300 s mission timer per credit**: deep traversal requires
   continue-accepted checkpoint respawns; the countdown window is
   narrow and the post-menu flow accepts nothing (Task-13 probe).
3. **Attract-slide**: after a missed countdown the flow slides into
   menus/attract and eventually the boot-logo reset (frames:
   `issue7_wagon_v1b/progress_c1250.png` agetec logo, `c1300` story
   screen, `c1350` SNK logo).

Wagon-kind labeling from the recorded dumps: the recorded periodic
spawn sequences in these runs are the TOWN combat rhythms, not proven
wagon rides — no >= 50-wagon count is claimed. Per the acceptance
criteria pre-declared in the issue, the physical ceiling is documented
instead of rounding up.

## Next steps to the target

1. Solve the arena gate live (leader-chopper kill: sustained aimed
   UP+Y at the leader + truck bypass), with the sensor running.
2. Map the mid-mission checkpoint trigger (respawn point after the
   yard) so continues resume ON the train.
3. Ride with the sensor: each wagon passing = one lifecycle event of
   the wagon fingerprint cluster; label small/big from slot dumps
   correlated with spawn PNGs.
