#!/usr/bin/env python3
"""post_issue8.py — Issue #6 round-8 report + Issue #5 session-11 note."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY6 = """**Round 8 (50/50) — MSX `m2_train` anchor REGENERATED + the recorded
M1-end vs M2-side loading diff executed (mechanism map + decisive
latch negative), Tetrade TRIPLE CAUSAL (level/speed/score — 4th
complete played game with counter-level causality), PSXMC place5
honest INCONCLUSIVE with two convention discoveries.** Commit
`772f4fc`, suite **489 passed + 1 xfailed**.

## MSX (issue #5) — session 11: the anchor is back, the gate gets a mechanism map

- **`m2_train` anchor REGENERATED** (attempt 9, `msx_m2_anchor9.py`):
  fresh boot -> M1 banner (chunk 107, deaths 0) -> post-banner
  gameplay_seen -> **2 M2 spawns** -> anchor saved at **px 76.4 /
  score 0 / php 76 / gren 10 / sec (11,9)** — the session-9 spawn
  numbers reproduce exactly.  56,099 frames, one boot.  The same run
  also saved an **`m1_end` anchor** (px 0.0, score 3300, sec (11,1) —
  the CONTINUE? gate).
- **The recorded lever (M1-end vs M2-side loading diff) executed**
  (`msx_m1end_m2side_diff.py`): per-byte RAM tracking over 5 windows —
  A `m2_train` live (restore + ride **+505.6 px**, input-aliveness
  proof), B `m1_end` quiet 4800f, C `m1_end` signature-gated START
  taps (endzone trap again, no spawn), D M1 live, E `m1_end` 7200f
  quiet watch -> attract world.  Diff-of-diffs
  (`msx_m1end_m2side_analyze.py`, + 4 unit tests): spawn_exclusive
  411 B / world_exclusive 3,982 B / ladder_exclusive 766,662 B /
  discriminator 3,381 B; the **gren 10->20 write at M2 spawn-in
  (f30)** reproduces the session-7 record.
- **Mechanism map**: `0x0EB5FC` is a **WORLD-ALIVE latch** — 0xFF in
  every live mission world (M1 *and* M2), 0x00 within the 30f
  post-restore re-init burst in every `m1_end` window, staying 0 while
  the ladder dies into attract.  `FLAGS_WORD 0x0EE518` dies to 0 at
  ~f2400 in every restored ladder (mission given up); E's ~f5820
  attract score write (3300->700) confirms the attract-demo terminus.
- **Decisive negative probe** (`msx_r8_latch_probe.py`, DISCLOSED
  GS-code constant holds): from `m1_end` restore, holding
  `0x0EB5FC=0xFFFF` (whole-window and late arms) — and holding it
  together with **SECTION_FLAGS=0x0009** — does **NOT** reopen the
  gate: all arms replay the identical ladder into attract (fw->0,
  score stays 3300, no spawn).  The gate's missing state is NOT
  (world-alive latch, section-flags) in tracked main RAM.  With
  m2t8/rg1-4/gs1-2 that is now **12 documented non-spawning contexts
  vs 2/10 fresh-boot successes** — the differentiator lies outside
  tracked main RAM (restore-path or CD-pipeline state).  Gate stays
  OPEN; the instrument bank (5-window tracker + analyzer + probe)
  persists for the next round.

## Tetrade — CAUSAL(level) + CAUSAL(speed) + CAUSAL(score)

Source pinned upstream `main.c` v1.0 @`5155664` (**LEVEL_GOAL 8**,
drop rates 30/27/13, clear table 200/500/700/1000 x level, hard-drop
2/cell).  Main run (`tetrade_r8_levelup.py`): **6 cycles, 368 pieces,
122 LINE CLEARS**, natural game over every cycle, CONTINUE refused —
zero RAM writes to game state.
- **CAUSAL(level)**: `0x1FF5A0` flips 0->1 at fc 4293 with lines
  **8->9 = LEVEL_GOAL exactly**.
- **CAUSAL(speed)**: drop cadence medians **30f (n=374, all=30,
  phase-locked mod 30) -> 27f (n=248, all=27) -> 13f at level 2
  (n=69)** — the source table verbatim.  (A first-pass MISMATCH
  verdict was refixed: phase concentration is per (cycle, level)
  bucket — gameTimer restarts each life.)
