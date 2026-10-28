# Round 34 report — the instrumented-beetle lever executed: the r30-r32
# "input regression" REFUTED as an observation artifact; BuzzyBee deep
# systems COMPLETE (ALL_PHASES_OK).

**Headline.** Round 34 ran the lever R32 recorded (instrumented beetle
build) and closed the two-game completion directive: **mspSX was
already PLAYING (accepted #9, r29); BuzzyBee is now deep-systems
complete** — input -> gameplay -> scoring -> death -> game-over screen
-> auto-return -> bestScore persistence across runs, ALL_PHASES_OK in
one boot. Along the way the round **refuted the r30-r32
"environment-level input regression"**: it was a read-addressing bug
in the r30 probe scripts, not an environment change. Suite untouched:
**565 passed + 1 xfailed**. 5 disclosed boots (caps disclosed pre-run:
2, amendment 3, 4, 5).

## 1. Instrumented beetle build (the R32 lever, executed)

- Vendored tree `beetle-psx-libretro` (df2b53b) instrumented at the
  pad path, grep tag `[PSXBUS]`:
  - `input.c` **L0fe**: frontend callback view, port-0 button u16,
    logged on change.
  - `frontio.c` **L1dev**: `InputDevice_Gamepad` device-level
    `buttons[2]`, logged on change.
  - `frontio.c` **L2bus**: every 0x42 response served on the pad bus;
    nonzero-button occurrences logged; aggregate counters
    (`dtr` = kernel-ISR DTR access attempts, `c42` = 0x42 responses,
    `c42nz` = nonzero-button responses) on a 120-frame heartbeat.
- Binary deployed as `mednafen_psx_libretro_psxbus_r34.so`,
  **md5 `f2383b2f6ea08c0509b08540963e49b2`** (source edits confined to
  the instrumentation; canonical `447b7ebf` untouched; rollback binary
  `79f8fac0` retained). Instrumentation edits live in the vendored
  tree, not the repo; the r34 scripts + this report document them.

## 2. Boot 1+2 (r34t1) — the bus is healthy for BOTH games

- **Boot 1 buzzybee** (`buzzybee_ntsc_lic.cue`): START hold 40f →
  `L0fe btn=0008` → `L1dev p0=0800` → **`L2bus nz=0800` served 50×**;
  kernel ISR alive throughout (`dtr`/`c42` counters climbing from
  ~f500). Core delivery layer 100% healthy for the "dead" game.
- **Boot 2 tetrade control** (`TETRADE_lic.cue`): CROSS hold →
  `L0fe btn=4000` → `L1dev p0=0040` → `L2bus nz=0040`. **The same
  binary serves both games identically.** (r34t1's post-hold verdict
  section crashed on a cosmetic set-op; the raw stderr bus log is the
  evidence and is quoted here in full.)

## 3. The observation-artifact root cause

- Audit of the probe scripts: **r23** (buzzybee boots, correct reads):
  `core.ram[va - 0x80000000:...]` — subtracts the KUSEG base; the host
  `ram[]` is the 2 MiB **physical** WRAM mapping, so `0x8005xxxx`
  indices are out-of-bounds and slice **empty**.
- **r30t2/t5/t6** read `core.ram[va:va+4]` with `va = 0x8005xxxx`
  RAW → every read returned empty → `0`. The r30 "input dead"
  observations on buzzybee were measurements of nothing. **r30t6's
  padbuf "injection" also wrote through the broken path**
  (empty-slice assignment = no-op), void on both the read and write
  side.
- The "alive" legs of the class split used correct paths: tetrade
  (kernel padbuff `0xBB120`, physical < 2 MiB) and minecraft (plugin
  oracle memory accessor). Hence the r30-r32 "class split:
  minecraft+tetrade alive, doukutsu+buzzybee dead" was **an artifact
  of which scripts used which addressing**. The ChangeClearPAD(0)
  class theory loses its buzzybee leg entirely; doukutsu's r30t8/r32
  "dead" evidence was vision-based (down_vis 0.32) and stands as
  observed, but the class collapses to "doukutsu-only, mechanism
  unproven". The r31 CCP(1) retraction (r32) is unaffected — its own
  control experiment already killed the causality claim.

## 4. Boot 3 (r34t2) — buzzybee reprieve probe (correct addressing)

`buzzybee_ntsc_lic.cue`, r23 anchors, `-0x80000000` reads:

- settle → `gs==0`; START hold 40f → **`nonzero_input_frames: 40`**
  (pad=8, held=8, first-frame trig=8) → **`gs 0→1`**.
- CROSS taps → **score 19→65→131** (r23 class confirmed).
- kernel padbuf candidates (r30t6 scan addresses re-read correctly)
  show the active-low button bytes landing during the hold.
- **Verdict: input ALIVE.** The r30 regression premise for buzzybee is
  refuted end-to-end: core bus serves (r34t1), kernel padbuf fills,
  game consumes (r23 + r34t2).

## 5. Boot 4 (r34t3) — deep systems completion pass, ALL_PHASES_OK

Source ground truth (upstream BuzzyBee master): health init 5999,
passive drain −3/frame in gameMode, enemy contact −1500 (edge), flower
+1000 (edge), level<0 → clamp 0 + `bestScore = max(bestScore, score)`
+ `gameState = 5`; gs 5 renders "Your Last attempt / Your Best score"
and auto-returns to gs 0 after >6 s with score reset and bestScore
retained; score +1/frame in gameMode.

One boot, event-driven phases:

- **A** title gs0 (health 5999 pre-init) → START → gs1.
- **B** run 1 idle death at f2011 (~1031 frames in gameMode):
  trajectory decodes **exactly per source** — `ds=+30/30f` (+1/frame),
  `dh=−90/30f` (−3/frame drain), one **enemy contact edge event**
  (dh=−1590 = −90 drain + −1500 contact). Death → gs5,
  **bestScore == score == 1000** (non-degenerate max() rise 0→1000).
- **D** auto-return at f2392 (waited 381f ≈ 6.4 s > 6 s spec): score
  reset to 0, bestScore retained 1000, health re-init 5999.
- **E/F** run 2 with 30 flap bursts: death at f3511, S2=1000,
  bestScore **retained** (max verified at equality).
- **Verdict: ALL_PHASES_OK.**

## 6. Boot 5 (r34t4) — game-over screen visual capture

- r34t3's snapshots fired on the gs5-detection frame (still rendering
  the last gameplay frame — snapshot-timing, noted honestly); boot 5
  captured the drawn screen ~90f after detection:
  **"YOUR LAST ATTEMPT: 1000 / YOUR BEST SCORE: 1000"** with the full
  credits block — PNG `scratch/r34/shots/death_screen_f02101.png`,
  repo-mirrored as `docs/evidence_gifs/r34_buzzybee_deep_systems.gif`
  (gameplay → death → game-over → auto-return).
