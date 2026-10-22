# Tetrade Playthrough — How the Game Was Learned and How It Runs

**Deliverable:** the FIRST complete game loop played end-to-end by the
PS1Play shared-core + plugin architecture: boot → title → menu → Marathon
→ real gameplay with verified telemetry → natural game over → refuse
CONTINUE → back at the menu. Game: **Tetrade** (MIT homebrew by Logan
Campbell, 3.2 MB disc image, license-patched locally — never committed).

All numbers below come from measured artifacts (trace JSONL, RAM reads,
screenshots). Reproduction commands are at the end.

---

## 1. How the game was learned

The learning was a five-step loop; every step left a reproducible
artifact (`scripts/tetrade_calib.py`, `emu/games_homebrew/evidence/`).

### Step 1 — Source-first rules (static knowledge)
Tetrade is MIT-licensed, so the fastest honest way to learn the RULES was
to read `main.c` from the author's repo (Logan-Campbell/Tetrade) and then
**verify every claim live** before trusting it:
- controls: LEFT/RIGHT move one cell per frame held; A (PAD_CIRCLE)
  rotates CW; B (PAD_CROSS) rotates CCW; UP hard-drops (+2/cell); DOWN
  soft-drops (+1/cell); SQUARE/L1/R1 hold; START pauses.
  **Menu confirm is `CROSS || START`** — this single source line
  explains the earlier sessions' failure: libretro "X" maps to
  TRIANGLE on the PSX pad, which does nothing in the menu. The fixed
  boot chain presses B (= CROSS).
- scoring: single 200×level, double 500×level, triple 700×level,
  Tetrade 1000×level; **level starts at 0**, so early clears score 0
  points — verified live (lines went up, score did not).
- game over: when a new piece cannot spawn → `isGameOver=1`; a
  destruction sweep runs ~120 frames, then "CONTINUE?" offers
  START = continue (resets the board) or **CIRCLE = refuse → title**.
- STRUCT LAYOUT (the key to zero-token perception):
  `matrix int[20][10]` at struct offset 0 (800 B), then `Tetrimino
  tetrimino` (92 B: type, shape[4][4], x, y, wasHeld, rotState, 2 ptrs),
  `nextTCount`, `nextTetriminos[14]`, `holdTerimino`, then
  `score/singleLine/doubleLine/tripleLine/tetrade/.../level/isGameOver`.

### Step 2 — Live boot calibration (procedural knowledge)
The calibrated input chain, each stage with a saved frame:
1. 900 frames settle (BIOS/logo) → title
2. hold START 120 f, release 90 f → main menu (`tplay_01_menu.png`)
3. press B 20 f → Marathon countdown → gameplay (`tplay_02_gameplay.png`)
   — this is where the previous session's X/TRIANGLE press failed;
   B (CROSS) enters instantly.
A savestate `m_fresh` is taken right after entry as a reproducibility
anchor; reloading it restores an all-zero board (verified by digest).

### Step 3 — RAM struct localization by INPUT CAUSALITY (no guessing)
The decisive trick: instead of scanning for a pattern, ASK the running
game where its own state lives:
1. snapshot all 2 MB of RAM as u32
2. hold LEFT for 2 frames (the game decrements `tetrimino.x`)
3. diff: exactly one u32 dropped by 1..2 from a value ≤ 10 → **that is
   `tetrimino.x`** (e.g. 0x1FF004, value 3 → 2)
4. the source layout fixes the struct base: `g = x_addr − 868`
5. plausibility gates: score==0, level==0, isGameOver==0, matrix values
   all ≤ 8, tetrimino.type sane
6. **gravity proof**: `tetrimino.y` must rise ~1 cell per 30 frames
   (observed ys: 14→15→16)
Result: **struct base = 0x1FECA0** for this EXE, stable across boots
(static stack allocation in `main()`), with every field offset verified
independently (x moves with input; y falls; rotState increments on A;
next-queue types refresh at spawn; counters verified below).

### Step 4 — Control causality with RAM evidence
| probe | input | RAM evidence |
|---|---|---|
| move | hold LEFT 3 f | tet_x 2 → 1 ✅ |
| rotate | tap A 1 f | shape[4][4] changed, rotState 0 → 1 ✅ |
| hard drop | tap UP 1 f | tet_type changed (piece locked) ✅ |
| scoring | hard drops during play | score +2 per dropped cell (0→8→42→70→…) ✅ cross-checked against the rendered HUD (trace 70 ↔ screenshot "Score 70") |
| checkpoint | load_state | board digest back to 0 ✅ |
Not verified in isolation (honest gaps): RIGHT was blocked by board
geometry at probe time (rotation worked in the same window); soft-drop
scored 0 because the piece was grounded (source: +1 only per actual
cell); hard-drop score is 0 when the drop distance is 0.

