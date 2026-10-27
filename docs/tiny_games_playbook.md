# Tiny-Games Playbook — measured lessons that speed up the big games

Round 15 (2026-10-27). Purpose: every tiny game must leave behind
reusable, MEASURED procedure so the next game — tiny or AAA — goes from
"acquired" to "really played" faster. This document is the transfer
layer the round-15 directive asked for: tiny-game lessons must show up
as speedups on big-game work.

## 0. The honest status taxonomy (mandatory in every report)

| status | meaning | evidence required |
|---|---|---|
| RUNNING | disc boots, input reaches the game, screen responds | boot timeline + pad-buffer mirror flip |
| PLAYING | closed loop: observe state -> decide -> act -> observable game effect (a catch, a dodge, a kill) | per-event anchors (RAM word or vision) + input mirror |
| WINNING | play reaches the game's OWN win/goal state | score word / win screen + the full pass ledger |

`RUNNING` must never be reported as "finished". Round 14 retracted a
showcase GIF for exactly this violation (0% interception, paddle never
moved). Round 15's flappy run is the first PLAYING+WINNING with the
full chain: 10 RAM-anchored pipe passes -> the game's own score
counter drawing "10" -> alive at the win frame.

## 1. Boot-route decision tree (measured, use this order)

1. **Game ships an ISO with license sectors?** (check sector 4 for
   "Licensed by") -> mount + boot directly. *FlappyBirdPSX: first-try
   boot, zero patching, ~7 s wall.*
2. **ISO without license?** -> `scripts/make_homebrew_lic.py` local
   patch (Tetrade/Nortis/PSXMC/Doukutsu route).
3. **Raw PS-EXE <= 32 KB?** -> wrap in the PSX-flavored container
   (PVD root dir record at offset **156**, not ECMA-119's 168) +
   license sectors (hello_pong route).
4. **Raw PS-EXE > 32 KB?** -> OpenBIOS `loadExe` single-read cliff
   (16 sectors, measured r14) BLOCKS the container route. Levers:
   stage-1 loader (r14, blocked by the stale-read anomaly) or
   upstream-minimal repro. Do NOT burn rounds here — pick a different
   game unless the big-game plan needs this exact binary.

## 2. Controller truth table (r15 — this cost four dead runs)

ps1play button names are **libretro joypad names**, not PSX names:

| ps1play name | libretro id | PSX button | pad-mirror bit (active low) |
|---|---|---|---|
| `B` | JP_B (0) | **CROSS** | 0x4000 |
| `A` | JP_A (8) | CIRCLE | 0x2000 |
| `X` | JP_X (10) | **TRIANGLE** | 0x1000 |
| `Y` | JP_Y (1) | SQUARE | 0x8000 |
| `START` | JP_START (3) | START | 0x0008 |

Verification ritual (2 minutes, saves hours): find the InitPAD buffer
(signature `00 41 FF FF`), read the u16 at `+2` while pulsing a button;
the cleared bit names the PSX button actually delivered. r15 measured:
`X` -> 0xEFFF (TRIANGLE) — the flappy flap (CROSS) silently never
fired until switched to `B`.

## 3. Input discipline

* **Edge-triggered games fire once per press.** FlappyBirdPSX
  `get_command` keeps `i32_last_padd`: holding the button = ONE flap.
  Any "hold to repeat" assumption dies here. Pulse: 2 frames held +
  >=3 frames released.
* 1-frame taps alias past pad polling (hello_pong r11/r12 lesson);
  2-frame pulses are the reliable minimum.

## 4. Sensor ladder (fastest first; stop as soon as a rung holds)

1. **Source/map symbols** — FlappyBirdPSX: 23 readable .c files gave
   the full mechanic model (flap impulse 256 world = 8 px/f, gravity
   -32/f rising vs -4/f falling, gap 70 px, gate x < -1152) before
   the first boot. For closed-source games: the shipped .map
   (psxBreakout cs50x.map -> 8 sensors in minutes).
2. **Whole-RAM delta pinning during REAL play** (never idle — a
   dedicated verification phase idles the bird to death; r15 lesson):
   i32 scan for the bird (pos.y at 4-aligned), **i16 scan for
   struct fields at base+2** (the pipe pos.x lives at odd 4-byte
   alignment — an i32 scan is structurally blind to it; r15 lesson).
3. **Vision** — bird centroid (color-mask), pipe gap (column band +
   no-green run); RAM only anchors score/pass events.
4. Score word: u16 words equal to the pass count, intersected at each
   event (hello_pong method).

## 5. Vision-servo math (reusable for any 1-D regulation game)

* Measure the action impulse from source/RAM first: one flap = 36 px
  rise over 8 f (fixed 8 px/f decaying 1 px/f). The bang-bang band is
  then arithmetic, not tuning: **flap at target+14 -> apex target-22**
  keeps a 20 px hitbox inside the 70 px gap with margin on both sides.
  The earlier +2 threshold overshot the gap top by 3.5 px and died.
* Scene-color pitfalls, each cost a run: pale bush green matched the
  pipe mask and clipped low gaps (fix: pipe family has r<150); pipe
  shading fragmentation broke column bands (fix: 1-px dilation);
  game-over box is tan, not white (measure the actual pixels, never
  assume).
* Target the pipe that is ON the bird until its box fully passes
  (red zone extends to cam x ~118), not the shiny new pipe behind it.

## 6. Game-understanding pays (the "learn the game" step is mechanical)

Read the source (or decompile) BEFORE playing and derive: death
conditions, scoring trigger geometry, input edge semantics, action
impulse, hitbox sizes. Every one of those five became a concrete bug
fix in the r15 controller. This is the same procedure as Issue #5's
MSX entity-table work — the tiny game just closes the loop in minutes
instead of days.

## 7. Measured transfer (rounds from "new game" to honest states)

| game | introduced | RUNNING | PLAYING | WINNING | rounds |
|---|---|---|---|---|---|
| hello_pong | r11 | r11 | **r14** (after the r13 retraction) | r14 (vs own AI: unwinnable, source-proven) | 4 |
| Tetrade | r4 | r4 | r8 | r8 (DoD closed) | 4 |
| **FlappyBirdPSX** | **r15** | **r15 (first boot)** | **r15 (same session)** | **r15 (score 10, RAM-anchored)** | **1** |

The r14->r15 speedup is exactly the playbook: boot-route tree (1),
controller truth table (2), pulse discipline (3), sensor ladder with
the i16 lesson (4), impulse-derived servo band (5). One new game cost
one session end-to-end including the GIF deliverable.

## 8. Application queue for the big games

* **MSX (Issue #5)**: the r12 lever — trace menu state byte
  `0x80095a7d` through the built-in MISSION SELECT — is sensor-ladder
  rung 2 (delta pinning during real menu navigation) plus the pulse
  discipline for menu taps. No new method needed.
* **Doukutsu (Cave Story PSX, accepted r13)**: menu navigation is the
  flappy servo problem in disguise (cursor y vs target item y, X to
  confirm, edge-triggered). Reuse `r15_flappy_play.py` structure with
  a title-screen classifier.
* **psxBreakout (pending)**: the r14 sensors from cs50x.map are ready;
  the only gate is the boot route (tree item 4). The playbook says:
  timebox boot experiments, do not stall the round on one binary.
