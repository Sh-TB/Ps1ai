#!/usr/bin/env python3
"""post_issue6_round9.py — Issue #6 round-9 report + Issue #7 wagon-run
note + Issue #5 session-12 cross-ref."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY6 = """**Round 9 (50/50) — Tetrade TETRIS x2 + natural level-2 + the
full drop-rate ladder (5/5 gates CAUSAL, policy untouched), MSX
armored-trio kill CAUSAL + decisive CAMERA-HELD negative at the new
px-2212 arena pin (issue #7), PSXMC place6 honest probe FAILED with
two instrument findings.** Commit `f082179`, suite **489 passed +
1 xfailed**.  All three subagent lanes hit the Task-tool infra
timeout on their return messages (round-8 precedent); every lane's
work was recovered complete from disk and the remaining executions
were driven directly by the orchestrator.

## Tetrade — 2-ply engine swap (round-7 playloop policy untouched), 5/5 gates CAUSAL

- `scripts/tetrade_r9_tetris.py`: Tetrade2PlyAI (Dellacherie eval +
  explicit TETRIS bonus) swapped into the policy's engine slot; the
  NEXT piece is read from live RAM (nextTetriminos[0].type @
  struct+896) with a frame-granular promotion cross-check: **715/715
  exact** — the read is honest.
- Live run (ws_tetrade_r9, one boot, 3 cycles, 710 pieces, 269
  clears, 172 s): **G1** calibration CAUSAL (profile anchor 0x1FECA0
  + LEFT/RIGHT x-displacement probe).  **G2 TETRIS x2**: fc8560
  level 5, score 22058->27084 = **+5000 = 1000x5 exact**; fc29039
  level 14, 170108->184108 = **+14000 = 1000x14 exact**; pre-vanish
  PNG ring (tetris_pre0..8) + clear PNGs; clears_by_type d1 175 /
  d2 34 / d3 6 / **d4 2**.  **G3** natural level 1->2 flip **x2**
  (lines 17->18 and 16->17 vs threshold 8*(level+1)=16) with 11
  level-2 clears all matching the table — and 35 level flips total
  (max level 18; two natural game overs lv15->0, lv18->0).  **G4**
  level-2 cadence: **86/86 clean gaps = exactly 13 f/cell** (source
  30/(1.10*2)).  **G5** score suite: level 0 12/12 zero, level>=1
  **205/205** match 200/500/700/1000 x level.
- **NEW — the full drop-rate ladder measured for the first time**
  (rounds 7-8 had only 30->27->13): per-level clean-window medians
  L0..L18 = 30/27/13/9/6/5/4/3/3/3/2/2/2/2/1... (n=98..463 each,
  min=max at L0..L13).  Evidence: `scratch/issue6_round9_tetrade/`
  (r9_report_main1.json, r9_sim.json — the offline sim predicted
  7-9 tetris per 12 lives for all three variants).

## MSX (issue #7 WAGON RUN) — the arena pin gets captured and killed; the gate holds anyway

- Three sensor walks (one boot each, continues counted+disclosed —
  71 total): T4 (55,524 f, px~1596 pin, truck visible), cap v1
  (70,351 f, **max_px 2212.0** — deepest M1 traversal of the
  campaign, 1,365 wagon-sensor spawn events), cap v2 = **PIN-BASED
  capture** (alive AND px >= 1400 AND < 10 px window over >= 360 f)
  -> savestate `wr9_arena` at px 2212.0 with a 35-slot census.
- The pin is held by **THREE 300-HP armored ground enemies (st
  0xA0D0, slots 10-12)** — the same armored-HP class as the
  choppers; the entity-class gate that failed in T4/cap1 was
  replaced by the pin signature (targetable set extended to
  0xA0D0/0xAB94, disclosed).
- **Arm YB** (the issue-doc web strategy: sustained AIMED UP+FIRE at
  the reddest/nearest 300-HP target): **8 kills** (slots 10+11,
  score 9709->10209, +500 each), SQUADRON_FELL x4 — and the camera
  HELD: 0/4 resolution attempts; the 300 s timer + respawn waves
  kill the player before any walk probe.  **Arm J1** (the session-3
  proven hop+UP-lob): kills land faster (cycle 2-3), same 8 kills,
  same SQUADRON_FELL x4, camera HELD 0/4; slot 12 (behind the
  player) was never reachable.
- **Verdict: armored-kill CAUSAL (16 kills, exact +500 steps);
  CAMERA-HELD — decisive negative for "the squadron falls with its
  red leader" AT THIS PIN.**  Three pin profiles now mapped (1164
  flyover ambush / ~1596 T4 truck pin / 2212 armored trio); the
  train yard remains unreachable in one boot.  Instruments:
  `msx_wr9_{arena,cap,cap2,leaderkill}.py`.  Evidence:
  `scratch/issue6_round9_msx/` (arena_t4, cap, cap2, leaderkill).