### Step 5 — The learning loop at play time
Per 60-frame chunk the plugin re-reads the live state and re-plans from
scratch (stateless, idempotent): board (20×10 from RAM) + shape + x/rot
→ the pure evaluator (`ps1play/agent/tetris_ai.py`) picks the best
(rotation, column) by lines/holes/bumpiness/heights → segments of
per-cell 2-frame taps with explicit releases → next chunk VERIFIES the
effect (x, shape) and corrects. Nothing is trusted across frames; a
failed rotation (SRS kick rejection near walls) falls back to
current-orientation placement after 2 stuck chunks.

---

## 2. How the game runs (the stack)

```
run_tetrade_playthrough.py (runner: budgets, journal, milestones)
  └─ PS1Play (ps1play/api.py — the one-class API)
       ├─ LibretroCore (beetle-psx 0.9.44.1 headless via ctypes)
       │    · OpenBIOS override (beetle_psx_override_bios=openbios, MIT)
       │    · license-patched LOCAL disc image (16 sectors from the
       │      user's own retail disc — the unblocks-homebrew trick
       │      from Issue #6; patched images never committed)
       │    · input = libretro pad sets per frame (B→CROSS, A→CIRCLE,
       │      X→TRIANGLE, Y→SQUARE) — explicit release always
       │    · RAM exposed as a 2 MB numpy view (observe-only)
       ├─ MemoryView (u8/u16/u32 readers, digests, diff regions)
       ├─ StateManager (savestates: m_fresh / run_entry)
       └─ TetradePlayPlugin (contract v1: boot_script / features /
            policy / infer_state — zero core edits, zero RAM writes)
```

Key runtime facts: one beetle boot per process (second in-process boot
returns contaminated state — protected by tests); emulation runs
~4.7× realtime headless (6,480 gameplay frames ≈ 23 s wall).

---

## 3. The run (measured)

| claim | value | evidence |
|---|---|---|
| boot chain via plugin only | title → menu → Marathon, 7 steps, 4.3 s | trace `boot_script_done`; `00_marathon_entry.png` |
| real pieces placed | **40** (target ≥30) | trace `pieces` per chunk |
| line clears (counters) | **11** singles (singleLine 0→11, verified per-increment) | trace clear events list |
| first clear | fc 2070, delta 1 | `milestone_first_clear_fc2070.png` |
| score trajectory | 0 → 218 (hard-drop +2/cell, HUD-cross-checked) | trace chunks; summary |
| level up | level 1 reached (8-line goal, source rule) | trace `level` |
| natural game over | fc 7890 after wrap-up tower | `milestone_gameover_anim.png` |
| loop closed | CONTINUE refused with CIRCLE → menu again | `99_title_after_run.png` |
| determinism | two full runs bit-identical (same fcs/scores) | tplay_20261022_104326 vs _104838 |
| suite | 334 passed + 1 xfailed (13 new offline tests) | `tests/test_tetrade_play.py` |

**Honest open items:**
1. `score` shows deterministic downward steps at some clear boundaries
   (e.g. 232→2 at fc 3444, lines preserved). The master-branch source
   has no score decrease; the release binary may differ from master
   (version skew). Score is VERIFIED for hard-drop accumulation and
   HUD agreement; the clear-time behavior is marked UNKNOWN (W3-6).
2. Mid-lock transient reads (type/x = -1) are gated (policy idles one
   chunk) — one garbage-plan chunk observed pre-gate, fixed and covered
   by a unit test.
3. The runner additionally guards every UP segment: drops are skipped
   in the type==-1 gap (race could corrupt score/board).

---

## 4. Reproduce

```bash
cd /home/z/my-project/ps1ai
python3 scripts/tetrade_calib.py                                   # learn
python3 scripts/run_tetrade_playthrough.py \
    --target-lines 6 --target-pieces 30 --max-frames 400000        # play
python3 -m pytest tests/test_tetrade_play.py -q                    # verify
```

Artifacts stay under `emu/games_homebrew/evidence/` (local-only,
gitignored). Only the plugin, the pure engine, the runner, tests and
this document are committed.
