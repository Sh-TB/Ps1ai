#!/usr/bin/env python3
"""post_issue7.py — Issue #6 round-7 report + Issue #5 session-10 note."""
import sys

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY6 = """**Round 7 (50/50) — Tetrade line-clear causality CLOSED (3rd complete
played game with counter-level causality), PSXMC place campaign honest
INCONCLUSIVE with the failure root-caused, MSX M1->M2 gate decisive
negatives, playloop.py generalized.** Commit `a0d07d0`, suite **485
passed + 1 xfailed**.

## Tetrade — GAMEPLAY_CONFIRMED + CAUSAL(lines), through the tool

Source-first (upstream `src/main.c` v1.0: board 10x20, struct offsets,
`BASE_DROP_RATE 30`, A=CIRCLE rot CW / B=CROSS rot CCW / UP=hard-drop,
`check_lines` adds `200/500/700/1000 * level` — **0 at level 0**), then
a one-boot calibration ladder: LEFT-tap whole-RAM u32 diff → **exactly
one hit** → live base `0x1FECA0`: matrix 20x10 @+0, type `0x1FEFC0`, x
`0x1FF004`, y `0x1FF008`, score `0x1FF584`, single `0x1FF588`, level
`0x1FF5A0`, over `0x1FF5A8` (savestate anchors; soft-drop 1f-tap delta
0 = honest negative, reproduces the Issue-8 record).

Main run through the generalized playloop tool: **39 pieces, 8 LINE
CLEARS** — cycle 1: singles 0→1→2 then a TRIPLE (lines 0→1→2→5) →
natural game over (score 532) → CONTINUE? refused with CIRCLE →
counters verified reset → cycle 2: 3 more singles → natural game over
(474).  Score stays drop-driven (+2/cell) exactly as the source
predicts at level 0.  Evidence: `scratch/issue6_round7_tetrade/`.

## PSX-Minecraft — PLACE campaign: INCONCLUSIVE(place), root-caused

- First battery honest-negative with a quantified diagnosis: the look
  ladder held 14-56 f = **2-12 deg below the horizon** (90 deg ≈ 228 f
  at the measured 18432 raw/f) — the crosshair never touched terrain;
  even R2 dig went non-persistent in that state; the fine-aim loop
  residuals were ±100-175 deg (asymmetric look rates).
- The pitch-sweep follow-up's giant full-screen diffs were identified
  by the sharper place4 iteration as the **CRAFTING UI overlay**: the
  game ticks ≥2x per frame — tick1 USE acts, tick2 raycasts the
  just-placed table and opens its modal (`block_crafting_table.c:232`);
  place3's later "placements" are RETRACTED as UI artifacts.
- place4 (fine aim err <1 deg, geo gates, UI-recovery): USE taps
  consume the selected stack with ItemID-context verification — chain
  **26→25→24→23 @0x7cda0 (CRAFTING_TABLE)** — but **zero visible
  world placements** (world_px 0 in every attempt).  Attempt 3's
  raycast then HIT a placed table (UI opened, ui_px 36852) — evidence
  the earlier USEs DID modify the world, just out of frame.
- Savestate round-trip on the edited world: RAM bit-exact + frame
  bit-exact at t+1 + functional re-edit accepted on the restored world.
- Verdict: **INCONCLUSIVE(place)** — stack-consumption CAUSAL, visible
  placement unproven.  Next lever: camera framing the target face +
  post-place world_px gate.  Evidence: `scratch/issue6_round7_psxmc/`.

## MSX (issue #5) — the M1→M2 gate: decisive negatives

From the post-banner CONTINUE? gate: a **41-offset tap-timing sweep**
(24f steps, savestate-restored frame-exact retries,
`msx_m2_gate_sweep.py`) landed in the input-live M1 endzone **41/41**
(gs1); a **5400f quiet watch** self-resolved into the attract demo
(gs2).  With m2t8/rg1-rg4 that is **8 documented attempts, zero M2
spawns** — the session-6 "one START accepts into M2" record does not
reproduce from this gate instance and is corrected to
"path-sensitive, mechanism unknown".  The rg1-vs-session-9 number
discrepancy was diagnosed and closed (different missions/rides/
policies — `discrepancy_rg1_vs_session9.md`).  Offline mining of the
rg1 attract-ladder tracker (1.03M changed bytes,
`msx_m2_candidates.py`) → the top candidate families decode as the
16-byte-stride entity pool (self-referential pointers), not flags.
Recorded next lever: the surgical M1-end vs M2-side loading diff —
requires the m2_train anchor.

## Tools

`scripts/playloop.py` generalized: `--policy/--cue/--workspace`,
GAME_DEFAULTS + POLICIES registry {pong, tetrade}, verdict_flags hook
(`--game pong` default unchanged) + 3 new tests.

No game bytes committed; all patched images local-only; suite
485+1xfail."""

BODY5 = """**Session 10 (round 7, the 50% main-game share) — the M1→M2 gate
gets decisive negatives.** Cross-ref: full report on issue #6 (round-7
comment), commit `a0d07d0`.

- The workspace reset had wiped the `m2_train` anchor; 8 documented
  regeneration attempts (m2t8, rg1-rg4, gs1-gs2) produced **zero M2
  spawns**.
- From the post-banner CONTINUE? gate: a **41-offset tap-timing sweep**
  (24f steps, savestate-restored frame-exact retries) → the input-live
  M1 endzone **41/41**; a **5400f quiet watch** → the attract demo.
  The session-6 "one START accepts into M2" record does NOT reproduce
  from this gate instance — corrected to "path-sensitive, mechanism
  unknown".
- The rg1-vs-session-9 ride-number discrepancy is closed: different
  missions (M1-end endzone vs M2 train), different ride policies —
  see `scratch/issue6_round7_msx/discrepancy_rg1_vs_session9.md`.
- Offline attract-flag mining (`msx_m2_candidates.py`) of the rg1
  tracker (1.03M changed bytes): top families = the 16-byte-stride
  entity pool (self-referential pointers), not flags — dead end
  documented in `candidates.json`.
- **Next lever (recorded): the surgical M1-end vs M2-side loading diff
  — requires the m2_train anchor.**  The gate instrument
  (`msx_m2_gate_sweep.py`: quiet arm + frame-exact offset sweep) is
  persisted and ready for the next round.

Evidence: `scratch/issue6_round7_msx/` (reports gs1/gs2/rg2-rg4,
candidate tables, PNGs)."""

s, d = req(f"/repos/{REPO}/issues/6/comments", method="POST",
           payload={"body": BODY6})
print("issue 6:", s, d.get("html_url", d))
s, d = req(f"/repos/{REPO}/issues/5/comments", method="POST",
           payload={"body": BODY5})
print("issue 5:", s, d.get("html_url", d))