## PSXMC — place6 honest probe failure with two instrument findings

- `scripts/psxmc_r9_place6.py` (the round-8 recorded lever: ray-
  directed aim with a LIVE raycast map via the R2 breaking-state;
  stable-frame grabs = two consecutive bit-exact frames; no camera
  movement between pre/after).  One-character runtime fix: LOOK_LEFT
  "Q" -> "SQ" (inputmap name).
- The probe honestly FAILED: the fresh-boot spawn differs from the
  r7/r8 worlds (player at [0, 9.62, 0]) and the R2 breaking-state
  map returned **no hits at any pitch 5..80 deg** (in_reach [],
  ground_block_y null); the CONTROL arm (5 deg, geometrically
  cannot place) still showed world_px 26,605 with no input — the
  fresh world is not static between pre/after (mobs/clouds).
  Verdict: **FAILED(probe)**; place stays OPEN with two recorded
  fixes for round 10: (1) bit-exact stability gate immediately
  before EACH attempt, (2) validate the R2 breaking-state probe
  against a known-hit configuration before using it as a raycast
  oracle.  Evidence: `scratch/issue6_round9_psxmc/` (report_place6
  .json + merged, 11 PNGs).

## Tools

`msx_wr9_arena.py`, `msx_wr9_cap.py`, `msx_wr9_cap2.py`,
`msx_wr9_leaderkill.py` (C/YB/J1/GR/MIX arms + walk phase),
`tetrade_r9_tetris.py` (2-ply AI + tetris PNG ring),
`psxmc_r9_place6.py`.  No game bytes committed; patched images and
savestates local-only.  Suite 489+1xfail."""

BODY7 = """**Round 9 (issue #6 50/50 share) — the town-arena pin is now
captured and directly attacked; the camera still holds.**  Commit
`f082179`; full report on issue #6 (round-9 comment).

- New deepest traversal: **px 2212.0** (cap v1, 70,351 frames, 40
  disclosed continues) past the T4 truck pin (~1596); the walk is a
  gauntlet of pins: 1164 (chopper-flyover ambush) / ~1596 (truck) /
  2212 (armored trio).
- **PIN-BASED arena capture** (`msx_wr9_cap2.py`): alive AND px >=
  1400 AND < 10 px window over >= 360 f -> savestate `wr9_arena` at
  px 2212.0; census = THREE 300-HP armored ground enemies (st
  0xA0D0, slots 10-12) — same armored-HP class as the choppers.
- The issue's web strategy tested LIVE at last (`msx_wr9_leaderkill
  .py`): **arm YB** (sustained aimed UP+FIRE) killed the trio (8
  kills, +500 each, SQUADRON_FELL x4) — **camera HELD 0/4**; the
  proven **arm J1** (hop+UP-lob, 3-connect recipe) killed faster —
  **camera HELD 0/4**.  The 300 s timer + respawn waves kill the
  player before resolution either way; slot 12 (spawns behind the
  player) was never reachable.
- Verdict: **armored-kill CAUSAL / CAMERA-HELD — decisive negative
  for "the squadron falls with its red leader" at this pin.**  The
  >= 50-wagon acceptance stays blocked at the gauntlet; next levers:
  (a) treat the walk as a continues-ladder and push max_px further
  with the pin-capture running every time, (b) probe whether the
  gate is TIMER-gated (kill trio + survive to timer rollover),
  (c) checkpoint-map the respawns so continues land ahead of the
  pin.  2,473 wagon-sensor spawn events recorded across the three
  runs (labeled attempts deferred until the yard is reachable)."""

BODY5 = """**Session 12 (round 9) — M1-side: the town gauntlet's third pin
(2212) captured and its 300-HP armored trio killed with two
independent input recipes; the camera holds.**  Cross-ref: issue #7
comment + issue #6 round-9 report, commit `f082179`.  Mission-2
front unchanged this round (the m2_train anchor + gate mechanism
map from session 11 stand); the M1 town work feeds the WAGON RUN
issue and maps the checkpoint/timer structure that any deep
traversal must survive."""

s, d = req(f"/repos/{REPO}/issues/6/comments", method="POST",
           payload={"body": BODY6})
print("issue6:", s, d.get("html_url", d)[:120])
s, d = req(f"/repos/{REPO}/issues/7/comments", method="POST",
           payload={"body": BODY7})
print("issue7:", s, d.get("html_url", d)[:120])
s, d = req(f"/repos/{REPO}/issues/5/comments", method="POST",
           payload={"body": BODY5})
print("issue5:", s, d.get("html_url", d)[:120])
