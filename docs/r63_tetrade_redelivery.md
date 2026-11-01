# R63 — Tetrade Full-Loop Re-Delivery (Issue #8)

Round: R63 · Date: 2026-11-01 · Base: `c34c6f2` (R62 wave) · Game:
**Tetrade v1.0** (MIT, Logan Campbell) · Issue: #8

## Why

Issue #8's DoD was met on 2026-10-26 (round 10: 41 clears, natural game
over, plugin loop), but the round-10 artifacts
(`tetrade_r10_plugin_loop.py`, `docs/tetrade_playthrough.md`,
`msx_r11_wagons.py`) were lost to the v0.5/v0.6 repo rewrites and the
sandbox rollbacks — none exists in the current tree. R63 re-delivers
the complete loop as FRESH, committed evidence on the current stack.

## What ran (one boot, `scripts/r63_tetrade_full_loop.py`)

boot → title → START → menu → CROSS on ">Marathon Mode<" → START tap →
180 f countdown → struct located by signature → **Dellacherie 2-ply
policy** (board + current piece + NEXT piece read from RAM; reads only)
→ natural game over (spawn overlap) → CONTINUE refused with CIRCLE →
restart → fresh Marathon verified.

## Anchor map (derived from the MIT source, verified live)

`TetradeGame` on the stack, base **`0x1FECA0`** this boot (matches the
round-10 prior: isGameOver `0x1FF5A8` = base+2312): matrix[20][10]
int @+0 (values = piece type 1..7, 0 empty), tetrimino{type@+800,
shape@+804, x@+868, y@+872, wasHeld@+876, rotState@+880},
nextTCount@+892, nextTetriminos[14].type@+896+92k (the round-10
"struct+896" prior = nextTetriminos[0].type), hold.type@+2184,
score@+2276, single@+2280, double@+2284, triple@+2288, tetrade@+2292,
level@+2304, isGameOver@+2312, isGamePaused@+2316. Live verification:
every field read sane; all 28 pieces' NEXT-promotion cross-checks
passed (28/28, vs 150/152 in round 10).

## Result (VERIFIED, `data/r63/tetrade_full_loop_summary.json`)

| DoD item | result |
| --- | --- |
| 1. Marathon via real pad input, no writes/cheats | PASS — 28 pieces steered with LEFT/RIGHT/CIRCLE taps + UP hard-drop; zero memory writes |
| 2. Real Tetris: reads the stack, steers, ≥1 verified clear | PASS — **1 line clear** (`single` 0→1); cause chain exact: score +0 at level 0 (`SINGLE_LINE_SCORE * level` = 0, matching the source), counter incremented, board row removed |
| 3. Natural game over + return to fresh menu | PASS — stack overflow, `isGameOver` 0→1, CONTINUE refused with CIRCLE, restart, counters zeroed, board empty |
| 4. Zero core edits | PASS — `ps1play/` untouched; the runner is a script over the existing API |

Final: 28 pieces, score 460 (hard-drop points only, level 0),
single 1 / double 0 / triple 0 / tetrade 0, level 0, game over reached
naturally. Per-piece trace: `data/r63/tetrade_full_loop_trace.jsonl`.

## Boot ledger (7 boots, all this session, all disclosed)

probe1 ×4 (3 entry-variant failures — the PRESS-START/PAUSED
key-repeat trap and the slow-gravity churn detector — then 1 success),
diag ×1 (the struct-scan diagnosis: the first scan's window cut excluded
the stack region; the second filter missed the transient `type = -1`
respawn state), full_loop ×2 (1 BLOCKED_NO_STRUCT before the fix,
1 success). Evidence PNGs stay local (`scratch/r63_tetrade/`) per the
repo hygiene rule; the JSONL trace + summary are committed.

## Honest notes

- The policy is a hand-written heuristic (no learning, no training —
  the R53→R62 training closure is untouched; this is a different game).
  It plays legal but weak Tetris (holes accumulate; one clear in 28
  pieces) — the DoD bar is "at least one verified clear", which is met;
  the round-10 policy was stronger and its loss is recorded honestly.
- Perception is RAM-read-based, which Issue #8's documented loop
  sanctions explicitly ("RAM diff-scan hunting for monotonic
  counters"); the visual-only requirement belongs to the #11/#12
  learning missions, not this issue.
- The runner drives the shared core through the existing `PS1Play` API
  with zero core edits; the plugin-contract file
  (`ps1play/plugins/base.py`) is untouched.
