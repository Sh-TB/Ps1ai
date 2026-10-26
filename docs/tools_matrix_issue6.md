# Tool capability matrix — measured on the actual environment (Issue #6, Phase B)

Measured 2026-10-22, host: CPU-only headless Linux x64, no GPU, no X server
except `Xvfb` + Mesa software GL (`swrast`). Existing backend = in-process
`mednafen_psx_libretro.so` (Beetle PSX 0.9.44.1 df2b53b) driven by
`ps1play/core/host.py`.

| Capability | Existing backend (beetle/libretro) | emucap | PCSX-Redux | Ghidra + psx_ldr |
|---|---|---|---|---|
| Input/frame control | `TESTED` — frame-exact `core.run(n, buttons)`; deterministic replay proven bit-identical on Tetrade | `BLOCKED` (as control layer) — no libretro PSX frontend; standalone patched Mednafen only | `TESTED` — `-no-ui -run -iso`, Lua `GPU::Vsync` hooks (900-frame scripted session on real MSX) | N/A |
| Screenshot/observation | `TESTED` — `frame_rgb()`, RAM snapshots | Untested (needs its own process) | `PARTIAL` — Lua can read VRAM; not exercised this session | N/A |
| Checkpoint/replay | `TESTED` — `StateManager` save/restore; determinism control `ctrl=0` | Advertised (`save_state`/`load_state`) | Untested | N/A |
| RAM/register inspection | `TESTED` — `MemoryView` 2MB | Advertised | `TESTED` — Lua FFI `PCSX.getMemPtr()` read of 0x800CA2F6/0xEE518 on live MSX | `TESTED` (static) |
| Execute/read/write breakpoints | None (no debugger interface in our host) | Advertised (Mednafen PSX adapter) | Advertised (Lua breakpoints + GDB server) — `PENDING` next session | Static xrefs `TESTED` |
| Function/call graph | Existing index (re_index.sqlite, 15k records) | N/A | Runtime tracing possible | `TESTED` — **3,957 functions (EXE) + 468 functions (ENEMY.BIN overlay), callers/callees extracted** |
| Setup/build cost | Already integrated | Rust >=1.88 build or prebuilt core packages; separate process + patched Mednafen + retail PSX BIOS needed | `TESTED` — prebuilt Linux x64 zip (87MB, distrib.app Build 470); needs Xvfb+Mesa software GL; extracted + running in ~10 min | Ghidra 11.4.2 (437MB) + full JDK 21 (user-space) + psx_ldr extension; BinaryLoader import path ~4 min analysis |
| CPU/RAM overhead | Low (in-process) | Unknown | Software-GL GUI stack runs headless; 900 frames in <240 s wall | One-shot analysis; cached by hash |
| License | beetle GPL-2.0-or-later (unmodified external core) | GPL-2.0-or-later | GPL-3.0-or-later | Ghidra Apache-2.0; psx_ldr custom-free (verify before code reuse) |
| **Decision** | **Keep as normal gameplay backend** | **REJECT as control layer; possible future oracle** (differential vs beetle) | **INTEGRATE as debugging oracle** (external process; Lua/GDB watchpoints for MSX boss-HP hunt) | **INTEGRATE as static-analysis oracle** (per-hash cache) |

## Detailed results

### emucap — `REJECT` as control layer (`BLOCKED` for libretro)
- Rust toolkit with MCP control; PSX support = patched **standalone Mednafen 1.32.1** via NDJSON/TCP — no libretro adapter, cannot drive our in-process core.
- Would require: separate Mednafen process + retail PSX BIOS + rebuilding the control stack. No practical advantage over our proven in-process harness for gameplay; possible future differential oracle.
- Source-verified capability list (memory R/W, breakpoints, frame step, screenshots) — https://github.com/mcpads/emucap (adapters/mednafen README).

