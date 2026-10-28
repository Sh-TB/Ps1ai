# Issue #6 — Round 36 report (2026-10-28): NEW-GAME INTAKE ×2 + full library status matrix

Trains: R36 ran 3 parallel work items per the standing directive —
A) LostPlumber intake (2 boots, cap disclosed), B) VoXide intake (4 boots,
caps amended 2→3→4 before each run, disclosed), C) library status matrix +
this report. Suite re-verified green before commit: **565 passed + 1 xfail**.
Disk repaired first (100% full → −3.2 GB stale workspaces/archives; game
assets kept). No game bytes committed; patched images + boot workspaces stay
in `emu/` (gitignored).

## 1. NEW GAMES ADDED (the user ask: "add 2-3 new loadable games")

### 1a. LostPlumber (NDR008/LostPlumber, MIT-in-header — flagged) — BOOTED + INPUT_RESPONSIVE
- Artifact: repo-tree `LostPlumber.ps-exe` 86,016 B, sha256 re-verified
  `413d315a…bc863f8`; PS-X EXE pc0 0x80010000 t_size 83,968 sp 0x801FFF00.
- Image: `r36t1_lostplumber_wrap.py` → iso9660_min wrap + no-space
  SYSTEM.CNF + LOCAL MSX license sectors (route 2, disclosed;
  `lostplumber_lic.bin` sha256 68b155f5…6b535c9b).
- Boot 1: boot-logo square renders f60 (472x640 core presentation), dark
  side-scroll world renders from ~f520 (240x320, orange brick terrain).
- Boot 2 (input causality): **RIGHT hold 90f → world scrolls left**
  (vis diff 8.38, census 387 bytes @0x80028000 tilemap region; PNG pair
  idle1/cross in shots; GIF mirrored). LEFT/CROSS/START inert — expected:
  the r22 source-read classifies it as "minimal loop (RIGHT scroll only)"
  jam prototype.
- Honest caveat: padbuf signature `41 5A FF FF` NOT found (driver stores
  differently than BuzzyBee) — input causality is proven VISUALLY, not via
  padbuf mirror. Ladder: **INPUT_RESPONSIVE (visual-causal)**.
- Evidence: `scratch/r36/lostplumber/{boot1_log,boot2_log}.json`, shots,
  `docs/evidence_gifs/r36_lostplumber_scroll.gif`.

### 1b. VoXide v0.1.11 (EBonura/voxide, GPL-2.0-or-later; assets CC0 per portal audit) — BOOTED + TITLE_RENDERED, INPUT_UNPROVEN (both cores)
- Artifact: `voxide.bin` 2,511,936 B, sha256 re-verified
  `7a37a390…c4e1e2ac` (zip-inner of the portal release, LICENSE inside).
- Image: `r36t2_voxide_lic.py` → route-2 license patch in place
  (`voxide_lic.bin` sha256 c9a3ef19…758c2bc2).
- Boot 1 (beetle): **title menu fully renders** — "VoXide — NOW WITH 2MB OF
  RAM!", PLAY GAME / NEW WORLD / SETTINGS / CREDITS; ambient rotating-world
  background (vis 19-25/120f).
- Boot 2 (beetle): DOWN/UP/CROSS probes ≈ ambient; CROSS on PLAY GAME does
  NOT enter the game (9×100f post-checks stay on menu).
- Boot 3 (pcsx_rearmed, interpreter — DRC segfaulted on OpenBIOS boot,
  disclosed): title renders there too ("ALSO TRY WIPEOUT!" rotating
  subtitle); menu still inert to DOWN+CROSS.
- Boot 4 (beetle, decisive): 8-button battery (DOWN/UP/CROSS/CIRCLE/START/
  SELECT/TRIANGLE/SQUARE) with menu-region-only diff — all 8 within ambient
  band (3.5-3.9, uniform) → **no causal input signal on either core**.
- Diagnosis (recorded as the transferable finding): PSoXide SDK (Rust) is
  the same **direct-SIO/TX-only class as zenmai/autogaz** — beetle's
  read-arms-receive model never services it (r22 22.3(e) core-source
  proof). Countermeasure lever (already on the r21 plan): standalone
  mednafen or PCSX-Redux backend for the TX-only class. Today's LostPlumber
  run doubles as the same-session CONTROL proving the core+host input path
  itself is healthy.
- Ladder: **BOOTED + TITLE_INTERACTIVE-looking, INPUT_UNPROVEN** (honest).
- Evidence: `scratch/r36/voxide/{boot1_log,boot2_log,boot3_log,boot4_log}.json`,
  `docs/evidence_gifs/r36_voxide_title.gif`.

Third new source identified but not booted (build-gated / heavy): psx-snake
(mfotzler, MIT — needs PSn00bSDK build), Cortex Ignition tech demo (23 MB,
portal release — not "very simple"). Held for the next intake round.

## 2. LIBRARY STATUS MATRIX (the user ask: "which stage is each game at — % + difficulty")

Ladder: BOOTED < INPUT_RESPONSIVE < STATE_CHANGE < GAMEPLAY_CONFIRMED <
PLAYING < WON/COMPLETE. Percent = honest completion of the game's own
verifiable loop (not generic difficulty). Difficulty = automation difficulty
(real-time pressure × state space × input surface), ★=trivial…★★★★★=hardest.

