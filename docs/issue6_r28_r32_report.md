# Rounds 28-32 lab log (session 5): one rung promotion, one honest class-kill, one retraction

Commit 647fe2c, suite 565 passed + 1 xfail (re-verified at close), 23 disclosed
boots across 5 ledgers. Environment events: the **5th filesystem rollback**
(mid-r28) wiped all game images + candidates + scratch again — every consumed
artifact was SHA-re-fetched byte-identical (MSPSX d35a189b, BuzzyBee EXE
9b0bfc08 → NTSC image 042b94bb, doukutsu bf15559e, BIOS md5 664ee444); the
push helper's silent GET-with-body bug on Git Data API POSTs was found and
fixed (deterministic 404 → method="POST").

## R28 — air_hockey: RUNNING → COMPLETE_LOOP_OBSERVED (7 disclosed boots)

- Boot 5 (wordspace) was cut off by the session boundary with no verdict;
  its partial paddle pins were reused as seeds (disclosed).
- Boot 6 (seeded-pin chase) produced the PNG-verified **complete loop**:
  score digits live (00%01 → 02%02 → 03%07 across shots), natural match end
  with **CONTINUE? countdown "2"** (@f11533), fresh match in a **NEW arena**
  (@f16933, 01%00).
- Honest misses: both word-space paddle pins turned out to be input-driven
  **accumulators** (probe range vs chase range wildly different) — our-goal
  agency is NOT claimed. The byte-diff score-box counter over-triggers (crop
  catches the COM meter edge); the PNG chain is the evidence.
- Ledger hygiene: a count-field bug (log appended without increment) was
  caught by the next boot's assert and fixed with a disclosed note.

## R29 — mspSX (Minesweeper Plus): RUNNING → **PLAYING (RAM-guided bot)**, accepted #9

- Asset re-fetched byte-identical after the rollback; source ground truth
  fetched from upstream `main.c` (zero boots): `Cell board[24][16]` (12 B
  cells), offset = **cursorX*192 + cursorY*12** — this closes the r22/r23
  layout ambiguity (the old A/B candidates were both transposed and only
  agreed at the (1,1) probe point).
- One clean boot, ALL_PHASES_OK in 1254 frames: exact board decode (192
  active, 32 mines) → 2-tap step-verified navigation → zero-cell **flood
  reveal 6 cells** (REVT 0→6, PNG numbered borders) → **CIRCLE flag**
  (flagged+1, mine_count 32→31) → navigate to a decoded mine → CROSS →
  **PREDICTED {lost:1, ctrl_dis:1} == observed**, "GAME OVER." PNG with the
  full-board mine reveal → START restart (fresh board, cursor 0,0).
- Boot 1 was a disclosed script-bug stop (my flood>=8 assert vs a valid
  6-cell flood); boot 2 was the pre-run-disclosed retry. Provenance
  complete → **accepted #9** (Unlicense + MPL-2.0 vendored spi.c note).
  No WIN claim (160 reveals); chord mechanic recorded as next lever.

## R30 — buzzybee deep: BLOCKED by an environment-level input regression (9 boots, parked)

The r23-proven START transition does not reproduce on a byte-identical
image. The full isolation matrix, all disclosed:

| probe | result |
|---|---|
| beetle (rollback binary 79f8fac0) | input_pad/held/trig all ZERO through 40f holds + double-taps; the kernel padbuf IS actively polled (valid released-state, not stuck 0xFFFF) |
| beetle rebuilt from vendored df2b53b (md5 447b7ebf; the documented f3b4a4be core + *.orig.so were destroyed by the rollback) | ALSO dead — the core binary is not the variable |
| PCSX-ReARMed (fresh per-backend ledger) | dead — not beetle-internal |
| direct padbuf injection | does NOT reach the game — the kernel rewrites the buffer every frame from its own SIO poll |
| Tetrade class probe (same binary+host) | input ALIVE (padbuff 0041ffbf during a CROSS hold = the exact CROSS bit; START vis 83.58) |
| doukutsu class probe | DEAD now — was ALIVE the same morning (r24/r25, pre-rollback) |

Class split observed at that point: Tetrade (ChangeClearPAD(1)) alive;
doukutsu+buzzybee (ChangeClearPAD(0) family) dead. buzzybee **PARKED at
GAMEPLAY_CONFIRMED** (no rung inflation) per the standing directive.

## R31 — the CCP(1) patch claim → SUPERSEDED by R32's control

Minecraft's source uses the same CCP(0) class, so a 1-instruction
ChangeClearPAD(0)→(1) patch (ELF-symbol-located at inputInit, image
PSXMC_lic_ccp1.bin, local only) was applied and its probe passed (pitch
ring + movement + reversal). **r31 claimed the patch caused it. That claim
was wrong** — see R32's control. The patch image remains harmless-but-
unevidenced; the rung status of minecraft did not change (already
place-confirmed).

## R32 — the control that corrected the record (4 boots, retraction)

- The CCP(1) rollout to doukutsu failed through three patch states (2 → 8
  → 9 sites, including addu-encoding moves found by a widened arg window
  and the pad-mode dispatcher `sltiu $s0,$s2,1` forced to always-CCP(1));
  down_vis stayed 0.32 in every state. The PSN00bSDK stub was
  ground-truthed as **B(0x5B)** from the minecraft ELF and the sector-aware
  ISO VA mapping was validated via an InitPAD caller (the argument lives in
  the jal DELAY SLOT, which is why naive adjacency scans miss it).
- **The control experiment**: UNPATCHED minecraft, identical probe → input
  ALIVE. r31's causality is **retracted**: minecraft receives input with or
  without the patch.
- Final honest split: minecraft + Tetrade BIOS-pad inputs alive;
  doukutsu + buzzybee (same input.c family) dead — per-game, mechanism
  unknown, and the morning-vs-now flip remains unexplained despite
  byte-identical images, BIOS, host code and two core binaries.
- Recorded lever: an **instrumented beetle build** from the vendored
  df2b53b tree (builds clean in ~3 min) with SIO/interrupt trace pins —
  the only remaining path into the kernel-pad delivery for the dead class.

## Library state after R32

tetrade PLAYING (99.86% landing bot) · hello_pong WON 5-0 · mspSX
PLAYING(bot) · flappybird deep-complete · air_hockey COMPLETE_LOOP_OBSERVED
· autogaz FULL_CYCLE_CAUSAL · psx-minecraft place-confirmed · doukutsupsx
GAMEPLAY_CONFIRMED (class-blocked) · buzzybee GAMEPLAY_CONFIRMED
(class-blocked) · zenmai PARKED (r26). No game bytes committed; every boot
amendment disclosed pre-run; two script-crash boots counted honestly
(r28 boot 2 KeyError, r30 rebuilt-core boot 2 numpy-write misuse).
