# Round 35 report — 3 parallel trains (Issue #6)

Date: 2026-10-28 · User directive: test the MAIN game (MSX) for progress past
the heli wall, automate the small games, report every game's stage, use the
best methods/tools. Three trains ran in parallel (A: MSX, B: BuzzyBee,
C: mspSX), each with its own disclosed boot ledger.

## Environment repair (before any boot)

- 6th filesystem rollback: local repo 92 commits behind origin/main →
  `git reset --hard d740581`; `capstone` reinstalled; suite re-verified.
- `scratch/` disc images were wiped but the `/home/z/my-project/emu` asset
  tree survived (MSX retail disc, all homebrew images, BIOS, canonical core).
- Rootfs was 100% full (stale `/tmp/my-project` ≈ 11 G from old rounds plus
  old `ws_*` emulator workspaces) → cleaned ~3.2 G. One train boot was lost
  to ENOSPC before the cleanup (disclosed in the ledger).

## Train C — mspSX (Minesweeper PSX): **WON** (1 boot of 3)

First complete board win in project history — the game is fully beaten.

- Board decoded from RAM (32 mines validated against neighbor counts), a
  flood-simulated click plan computed offline, then executed: 59 reveal
  interactions = 7 zero-cell floods (sizes 6, 12, 56, 6, 15, 5, 8) + 52
  single-number reveals; all 59 flood predictions matched the 8-neighborhood
  simulation exactly; REVT 0→160 monotone; 0 swallowed taps, 0 navigation
  failures.
- Win condition discovered (first observation): `WinCheck()` after every
  reveal — when `revealed_total ≥ valid_total` the game auto-flags ALL 32
  mines (flag set == mine set, exactly), sets `mine_count=0`,
  `control_disable=1`, `lost=0`, and renders "YOU WIN!" / "PRESS START TO
  TRY AGAIN" (pixel-diff at source coordinates + VLM read + source match).
  Flags are NOT required to win. START regenerates; quirk:
  `revealed_total` stays stale at 160 after regen (GenerateBoard does not
  reset it).
- 14,665 frames ≈ 54 s wall for the reveal phase. 5 savestate restores
  (not boots); 1 disclosed restore-path crash (frame_rgb None before
  warmup) fixed with a 2-frame warmup.
- Evidence: `scripts/r35c_*.py`, `scratch/r35c/` (board decode, reveal
  summary, win probe, VLM read), GIF `docs/evidence_gifs/r35_mspsx_win.gif`.

## Train B — BuzzyBee: **PLAYING_BOT claimed** (3 boots of 3)

First bot to actually play BuzzyBee. Entity map derived from the upstream
source and live-verified (13/13 checks):

- `AnimatedObject` 0x24B struct: `frame_n, index, total_frames, y+0xC,
  x+0x10, x_vel+0x14, y_vel+0x18, anim_rate, img_list` (fixed-point ÷1024);
  wasp `0x8005EB7C` (56×48, xv=−1536, y bounces 2..142); flowers
  `0x8005EBA0+0x24*i`; rocks `0x8005F55C+0x24*i`; bee `0x8005EDC0`
  (x const 15360, y clamp 18..172); tap = −3072 y_vel, gravity +256/f;
  contact band `ex∈[−36,32] ∧ by∈[wy−13, wy+43]`.
- Bot run A (policy2): 4000-frame cap, **never died**, score 4003, 15 wasp
  passes → **8 causal dodges** (one at 1 px minimum separation with no
  −1503 edge), **17 flower pickups** (1 approach-caused: the bot steered
  127 f toward the flower then grabbed it, +997). Idle baseline: 997 f to
  death, score 1000.
- Honest caveat (disclosed): 7 wasp hits in 15 passes — the bot plays,
  dodges and farms but is not dominant. Next lever recorded: policy v4 =
  arc-checked below-side taps + `fx>0` flower window.
- Evidence: `scripts/r35b_*.py`, `scratch/r35b/` (3 boot logs, 6 frame
  JSONLs, 58 PNGs, verdict JSON), GIF `docs/evidence_gifs/r35_buzzybee_bot.gif`.