### PCSX-Redux — `TESTED`, decision: integrate as debugging oracle
- Prebuilt: https://distrib.app/pub/org/pcsx-redux/project/dev-linux-x64 (JS app; real asset URL extracted via headless browser; Build 470, 87 MB zip).
- Headless: `-no-ui -run -testmode -stdout -lua_stdout -iso <cue> -archive <zip(autoexec.lua)>`; requires `Xvfb` + Mesa software GL (SDL dummy driver rejected: "OpenGL support ... not available in current SDL video driver").
- Proof run on the real MSX disc: Lua autoexec executed, `GPU::Vsync` fired 900 frames, FFI read of validated HP word `0x800CA2F6` and flags word `0xEE518` (both 0 pre-gameplay — correct), `pcsx_exit()` clean shutdown under `-testmode`.
- Next: Lua/GDB watchpoints to capture the FIRST instruction writing the Iron Nokana boss HP store (Issue #5 BLOCKED line).

### Ghidra + ghidra_psx_ldr — `TESTED`, decision: integrate (static oracle)
- Ghidra 11.4.2 + user-space Temurin JDK 21 (apt only has JRE-style 21; Ghidra needs `javac`).
- Extension zip for 11.4.2 downloaded but its loader was NOT picked up by headless import even after install attempts (`Extensions/Ghidra/`, user `Extensions/` + marker). Worked via `-loader BinaryLoader -loader-baseAddr 0x80010000 -loader-fileOffset 2048 -processor MIPS:LE:32:default` instead. `PENDING`: get native loader working for EXE-header/PSYQ-GDT conveniences (psyq420.gdt etc. ship in the extension).
- EXE import+analysis: SUCCEEDED (622,592 B, sha256 `1508b532…`) — 3,957 functions; anchor `0x8002DB48` (spawn writer from death_path.json) confirmed as `FUN_8002db48` with caller `0x80030A9C` — cross-validates the existing static DB.
- ENEMY.BIN overlay: extracted from disc (LBA 2758, sha256 `809170c7…` = manifest match), code region file-off `0xD180..0x1C2C8` imported at live-verified VA `0x8009C0E8` — 468 functions. Probes: `FUN_800a41d8` (damage entry) exists exactly at the death_path.json address; `FUN_800a87f8` (dispatch) has **8 in-overlay callers** (`8009fafc, 8009fcb4, 8009fdcc, 8009f170, 8009edec, 800a0ab0, 8009f304, 8009f494`) — new evidence extending the death-path graph.
- Evidence: `/home/z/my-project/emu/tools/ghidra_evidence/` (functions JSONs + anchor probes; committed copies under `data/games/SLUS-01212/`).

## Backend compatibility finding (from the homebrew vertical slice)
beetle-psx + OpenBIOS never completes a kernel low-level pad poll for
PSn00bSDK homebrew (Tetrade): padbuff never appears in ANY state (unfilled
`ff ff…`, success `00 41 ff ff`, aborted `ff 41…`) after 600+ frames; no
button byte ever flips FF→F7 under any held button. OpenBIOS source
(`openbios/sio0/pad.c`): `alterUserPadData` only copies data for pad IDs
`0x41/0x23` (high-level path), and low-level `readPad` aborts on tight IRQ
timeouts. Retail-pad games (MSX) unaffected. Classified: **shared
backend/BIOS compatibility defect**, protected by an xfail regression test.

**Cross-backend reproduction (`TESTED` 2026-10-22):** the same Tetrade disc
under PCSX-Redux (which ships its own OpenBIOS build) with Lua
`PCSX.SIO0.slots[1].pads[1].setOverride(BTN.START)` held for two 300-frame
windows still shows no real padbuff (`SCAN held300f/held2_300f`: only
coincidental `00 04 xx xx` data bytes, btn values stable across press
phases — not `0xFFF7`). The defect is therefore **in the OpenBIOS kernel
low-level pad path itself (vs emulated SIO ACK timing), reproduced across
two independent emulators** (beetle 0.9.44.1 AND PCSX-Redux HEAD).
PCdrv-era/retail pad reading (MSX) is unaffected in both. Candidate future
fixes: OpenBIOS-side timing patch, or a plugin-declared compatibility patch
(patched-copy policy: local-only, never redistributed), or retail-BIOS
runners where legally available.

---

## Addendum 2 (2026-10-22) — boot gate SUPERSEDES the pad-defect diagnosis

**Root cause found (OBSERVED, decisive A/B):** every "no padbuff / no button
flip" negative above was produced by a game that had never actually run.
Unpatched homebrew discs (Tetrade, Nortis, PSXMC) **boot-loop inside the
OpenBIOS shello CDChecker**: identical cube animation and bit-identical frame
timelines across three different discs, game EXE never reaches RAM (~72 KB
nonzero after 900+ frames). Copying the 16 license sectors (0..15) from the
user's own retail disc into a LOCAL copy of each homebrew image unblocks all
of them (RAM 72 KB -> 555 KB; game loads; title screens render).

**With the game actually running, the beetle+OpenBIOS pad path works:**
- padbuff fills: `00 41 ff ff` at 0xBB120 / 0xBB142 (Tetrade's own buffers)
- buttons deliver: held libretro X -> btn word `ff ef` = `0xEFFF` = TRIANGLE
  (beetle mapping: RETRO X -> PSX TRIANGLE); START -> `f7 ff` = `0xFFF7`
- full input causality chain proven for Tetrade: START -> title -> menu,
  CROSS -> Marathon gameplay, piece responds to LEFT/RIGHT (visual diffs
  21.75 / 0.62 / 0.54; screenshots in the Issue #6 report)
- PSXMC (MIT) and Nortis (license-blocked) also boot and respond to input
  after the same local patch

Status changes:
- `SUPERSEDED`: "OpenBIOS kernel low-level pad defect on beetle" — the
  padbuff absence was a boot-gate symptom, not a pad-path defect.
- `STALE, PENDING re-test`: the PCSX-Redux-side scan (game ran there, yet no
  padbuff) — re-test under the license fix before drawing conclusions.
- `IMPLEMENTED`: scripts/make_homebrew_lic.py (local-only patched images;
  never committed) + tests/test_plugins_contract.py::test_real_tetrade_lic_
  input_causality (subprocess-isolated: beetle holds global emulator state,
  one clean boot per process).

Practical rule for the lab: **one beetle boot per process**; boot-gated
discs must be license-patched locally before any input-causality claim.

---

## Addendum 3 (2026-10-25) — round 4: three games advanced in parallel

**Nortis — full LOCAL causality chain (A6-grade, integration still blocked):**
START → gameplay (gray diff 11.58; session-3 independent run 11.66), falling
piece motion 7/7 windows, LEFT dx slope −11.0 px/sample / RIGHT +16.0
(controls 0.0), CROSS hard-drop 183 px vertical extent vs 31 px control, and
CIRCLE-held suppresses the CROSS hard-drop (fall speed 31 vs 175) exactly as
upstream `pad.c` button-priority predicts. START is a no-op mid-game
(negative control, matches source). License re-probe via authenticated API:
98 files, 0 license files — `REJECTED` stands, evidence upgraded.

**PSX-Minecraft — GAMEPLAY_CONFIRMED:** directional movement with reversal
(LEFT 120f madiff 21.45 → RIGHT-after-LEFT 5.25, 75.5% restored); look-loop
down→left→up→right returns a BIT-IDENTICAL baseline (madiff 0.0); R2 attack
digs a persistent world change (30.64 / 44991 px); R1 jump lands bit-exact;
START inventory opens on RELEASE (mid-hold 0.0); idle windows are bit-exact
(0 changed px) vs held 15–46. Bindings ground-truthed against upstream
`bindings.c` @ `infdev_2025_04_18`, verified 1:1.

**hello_pong — artifact obtained + BOOTED (blocker was stale):** the recorded
"401 token lacks Actions:read" was actually the shared sandbox egress IP
hitting the GitHub rate limit (403 with a rate-limit body). With the EXISTING
Ps1ai token: artifacts listing 200, zip download 200, zip sha256
`51321870…bc49` matches the API digest exactly. Extracted `hello_pong.bin`
(2,500,176 B, sha256 `a592f7ed…af247`, BOOT=cdrom:\GAMEPS1.exe;1), built the
standard local license-patched image: BOOTED at f1200 (static game screen,
frame_mean 20.24, padbuff `00 41 ff ff` ×2, stable to f2100; screenshot shows
GAME OVER / PLAYER 1 WINS! / PRESS X TO PLAY AGAIN). Unpatched control
reproduces the CDChecker cube boot-loop. Accepted on boot evidence; input
causality (X restart) is the round-5 target. An earlier `BOOT_FAIL` verdict
from a workspace missing `openbios.bin` is recorded honestly and superseded.

Manifest updated accordingly: accepted = tetrade, psx-minecraft, hello_pong;
candidates_pending = []. New probe scripts persisted outside the repo:
`scripts/nortis_causality.py`, `scripts/psxmc_causality.py`,
`scratch/issue6_round4_hellopong/boot_hellopong.py`.

---

## Addendum 4 (2026-10-25) — round 5: the complete-game round

**hello_pong — second game with a COMPLETE played loop (after Tetrade/`3a76322`):**
controls ground-truthed from upstream `src/libs/game_pad.h` (`PAD_BUTTON_X =
0x4000` = PSX CROSS = libretro **B**; libretro X = TRIANGLE = in-play pause,
negative control madiff 0.0). X-restart causal (GAME_OVER → MENU → PLAYING,
madiff 4.223). **PLAYER_CONTROLLED**: left paddle UP dy −90.0 / DOWN +169.0
(reversal proven), RIGHT clean no-op, right paddle static — no AI
(`P1: OK / P2: OK`). Steered play tracked the ball; ball exit → natural
GAME_OVER **bit-identical** to the boot screen (madiff 0.0) → restart →
second cycle. Whole game ≈170f, ends after ~2 points. Quirks honest:
winner text constant, paddle position carries across restarts.

**Nortis — COMPLETE LOCAL GAME LOOP, no line clear (honest):** boot →
16-piece greedy steering run (shallowest-reachable-column policy with
piece-masked board perception) → NATURAL game over ("GAME OVER! TRY AGAIN /
PRESS START", PNG-verified) → START restart → empty board + fresh piece
(diff vs entry 0.71, falling blob 204 px). Line clear NOT achieved across
**6 policy iterations** on the deterministic RNG — score/lines causality
stays UNPROVEN (counters 0). The iteration record (border poisoning,
spawn-piece contamination, HUD-strip false positives, and the **inverted
steering direction bug** fixed in v6) is preserved in
`scratch/issue6_round5_nortis/report.json.iterations` — the learning loop
the lab documents, dead ends included.

**MSX (main game, issue #5 session 8, run in parallel):** the WINTER scene
after the train fade-out is the **ATTRACT DEMO** — decisive probes:
input-free watch self-advances (px 76.4→428.6, score 0→4000), one START tap
aborts to the PSX main menu (px→0.0, flags→0), RIGHT-hold does nothing
while the demo's own player fights (px frozen 5.1, score climbing). The
session-7 "wall-stuck damage-tick" pattern is the demo's player. Real M2
ride reproduced (px 76.4→822.4, score→10930, zero deaths) from the
session-7 `m2_train` anchor — restored bit-for-bit deterministic. 0xC
banner still uncaptured; levers recorded in `m3_verdict.json`.

## Addendum 5 (2026-10-25) — round 6: Nortis line-clear causality closed; M2 terminus characterized; playloop tool

**Nortis — the round-5 gap (line clear NOT achieved) is CLOSED.**  The
path was calibration-heavy and is the lab's best documented learning
loop yet: six probes (`nortis_calib{,2..6}.py`) pinned the release
binary's true memory layout — GameState @0x15FB0 (7 u32s), settled
field @0x1615C (26x10 u32s, stride 40, row = positionY-2) with a
second copy @+0x410, render array @0x15FCC that misleadingly contains
the active piece (three probes burned before the
changes-only-at-commit behavioral isolate), and **starting terrain**:
title-screen leftovers (S+T pieces, field rows 10-13) the binary never
clears — invisible to every previous PNG-based policy.  Input: 1 cell
per press-edge, ROTATE=CIRCLE(A), DROP=CROSS(B), one action/frame,
gravity 20 f/row (source flipped-args bug: level pinned to 20).
`nortis_lineclear.py` (RAM-truth greedy, clear-first scoring, per-piece
plan verification): **lc10 = 62 pieces, 50/62 plan-perfect, 5 line
clears; cycle 1: clearedLines 0->1->2->3 -> natural game over; START
restart -> cycle 2: 0->1->2 -> natural game over.**  `points` stays 0
(the source never increments it).  Verdict: **GAMEPLAY_CONFIRMED +
CAUSAL (lines counter)** — Nortis now has a complete played game WITH
line-clear causality, twice.

**MSX session 9 (issue #5, the 50% main-game share):** the M2 train
ride's deterministic terminus is now fully characterized — ride
px 76.4->822.4 (score 10930, php 121, no death) -> scripted crash
teardown -> **NOW LOADING** (52 s) -> attract-logo cinematic (f1200-
2400) -> a WINTER world spawns at f4020 (px 120.3, php 120, score 0,
fresh run state) that is **input-dead** (RIGHT probe: the demo's own
player self-moved -35.7 px and took damage).  SELECT-feeding the
loading window (v5) and early START taps (v6) = honest negatives.
Arcade-order ground truth (fandom): no train mission exists in
MS2/X arcade — the SLUS train section is Arrange-specific.  The
M2->M3 gameplay gate stays OPEN; recorded next lever = attract-flag
RAM hunt around the loading window.  6 variant reports +
ladders in scratch/issue6_round6_msx/.

**New tool: `scripts/playloop.py`** (+ 5 mock tests) — the reusable
game-loop driver (one boot/process, Observation bundle, pluggable
policies, honest verdicts, JSONL+report).  hello_pong dogfood: the
artifact was REFETCHED through the documented API procedure (zip
sha256 51321870... == manifest; bin a592f7ed... == manifest),
re-patched locally, and the loop ran through the tool: boot ->
natural game over (madiff 5.61 -> 0.0 static) -> X restart ->
transition **madiff 4.223 — the round-5 causal signature, reproduced**.
Score-region causality INCONCLUSIVE (the blob steering detector found
no ball: threshold tuning pending; paddle control was round-5-proven).

Suite 482 passed + 1 xfailed (5 new playloop tests).

## Addendum 6 (2026-10-26) — round 7: Tetrade line-clear causality closed; PSXMC place-block causality + persistence; MSX gate decisive negatives; playloop generalized

**Tetrade — LINE CLEARS + complete played game x2 cycles (through the
tool).**  Source-first (upstream src/main.c v1.0: board 10x20, struct
offsets, `BASE_DROP_RATE 30`, A=CIRCLE rot CW / B=CROSS rot CCW /
UP=hard-drop, `check_lines` adds `200/500/700/1000 * level` — 0 at
level 0) then a one-boot calibration ladder: LEFT-tap whole-RAM u32
diff → exactly one hit → live base `0x1FECA0` (matrix 20x10 @+0, type
`0x1FEFC0`, x `0x1FF004`, y `0x1FF008`, score `0x1FF584`, single
`0x1FF588`, level `0x1FF5A0`, over `0x1FF5A8`; savestate anchors;
soft-drop 1f-tap delta 0 = honest negative, reproduces the Issue-8
record).  Main run through the generalized playloop tool: **39 pieces,
8 LINE CLEARS** — cycle 1: singles 0→1→2 then a TRIPLE (lines
0→1→2→5), natural game over (score 532) → CONTINUE? refused with
CIRCLE → counters verified reset → cycle 2: 3 more singles → natural
game over (474).  Score stays drop-driven (+2/cell) as source predicts.
Verdict: **GAMEPLAY_CONFIRMED + CAUSAL (lines counters)**.  Evidence:
`scratch/issue6_round7_tetrade/`.

**PSX-Minecraft — the PLACE campaign: honest INCONCLUSIVE(place) with
the failure root-caused and a confirmed use-consumption chain.**  The
first battery aimed only 2-12 deg below the horizon (90 deg ≈ 228
frames at the measured 18432 raw/f) — the crosshair never touched
terrain, and even R2 dig went non-persistent there; the fine-aim
loop's residuals were ±100-175 deg (asymmetric look rates).  The
monotonic pitch-sweep follow-up produced giant full-screen diffs that
the sharper place4 iteration identified as the CRAFTING UI overlay
(the game ticks ≥2x per frame: tick1 USE acts, tick2 raycasts the
just-placed table and opens its modal, block_crafting_table.c:232;
the START guard then left the inventory open — place3's "placements"
are retracted as UI artifacts).  place4 (fine aim err <1 deg, geo
gates, UI-recovery): USE taps consume the selected stack with
ItemID-context verification — chain 26→25→24→23 @`0x7cda0`
(CRAFTING_TABLE) — but zero VISIBLE world placements (world_px 0 in
every attempt); attempt 3's raycast then HIT a placed table (UI
opened, ui_px 36852) — evidence the earlier USEs did modify the
world, just out of frame.  Savestate round-trip on the edited world:
RAM bit-exact + frame bit-exact at t+1 + functional re-edit accepted
on the restored world.  Verdict: **INCONCLUSIVE(place)** —
stack-consumption CAUSAL, visible placement unproven; next lever =
camera framing the target face + post-place world_px gate.  Evidence:
`scratch/issue6_round7_psxmc/` (report_place3.json, report_place4.json).

**MSX (issue #5) — the M1→M2 gate gets decisive negatives.**  From the
post-banner CONTINUE? gate: a 41-offset tap-timing sweep (24f steps,
savestate-restored frame-exact retries, `msx_m2_gate_sweep.py`) landed
in the input-live M1 endzone **41/41** (gs1); a 5400f quiet watch
self-resolved into the attract demo (gs2); with m2t8/rg1-rg4 that is
**8 documented attempts, zero M2 spawns** — the session-6 "one START
accepts into M2" record does not reproduce from this gate instance and
is corrected to "path-sensitive, mechanism unknown".  Offline mining
of the rg1 attract-ladder tracker (1.03M changed bytes,
`msx_m2_candidates.py` → candidates.json) top families decode as the
16-byte-stride entity pool (self-referential pointers), not flags.
Recorded next lever: the surgical M1-end vs M2-side loading diff —
requires the m2_train anchor.  The rg1-vs-session-9 number discrepancy
was diagnosed and closed (different missions/rides/policies —
`discrepancy_rg1_vs_session9.md`).

**Tools:** `scripts/playloop.py` generalized (`--policy/--cue/
--workspace`, GAME_DEFAULTS + POLICIES registry {pong,tetrade},
verdict_flags hook; `--game pong` default unchanged) + 3 new tests.
Suite **485 passed + 1 xfailed**.  No game bytes committed; all patched
images local-only.

---

## Addendum 4 (2026-10-26) — round 9: pin-capture methodology + 2-ply Tetrade engine + honest probe failure

**MSX (issue #7 WAGON RUN).** `scripts/msx_wr9_arena.py` (T4 sensor
walk), `msx_wr9_cap.py` (v1: 70,351 f, max_px 2212, 1,365 sensor
spawns), `msx_wr9_cap2.py` (v2: PIN-BASED arena capture — alive AND
px >= 1400 AND px-window < 10 over 3x60f chunks — saved `wr9_arena`
at px 2212.0 with a 35-slot census). `msx_wr9_leaderkill.py` runs one
arm per boot (C control / YB sustained UP+FIRE / J1 hop+UP-lob /
GR grenade economy / MIX rotation) from the savestate with disclosed
restores, hp-drop/kill bookkeeping, squadron-collapse watch and a
300f RIGHT walk probe for camera-unlock. Round-9 result: armored-kill
CAUSAL (16 kills of the 300-HP 0xA0D0 trio, +500 each), CAMERA-HELD
0/8 — the entity-class gate was replaced by the pin signature after
census showed the pins held by non-chopper families (CHOPPER_ST
extended to include 0xA0D0/0xAB94, disclosed).

**Tetrade.** `scripts/tetrade_r9_tetris.py`: 2-ply placement AI
(Dellacherie + TETRIS bonus) swapped INTO the untouched round-7
playloop policy object; next piece read from live RAM (base+896,
promotion cross-check 715/715); per-frame RGB ring dumps pre/post
vanish PNGs around 4-line clears. All five round gates CAUSAL
(tetris x2 exact-scored, natural 1->2 flip x2, L2 cadence 86/86 = 13
f/cell, 205/205 + 12/12 score suite, full drop ladder L0..L18).

**PSXMC.** `scripts/psxmc_r9_place6.py`: stable-frame grabs (two
consecutive bit-exact), no camera movement between pre/after, live
raycast map via the R2 breaking-state. Honest probe failure (control
arm anomalous in a fresh world) with the two recorded instrument
fixes; the place campaign remains open.

Suite **489 passed + 1 xfailed**. No game bytes committed; patched
images and savestates local-only.

### Addendum 4 (2026-10-26) — round 10: three games advanced in parallel

**MSX (issue #7).** `scripts/msx_r10_cap.py` regenerated the px-2212
arena pin from a fresh boot (57,482 f, 31 disclosed continues, census
= 3x 300-HP 0xA0D0 slots 10-12, wr9_arena savestate). `msx_r10_
timergate.py` (fight/kite/hold) confirmed the front duo kill-causal
again (+500/slot) but survival after field clear caps at 1,140 f —
the 300 s rollover (18,000 f) is unreachable while the rear spawner
lives; verdict INCONCLUSIVE_SURVIVAL_CEILING. `msx_r10_rollover.py`
added a 1 Hz countdown hunt (12 x 60 f RAM snapshots, u16 exact
-decrement/s): **NO 1 Hz timer word exists in main RAM** — the "300 s
timer" is not a u16 countdown at the arena; engineered survival (edge
hold, early jumps, anti-air, grenade lobs) still ceilinged at 21.1 s.
`msx_r10_rear2.py` proved the rear spawner REACHABLE without walking:
surgical 2 f turn + stationary grenade lobs landed a slot-12 HP drop
(+200 damage points, REAR_DAMAGE_CAUSAL) — but the trio cycles to
respawn-pending within ~100 f of engagement and the player still dies
~16 s in. Continue-landing map from the cap trace: 1164 (chopper pin,
dozens of landings) and 1424-1525 (truck pin); **no checkpoint past
2212** — the arena is one-pass. Issue #7's >=50-wagon target stays
blocked at the gauntlet, now with the spawner-reachability + timer
absence + checkpoint map evidence recorded.

**Tetrade (issue #8 DoD closure).** `scripts/tetrade_r10_plugin_loop
.py` ran the COMPLETE loop through the plugin contract v1 with zero
core edits (PS1Play.run_steps/observe/play -> TetradePlayPlugin hooks
only): boot -> title -> menu -> Marathon -> 151 pieces / 41 clears
(score gate 41/41 exact, level-0 clears zero clear-pts per source) ->
6 natural level flips 0->6 (thresholds exact) -> next-piece RAM read
150/152 (98.7%) -> natural game over at level 6 (score 33,582,
0x1FF5A8) -> CONTINUE refused (CIRCLE) -> restart -> fresh Marathon
(counters zeroed + live piece). All five issue-#8 DoD items PASS/CAUSAL.

**PSXMC.** Round-9's two mandatory fixes both closed: FIX-1 per-
attempt bit-exact stability gates (`stable_gate`, sha twice 8 f
apart); FIX-2 the R2 breaking-state oracle VALIDATED (straight-down
x3 in-column/in-reach/world-arbitrated, clean horizon negative) after
three instrument root-causes: (1) chunk offset — capstone disasm of
the fixed binary (`worldGetChunkBlock` @0x80025ab0 / `chunkGetBlock`
@0x8001c120) pinned World.chunks @ +0x3144 (ax + 7*az, NULL = idle
slot — the r10 '49-consecutive-pointer' runtime scan failed on the
5x5-loaded window) and Chunk.blocks @ +0x8C (x + 8z + 64y, x
innermost); (2) id deref — upstream block.h (@infdev_2025_04_18):
IBlock is a vtable-first interface, Block.id is a u8 BEHIND a pointer
at IBlock+0 (callers do `lw`+`lbu`); (3) base algebra in the fallback
scanner. Ground truth for this spawn: real surface y=7 (not the
flatland 4/5). `psxmc_r10_place7.py` v2 digs a world-arbitrated cell
2-3 blocks ahead and places into the hole with converging sensors
(world id 0->non-zero + stack delta + PNG diff); the place campaign
verdict is recorded in `scratch/round10_psxmc/place7/report.json`.

Suite **521 passed + 1 xfailed**. No game bytes committed; patched
images, workspaces and savestates local-only.