| # | Game | Source/License | Rung (exact) | % | Difficulty |
|---|------|----------------|--------------|---|------------|
| 1 | mspSX (Minesweeper) | AcidGunner/MSPSX, Unlicense | **WON** (r35 full-board win, 59-click flood, YOU WIN! RAM+PNG) | **100%** | ★ (turn-based, deterministic) |
| 2 | hello_pong | marconvcm/ps1_dev, MIT | **WON 5-0** (closed-loop agent, play-again proven) | **100%** | ★ |
| 3 | autogaz | egemenkus0/autogaz, MIT | **FULL_CYCLE_CAUSAL** (its max: 4-screen meme app, no gameplay exists) | **100%** (as designed) | ★ |
| 4 | FlappyBirdPSX | IcePanorama, Unlicense | **deep-complete** (WINNING: 10 RAM-anchored pipe passes) | ~95% | ★★ |
| 5 | Tetrade | Logan-Campbell, MIT | **PLAYING** (bot: 1,816 pieces, 230 clears, 99.86% landing) | ~85% | ★★★ |
| 6 | BuzzyBee | NDR008, MIT | **PLAYING_BOT** (r35: 4,000f never-died, score 4,003, 8 causal dodges, 17 flower pickups) | ~75% | ★★★ |
| 7 | air_hockey (retail) | owner disc | **COMPLETE_LOOP_OBSERVED** (match→end→CONTINUE→new match) | ~70% | ★★★ |
| 8 | Poy Poy (retail) | owner disc | **WON** (r19 charged-throw RETIRE) + real-match closed-loop PLAYING (r18) | ~60% | ★★★ |
| 9 | doukutsu (Cave Story PSX) | fgsfdsfgs, MIT | **GAMEPLAY_CONFIRMED** (r24/25) | ~35% | ★★★★ |
| 10 | Metal Slug X (MAIN, retail) | owner disc | village section: heli-kill recipe **GAMEPLAY_VERIFIED** (3-connect +1100, hp 300→0); **D7 wall pin at px-1164 stands**; mosque-cannon pin-lift = next lever | ~35% of M1 | ★★★★★ |
| 11 | BKBS (one-song rhythm) | hardrockbluesky, MIT | **RUNNING** (pad bits proven; note HITS not proven) | ~40% | ★★★ |
| 12 | PSX-Minecraft | EngineersBox, MIT | **place-confirmed** (STATE_CHANGE + world render + stack 10→9 persist) | ~30% | ★★★★ |
| 13 | **LostPlumber — NEW R36** | NDR008, MIT | **INPUT_RESPONSIVE** (RIGHT-scroll visual causality ×2) | ~20% | ★★ |
| 14 | **VoXide — NEW R36** | EBonura, GPL-2.0+CC0 | **BOOTED, INPUT_UNPROVEN** (2 cores tested; TX-only class) | ~10% | ★★★★ |
| 15 | zenmai (Zork) | msonrm, MIT | **PARKED** (BOOTED_TEXT; direct-SIO TX-only — same class as VoXide) | ~15% | ★★★ |
| 16 | Trap Gunner (retail) | owner disc | booted + menu-walk mapped | ~15% | ★★★ |
| 17 | ballistic (retail) | owner disc | BOOT_THEN_STALL | ~5% | ★★★ |
| 18 | FFT6 (retail) | owner disc | boot-verified | ~5% | ★★★★ |
| 19 | psxBreakout | NDR008, no license | candidate; EXE_LOAD_CRASH (route-4 cliff) | ~5% | ★★ |
| 20 | HMBTN | community toolchain, BYO disc | **BLOCKED_PENDING_DISC** (text tooling 89% byte-exact READY) | ~10% | ★★★★ |

Refused-by-policy: Nortis (no license), every no-license repo (r21/r22
lists). Score-keeping: 3 games at 100% of their verifiable loop (mspSX,
hello_pong, autogaz), 20 titles tracked, 12 accepted+ingested.

## 3. CROSS-GAME IMPACT (the user ask: "complete them so they impact other games")

1. **VoXide ↔ zenmai/autogaz class proof**: two INDEPENDENT games now
   demonstrate the TX-only/direct-SIO block on beetle+rearmed (VoXide
   menu-inert across 8 buttons × 2 cores; zenmai input-dead) while the
   same-session control (LostPlumber, BIOS-pad class) receives input
   fine — the backend lever (standalone mednafen / PCSX-Redux, write-side
   pad model) now has TWO motivating clients and one live control.
2. **LostPlumber = same-day new-core control**: its RIGHT-scroll causality
   on the identical core+host path validates every negative result above
   (methodology hygiene, r30-class regression excluded).
3. **rearmed core operationalized**: interpreter boots retail-style images
   to title (DRC segfault on OpenBIOS recorded) — a second backend for
   future cross-checks, needed before any TX-only claim can generalize.
4. Route-2 license patching is now a 10-minute turnkey flow
   (r36t1/r36t2 scripts) for any PS-EXE or prebuilt bin — the intake
   bottleneck stays at input-class discovery, not boot.

## 4. Boot ledger (disclosed)

- r36t1 LostPlumber: cap 2, used 2 (boot1 intake + boot2 causality).
- r36t2 VoXide: cap 2 → amended 3 (rearmed decisive experiment) → amended 4
  (decisive input battery) — both amendments BEFORE the runs; used 4.
- rearmed DRC crash: segfault in recompiled code at BIOS PC 0xbfc066f0 on
  OpenBIOS — recorded; interpreter mode used instead.
- Suite: 565 passed + 1 xfail (re-verified this round).
- Game bytes: none committed; patched images in emu/games_homebrew/patched/
  (gitignored); GIFs mirrored into docs/evidence_gifs/.
