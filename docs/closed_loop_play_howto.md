# How the agent actually PLAYS (closed-loop recipe) — hello_pong as the worked example

This document answers "how is playing saved in the plugin" and is the recipe
every per-game player agent follows. Nothing here is magic: the play loop is
**classical perception → decision → legal input**, rebuilt per game on top of
the shared `ps1play` framework.

## 1. The three layers

### Layer A — framework (in `ps1play/`, shared by every game)
- **Boot headless**: `harness.py` + `api.py` load the Beetle PSX libretro core
  through a pure-Python ctypes frontend — no GPU, no window, ~110-400 fps
  software rendering. The game boots from a (local, license-patched) cue/bin.
- **Perception surfaces** (all live, per frame):
  - **Pad injection**: legal button presses only (the same 14 buttons a real
    DualShock has). `ps1play/core/inputmap.py` maps names → bitmasks.
  - **RAM view**: the live 2 MB main RAM as a numpy array — read-only during
    real play.
  - **Frames**: RGBA screenshots for evidence (humans/GIFs), and — for
    vision-only agents like Poy Poy r18 — pixel analysis.
  - **Savestates**: used for calibration/checkpoints (read-only anchors), never
    to skip during a real run.
- **Agent engine** (`ps1play/agent/`): `memscan.py` (find counters), `events.py`
  (event-verified anchors), `policy.py` + `loop.py` (the tick loop),
  `worldmodel.py` (slot discovery), `rewards.py` (progress signals).

### Layer B — the per-game player agent (e.g. `scripts/r19t4_hellopong_win.py`)
A small, deterministic, **zero-LLM-token** loop. For hello_pong:

```
every frame tick:
  1. PERCEIVE   ball (cx, cy) + left-paddle x  ← RAM paddle struct (y @0x1FFEB0)
                + score word @0x1FFEB4 (both sides)
  2. DECIDE     proportional control: move paddle toward predicted ball
                intersection (sign of last_vx, kept across vx==0 frames —
                the r19 attribution bug)
  3. ACT        press UP/DOWN taps only (legal pad input)
  4. VERIFY     after every point: RAM left_delta == +1 AND PNG of the score
                band changed AND rally was physically load-bearing
                (agent touches counted by frame-trace)
  5. LOOP       until score == 5 (the game's own win condition) → GAME OVER
                screen detected → "PRESS X TO PLAY AGAIN" restart proven by
                playing one more real point in a fresh 0-0 game
```

Verdict **WON** is only issued when the win state was reached *through this
loop in the same session* — with per-point causal anchors (RAM delta + PNG +
event log). RUNNING (boots, inputs register) and PLAYING (loop closes but no
win yet) are reported honestly separately.

### Layer C — evidence (what gets committed vs. stays local)
- Committed: agent scripts, `report.json`/`evidence.md` summaries, mirrored
  GIFs in `docs/evidence_gifs/`, manifest status lines, issue reports.
- Never committed: game discs/bytes (license-patched images stay in the local
  `emu/` workspace), full frame dumps (deleted after GIF creation).

## 2. The generic recipe (how a NEW game gets this treatment)

1. **Boot ladder** — boot → title → menu, each transition verified by a
   measured signature (RAM bytes or frame diff), never assumed.
2. **Calibration** — determinism check (ambient diff = 0), then per-button
   probes: press → whole-RAM diff → what moved? (r18 Poy Poy: B=grab,
   A≡X; hello_pong: UP/DOWN move paddle y by ±8.)
3. **Sensor pinning** — find the few counters that matter (score, position,
   state word) by RAM diffing across known events.
4. **Policy** — the simplest loop that moves a game metric in the right
   direction (proportional control, greedy targeting, or a placement
   heuristic — Tetrade r19: height/holes/bumpiness, 99.86% landing accuracy).
5. **Closed-loop run** — perceive→decide→act→verify every tick; log per-tick.
6. **Win-state proof** — play until the game's OWN win condition; record the
   exact frame, RAM deltas, PNGs; then re-enter from the game's own
   restart flow to prove the loop is repeatable.
7. **Honest verdict** — RUNNING / PLAYING / WON (+ what is still missing).

## 3. Scoreboard of games played this way (live)

| game | verdict | proof headline |
|---|---|---|
| hello_pong | **WON 5-0** (r19) | per-point RAM left_delta=1, play-again proven |
| Poy Poy (retail) | **WON round** (r19) | charged throw → opponent RETIRE! f1208 |
| Tetrade | **PLAYING** (r19) | 230 clears, 99.86% landing accuracy, 20 continue-refusals |
| FlappyBird PSX | **WINNING** (r15) | 10 pipes past the game's own win gate |
| PSX-Minecraft | CONFIRMED visible place (r19) | stack 10→9, world_px 1,269, persist-60f |
| psxBreakout | WON (pre-r16) | first closed-loop win: ball track, bricks clear |

Framework: `ps1play` · Player agents: `scripts/` (one file per game) ·
Full round reports: `docs/issue6_r*_report.md` and issue #6 on GitHub.