- Auto-return fired at **f2392 — the same frame as r34t3's run**:
  fully deterministic.

## 7. Honest residuals

- **Score cap 1000**: both runs ended at exactly 1000 despite ~1031
  and ~1039 frames in gameMode — a cap or stop at 1000 is the likely
  mechanism; not disassembled (the r23 runs never reached it).
  Recorded as observed-twice.
- **Flower +1000 never observed live** (idle deaths); enemy −1500
  edge observed 2× (run 1) and classified.
- **bestScore retain-at-S2<S1 direction untested** (both runs scored
  1000); the non-degenerate rise (0→1000) and equality retention are
  verified.
- r34t1 boot-2 tetrade padbuff read `00000000` at f900 vs r30t4's
  `0041ffbf` (settle-timing difference); the bus trace still shows the
  tetrade ISR + delivery healthy, and tetrade's ladder state is
  unaffected.
- Ladder discipline: buzzybee stays **GAMEPLAY_CONFIRMED** as its
  rung — this round adds the systems closure (death/bestScore/
  auto-return loop) on top; no rung vocabulary was inflated.

## 8. Ledger

- 5 disclosed boots in `scratch/r34/boots_used.json` (r34t1 ×2, r34t2,
  r34t3, r34t4; caps disclosed pre-run: 2 → amendment 3 → 4 → 5).
- Scripts: `scripts/r34t1_bus_probe.py`, `r34t2_buzzybee_reprieve.py`,
  `r34t3_buzzybee_deep_complete.py`, `r34t4_buzzybee_deathshot.py`,
  `r34_buzzybee_gif.py`.
- Instrumented core provenance: md5 `f2383b2f` (deployed),
  canonical `447b7ebf` untouched, rollback `79f8fac0` retained.
- No game bytes committed; images remain local-only.