- **CAUSAL(score)**: **40/40** level-0 clears add zero clear points
  (0 x level) and **61/61** level>=1 clears match the 200/500/700/
  1000 table x level exactly.
- Independent HUD corroboration via VLM screenshot reads (score 674
  matches RAM at the flip; level 1 visible next cycle).
- Verdict: **GAMEPLAY_CONFIRMED + CAUSAL(level, speed, score)**.

## PSX-Minecraft — place5: INCONCLUSIVE(place), two discoveries

Pitch ladder 15.5-25 deg (DIRECT convention: ring+ = camera DOWN,
matching the raycast), fine-aim err <= 1 deg, control arm clean — and
every attempt: stack 26->26 (delta 0), ui_opened, world_px 35-40k,
raycast hits: [].  New source discoveries:
1. **The raycast and the renderer disagree on pitch sign**
   (`world_raycast.c` rotationToDirection5o Y = -sin5o(pitch) vs
   `camera.c:83` +sin(pitch)) — aim conventions must be chosen per
   consumer, not globally.
2. **The UI-close binding is START**
   (`block_crafting_table.c:200` BINDING_OPEN_INVENTORY ->
   RELINQUISH); **CIRCLE is BINDING_LOOK_RIGHT** — round-7's
   "close with CIRCLE" recovery was rotating the camera.
Reach 6 (`player.h:27`), place at hit+face (`player.c:321`).  The
delta-0 + UI-opened pattern says the USE raycast hits nothing
placeable at these pitches; next lever: **ray-directed** aim with the
target face in frame, then the world_px gate.

## Tools

`msx_m1end_m2side_diff.py` (5-window one-boot per-byte tracker),
`msx_m1end_m2side_analyze.py` (+ `tests/test_msx_r8_analyze.py`),
`msx_m2_anchor9.py`, `msx_m2_candidates8.py`,
`msx_r8_globals_query.py`, `msx_r8_latch_probe.py`,
`psxmc_r8_place5.py`, `tetrade_r8_levelup.py`.

No game bytes committed; all patched images and evidence local-only
(`scratch/issue6_round8_{msx,psxmc,tetrade}/`).  Suite 489+1xfail."""

BODY5 = """**Session 11 (round 8, the 50% main-game share) — the `m2_train`
anchor is back and the M1->M2 gate gets its mechanism map.**
Cross-ref: full report on issue #6 (round-8 comment), commit `772f4fc`.

- Anchor regenerated at attempt 9 (`m2t9`): fresh boot -> M1 banner ->
  post-banner gameplay -> **2 M2 spawns** -> `m2_train` saved (px 76.4,
  score 0, gren 10, sec (11,9) — session-9 numbers exact) + `m1_end`
  saved in the same run.
- The session-10 recorded lever (M1-end vs M2-side loading diff) ran
  as 5 per-byte RAM windows: mechanism map = `0x0EB5FC` world-alive
  latch (0xFF live / 0x00 attract-resolved), `FLAGS_WORD` death at
  ~f2400, attract score write ~f5820; gren 10->20 spawn-in write
  reproduced; spawn_exclusive 411 B / discriminator 3,381 B ranked.
- Decisive negative (disclosed GS holds): latch (+SECTION_FLAGS=9)
  holding does NOT reopen the gate — **12 documented no-spawn contexts
  vs 2/10 fresh-boot successes; the missing state is outside tracked
  main RAM** (restore-path or CD-pipeline state).  Next levers: the
  CD-loading pipeline state at the countdown->loading seam, or an
  anchor regen run instrumented DURING the natural ladder (the only
  path that spawns).
- Instruments persisted: `msx_m1end_m2side_diff.py`,
  `msx_m1end_m2side_analyze.py` (+tests), `msx_r8_latch_probe.py`,
  `msx_m2_anchor9.py`.  Evidence: `scratch/issue6_round8_msx/`."""

s, d = req(f"/repos/{REPO}/issues/6/comments", method="POST",
           payload={"body": BODY6})
print("issue6:", s, d.get("html_url", d)[:120])
s, d = req(f"/repos/{REPO}/issues/5/comments", method="POST",
           payload={"body": BODY5})
print("issue5:", s, d.get("html_url", d)[:120])