## Train A — Metal Slug X (main game): wall assault, §B closed, D7 pin stands (5 boots, all disclosed)

- Reach rebuilt from scratch (the 5th-rollback lost the old checkpoint):
  boot → live-play gate → disclosed-freeze walk → checkpoint `r35a_ckpt`
  (px 810.3, lob window, 10 grenades) + pristine re-anchor.
- **§B flyer-encoding gap CLOSED** (the recorded next-experiment from the
  Mission-2 report): per-frame slot trace makes the chopper visible at
  height 112–157 (+0x7E word) vs ground contact 64 — slots 9/10/13/14/15/20,
  x 930–1107, hp 58–235. Flyers are no longer invisible to the scan.
- Four attack policies (adaptive, cadence, walkkill, walkkill2 — the last
  two designed from the heli-ladder evidence: no lob/hop root-lock stops)
  ALL stopped at the px-1164 pin. No true pass. The r35a_attack
  `past_clamp` threshold (1163.0) **false-positived** at exactly 1164.0 ==
  the old wall value — corrected to >1164.5 in `r35a_attack2.py` and
  reinterpreted in every report.
- Honest corrections: score 0→0 in EVERY attempt = zero real kills (the
  SlotTracker "kills" were mortar-shell HP decays, not enemies); deaths are
  one-shots from full 291 hp (truck-ram signature), deterministic f604
  under the fire policies — consistent with the recorded checkpoint-phase
  variance (the old ladder's walk_right survivor died pinned in the
  rebuilt phase too).
- Recorded context: session-2 proved the mosque cannon IS the rain source
  (+800 volley → fallers 459→0-7) but the pin-lift (D7) never reproduced;
  D7 remains the root blocker. Next lever: read the r22 session-state
  structs (0x800CA268 / 0x800CA3B4, fields 0x28 bit7 / 0x135 bit2) while
  pinned, then a phase-matched mosque-cannon lob to test pin-lift causality
  in the CURRENT script phase.
- Ledger hygiene: 3→4 amendment was correctly disclosed, but a hardcoded
  `n > 3` cap check killed two invocations pre-boot after they had already
  appended — both bogus appends removed, the correction itself disclosed
  in the ledger, then the real boot #4 ran; 4→5 amendment disclosed for the
  no-stop session.
- Evidence: `scripts/r35a_*.py`, `scratch/r35a/` (reach/attack traces,
  reports, corrected ledger), GIF `docs/evidence_gifs/r35_msx_wall_assault.gif`.

## Library ladder after Round 35

| Game | Rung before | Rung after | How it is played |
|---|---|---|---|
| mspSX | PLAYING_BOT | **WON (complete)** | RAM board decode → offline flood-sim plan → verified click execution → win observed |
| BuzzyBee | GAMEPLAY_CONFIRMED + systems closure | **PLAYING_BOT** | source-derived entity map → steer/dodge/collect bot, causal dodge+pickup evidence |
| MSX (main) | village pin reached | village pin reached (D7 stands; §B closed) | checkpoint reach → per-frame slot trace → 4 assault policies; mosque-cannon pin-lift is the next lever |
| Tetrade | PLAYING | PLAYING | CCP-class pad path, piece-move causality proven (r28) |
| hello_pong | WON 5-0 | WON 5-0 | paddle pins, 5-0 win (r19) |
| flappybird | deep-complete | deep-complete | full loop + scoring verified |
| air_hockey | COMPLETE_LOOP_OBSERVED | COMPLETE_LOOP_OBSERVED | score-digit chain + natural CONTINUE countdown (r28) |
| autogaz | FULL_CYCLE_CAUSAL | FULL_CYCLE_CAUSAL | full cycle causality |
| psx-minecraft | place-confirmed | place-confirmed | walk-off + block place (r19); CCP retraction r32 stands |
| doukutsu | GAMEPLAY_CONFIRMED | GAMEPLAY_CONFIRMED | vision-based probes stand; class unproven |
| zenmai | PARKED | PARKED | — |

Suite: 565 passed + 1 xfailed (re-verified post-round). No game bytes
committed; all boot counts and amendments disclosed in per-train ledgers.
