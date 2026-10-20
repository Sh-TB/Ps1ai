# PS1Play — an AI agent that plays PS1 games by reading RAM

<p align="center">
  <img src="docs/demo.gif" alt="PS1Play playing Metal Slug X Mission 1, headless" width="480">
</p>

<p align="center">
  <b>Metal Slug X (SLUS-01212)</b> running fully headless on a libretro core,<br>
  played by a zero-token agent that <b>never looks at pixels</b> — it reads the emulated 2&nbsp;MB RAM as numpy arrays.
</p>

---

## What is this?

**PS1Play** is a plugin-based, agentic framework that boots PlayStation 1 games with
**no GPU, no X11, no window** — a pure-Python (ctypes) libretro frontend runs the
Beetle PSX core at **~110–400 fps** with software rendering — and then plays the game
**like a human**: it only injects pad buttons, and it *perceives* the game entirely
through **RAM bytes**.

Three hard design rules make it different from typical "AI plays games" demos:

1. **Zero pixels for decisions.** Screenshots are saved as evidence for humans only.
   The agent's perception is numpy analysis of the live 2 MB main RAM — the same
   information a GameShark sees, used for *reading*, not cheating.
2. **Zero LLM tokens at runtime.** No vision model, no language model in the loop.
   Discovery, world-modelling and the policy are classical algorithms (numpy).
3. **Legal inputs only.** During real runs the agent never writes a byte of game
   memory, never rewinds. Savestates are used only for read-only calibration probes
   and checkpoints. (A full GameShark engine exists as an opt-in assist and is
   verified with event proofs.)

## How it works

```
                        ┌──────────────────────────────────────────────┐
                        │                libretro core                 │
                        │        (Beetle PSX, software renderer)       │
                        └───────────────┬──────────────────────────────┘
                                        │  ctypes frontend (core/host.py)
             button injection           │              live 2 MB RAM view (numpy)
        ┌──────────────────────────────►│◄──────────────────────────────┐
        │                               │                               │
┌───────┴────────┐              ┌───────▼────────┐              ┌───────▼────────┐
│   policy.py    │              │  worldmodel.py │              │ perception.py  │
│ dodge > shoot  │              │ discovers entity│             │ event-verified │
│ > grenade >    │              │ slots (enemy / │              │ anchors (bombs │
│ heal > loot >  │              │ bullet / item) │              │ -1 per grenade)│
│ advance        │              │ from behaviour │              │ + freeze tests │
└────────────────┘              └────────────────┘              └────────────────┘
        │                               ▲                               ▲
        └────────────── semantic scene ─┴─────── GameShark-grade seeds ─┘
                                       (agent/gsmap.py — read-only)
```

**The pipeline, end to end:**

| Stage | Module | What happens |
|---|---|---|
| Boot | `core/host.py` | ctypes libretro frontend: software XRGB8888 rendering, joypad injection, live RAM/VRAM numpy views, savestates |
| Enter | `api.py` `enter_gameplay3` | Adaptive menu navigation with a 64×48 thumbnail classifier + input-responsiveness gates; **control is proven** by trajectory divergence (3 input scripts from one savestate must produce different RAM futures — attract demos can't fake it) |
| Perceive | `agent/perception.py` | Finds the *dynamic* gameplay cluster each boot via event-verified anchors (bombs counter: exactly −1 per grenade, twice) and translates the whole hp/ammo/lives cluster by delta; every role carries an honest verification status |
| Model | `agent/worldmodel.py` | Discovers entity tables live from behaviour: words that move *without* input = enemies, fast movers = bullets, static-until-touched = items |
| Decide | `agent/policy.py` | Human-priority rule base: dodge bullets → shoot nearest → grenade clusters → eat health → loot → advance with hop cadence and tap-fire rhythm |
| Evidence | `agent/events.py` | Reason-coded event log: score changes / resets / wrap / suspicious jumps, kill candidates (ESTIMATED) vs verified kills, two-stage mission-clear detection |
| Progress | `agent/progress.py` | Camera/progress word accepted **only** after calibration tests pass; camera-lock distinguished from a true stall; unverified signals can never claim progress |
| Learn | `agent/discovery.py`, `memscan.py` | RetroArch-style read-only cheat finder + bidirectional probes build a per-game **profile** once, reused forever |
| Assist | `agent/gameshark.py` | Full PSX PAR/GS engine: parse `8x/3x/D0/A0`, apply per frame (hardware behaviour), **verify with event proofs**, revision-check published patches |
| Resume | `core/statemgr.py` | Savestates + JSONL journal → "continue from where you left off", even in a fresh process |

## v0.6 — the honesty audit (what the v0.5 evidence actually showed)

The v0.5 report (`download/ps1play_v4_mission1/mission1_report.json`) is preserved
as a fixture. Auditing it against its own telemetry exposed six real defects, all
fixed in v0.6 with regression tests:

| # | Defect in v0.5 | Root cause | v0.6 fix |
|---|---|---|---|
| 1 | `score_start == score_end == 200` while telemetry visited 96..252 | score sampled once per chunk with no reset/wrap handling; 18 continues reset the score silently | `agent/events.py` `ScoreTracker`: raw-bytes before/after per action interval, reason-coded RESET / WRAP / SUSPICIOUS; report validator rejects contradictory reports |
| 2 | "`kills_est = 27`" | every score delta ≥ 90 was counted as a kill | `KillClassifier`: score deltas produce **ESTIMATED** kill candidates; **VERIFIED** requires independent entity evidence. The two counts are never merged |
| 3 | camera word `0xCA2E2` used while `verified: false`; frozen at 58 for 250 chunks | no camera-lock vs stall separation | `agent/progress.py`: calibration must pass idle/right/left/monotonic tests; runtime monitor distinguishes PROGRESS / CAMERA_LOCKED / STALLED / RESET / WRAP / INVALID |
| 4 | telemetry `bombs` jumped 0→30 (grenades only decrement) | re-anchors after mission reloads latched onto wrong words | `PerceptionGuard.invalidate()` + `validate_anchor()`: after any reload the cluster is dropped, re-anchored, and plausibility-checked (in range 0..40, never rising) |
| 5 | mission byte change = "MISSION CLEAR" claim | the byte at `0x0D4213` is the *mission-unlock* bitmask (per published GS code `300D4213 00FF`), not a proven clear signal | `MissionClearDetector`: `mission_clear_detected` (byte change) ≠ `mission_clear_verified` (sustained + independent corroboration) |
| 6 | hardcoded absolute paths | config only editable in source | CLI args + env vars (`M1_GAME`, `M1_CORE`, `M1_WORKSPACE`, `M1_EVID`, `M1_CHUNKS`, `M1_RESUME`) with path validation before boot — original defaults preserved |

The report self-consistency validator (`agent/report_validate.py`) **fails on the
original v0.5 report** (that is a unit test) and the new runner refuses to write
a report that does not pass it.

## v0.7 — frame-scheduled policy + verified emulator smoke

A source-grounded re-inspection of the *active* Mission-1 execution path
(`run_mission1_legit.py` → `RobustLegitPolicy.decide()` → `execute()` →
`LibretroCore.run_frame()`) confirmed four more defects and fixed them
(`tests/test_policy_frames.py`, 14 new unit tests — all offline):

| # | Defect in v0.6 | Root cause | v0.7 fix |
|---|---|---|---|
| 1 | A chunk aligned with the grenade phase pressed **A on all 60 frames** (up to `bombs` grenades dumped in one chunk) | `fc` advanced once per chunk while `(fc % 300) == 30` / `(fc % 900) % 75 == 0` were evaluated inside the per-frame loop | global frame index advances per frame; scheduled actions are pure predicates over it → the button timeline is **invariant to chunk partitioning** (tested for sizes 1, 13, 30, 59, 60, 61, 120) |
| 2 | `decide()` accepted `timer`, `zone`, `churn` and never used them (dead ZONE mode) | signature grew without validation | signature reduced to `decide(chunk, stall_chunks, bombs, bombs_verified)`; the contract is unit-tested |
| 3 | `stall > 60` meant **3,660 frames** (stall counts chunks of 60), not 60 | unit ambiguity | units explicit: `stall_chunks` + named thresholds (`STALL_SHRED_AFTER_CHUNKS`, `STALL_PAUSE_AFTER_CHUNKS`); boundary tests pin the exact engagement point |
| 4 | a blocked walker with an **unverified** bombs counter had no recovery path at all (shred required verification) | bounded tactical behavior missing | deterministic UNSTICK window (30 f step-back LEFT + 13 f hop, every 900 f while stalled) — tested |
| 5 | report claimed `frames == chunks * 60` while keepalive/recovery probes ran ~95 extra frames every 3rd chunk | report-vs-telemetry disagreement | report now records `frames` (actual `p.t` delta), `frames_nominal` and `overhead_frames` separately |

New evidence artifact: `scripts/emulator_smoke.py` (EMULATOR_SMOKE tier) —
loads the real libretro core through the real ctypes host and extracts the
core's own embedded BIOS table. On the current dev sandbox it proves:
`Beetle PSX 0.9.44.1` loads and `retro_init()` runs, and **this core build only
accepts SCPH-55xx/7003 BIOS revisions** — an SCPH-1001 image is rejected by
design. The remaining blockers for a real run are exactly two files
(`env_probe.py` prints them): the disc image and `scph5501.bin`
(MD5 `490f666e1afb15b7362b406ed1cea246`).

> **v0.8 correction:** the string-derived claim above was superseded by
> executable boot tests. The gate is real (name+SHA1 region lists), but
> the consequence was misread: the core silently boots an embedded
> OpenBIOS instead of failing. See the v0.8 section for the executed
> decision table.

## v0.8 — the BIOS decision table, executed (replaces a string-derived claim)

v0.7 stated that this core build "only accepts SCPH-55xx/7003" based on
strings extracted from the binary. v0.8 replaced that inference with
**executable boot tests** (`scripts/bios_probe.py`) and found that the
claim was right about the gate but wrong about the consequence:

> **The core does not reject a foreign BIOS loudly — it silently falls
> back to an OpenBIOS image embedded in the core binary**
> (`libretro.c`: `firmware_is_present()` → `memcpy(BIOSROM, openbios, …)`).
> Every previous "booted" screenshot on this machine — the rotating
> cube — was the embedded **OpenBIOS shell**, not the supplied BIOS.

The decision table (all rows executed on this machine, evidence in
`scripts/bios_probe.py` JSON outputs):

| # | Configuration | Firmware actually used | Content | Verdict |
|---|---|---|---|---|
| 1 | no content (`retro_load_game(NULL)`) | — | — | unsupported by 0.9.44.1 (load fails) |
| 2 | `scph1001.bin` (MD5 `4dc4690a…`, authentic) | **embedded OpenBIOS fallback** | self-made audio disc | BIOS **not loaded**; boots anyway (the trap) |
| 3 | `scph7502.bin` (MD5 `30a25911…`, authentic) | embedded OpenBIOS fallback | self-made audio disc | same trap |
| 4 | `scph1001.bin` + `skip_bios=enabled` | embedded OpenBIOS fallback | audio disc | `skip_bios` is a boot-flow patch (BIOS+0x6990), not a firmware bypass |
| 5 | `openbios.bin` (MIT, `664ee444…`) + `override_bios=openbios` | **OpenBIOS via the OFFICIAL firmware path** (`Override firmware found` in log) | audio disc | PASS — lawful retail-BIOS-free boot |
| 6 | self-made pad-test disc (SYSTEM.CNF → PS-X EXE) | any | our own EXE | executable **dispatch not reached** (shell parses `SYSTEM.CNF;1` per its ROM strings, but no boot within 1800 frames) |
| 7 | direct `.EXE` content | — | our own EXE | `LoadEXE()` accepts it, but this build never patches PC/SP → the EXE never runs (TextMem is only mapped into the PIO window) |

What was built to make this decidable and repeatable:

* `scripts/bios_probe.py` — one BIOS × one content × one option set →
  BOOTED / LOADED_NO_RENDER / LOAD_FAILED verdict with hashes, core
  variables, log tail, screenshot, and the **fallback-vs-official
  firmware flag** (`firmware_fallback` / `firmware_override_found`).
* `third_party/openbios/openbios.bin` — the OpenBIOS image (MIT,
  © PCSX-Redux) byte-identical to the core's own embedded blob
  (MD5 `664ee444f38f6008d0cffc9d23e5c40d`), with `PROVENANCE.md`.
  With `beetle_psx_override_bios=openbios` this boots through the
  official firmware path — no proprietary BIOS required.
* `scripts/make_audio_fixture.py`, `scripts/make_padtest.py` — lawful,
  self-generated content: a silent-CDDA disc, and a hand-assembled
  MIPS pad-test EXE/disc (RIGHT→red, LEFT→blue, ✕→green, START→white).
* `scripts/input_causality.py` — the INPUT_CAUSALITY A/B harness
  (baseline vs treatment vs screenshot evidence). Host-side input is
  **proven correct** on this machine: per-frame `input_state` trace
  shows `port0/device1/id7 → 1` during holds (32 polls/frame), and
  savestate branches stay byte-identical when no input is scheduled
  (determinism). The remaining blocker is content-side only: the
  OpenBIOS shell does not consume pad input.
* `scripts/autolab.py` — the one-command gate ladder:
  `python3 scripts/autolab.py --goal gates --budget-minutes 10` runs
  UNIT → EMULATOR_SMOKE → BIOS_BOOT → CONTENT_BOOT → INPUT_CAUSALITY →
  TARGET_GAME, records every experiment to a resumable JSONL ledger
  with fingerprint dedup, and prints the single highest-value blocker.
* `env_probe.py` now classifies BIOS files against the core's real
  gate (`RETAIL_OK` / `OPENBIOS_OK` / `KNOWN_UNSUPPORTED` — flagging
  the silent-fallback trap for SCPH-1001/7502 by hash) and reports
  which firmware path the boot smoke actually took.
* Host fixes: `LibretroCore.load_game(None)` contentless attempts with
  core-log diagnostics; `PS1Play(..., var_overrides=…)` passthrough for
  core options.

**Remaining blockers, precisely:** (1) `scph5501.bin`
(MD5 `490f666e1afb15b7362b406ed1cea246`, SHA1 `0555c6fa…`) for retail
NTSC-U runs — the supplied SCPH-1001/7502 files cannot be loaded by
this core; (2) ~~the SLUS-01212 disc image~~ **solved in v0.11** — the
user supplied the disc; the file stays outside the repository
(copyright), only hashes and screenshots are kept.

## v0.11 — the real SLUS-01212 disc boots; control proven on the real game

v0.10's exe-direct path died on a SYSCALL because it skipped kernel
initialization. v0.11 closed the gap lawfully: the **user supplied the
disc image** and the OpenBIOS official firmware path boots it. The
boot flow is observed frame-accurately: BIOS cube → title loading →
Agetec "PRESS 1P OR 2P START" → mode menu (ARCADE MISSION / COMBAT
SCHOOL / ART GALLERY / OPTION) → `OK? YES` → SOLDIER SELECT →
**Mission 1 live gameplay** (arcade HUD, 1UP=2, mission timer counting).

Menu semantics were decoded **empirically with pixel checks**, not
guessed — including a negative result: the Agetec screen idle-times-out
into the attract replay, so a no-input control run is mandatory before
crediting any button with a transition. START enters the mode menu;
UP/DOWN move the highlight; circle opens and confirms the `OK?` dialog.

The decisive experiment (`scripts/real_input_causality_game.py`): one
save-state at f5600, three branches of 240 frames:

| Branch | Input | Result |
|---|---|---|
| A | none | Marco at the start signpost (control) |
| B | RIGHT held | Marco walks into the level, camera scrolls, two enemies engage; diff vs A = **22.60** |
| C | LEFT held | diff vs A = **1.29** — Mission 1 starts at the LEFT map boundary, so zero displacement is the expected physical response, not a failure |

B-vs-C = 22.57, and the numbers reproduce exactly across re-runs
(deterministic). **Controller → world causality is PROVEN (OBSERVED)
on the real SLUS-01212 game.** Mission clear is NOT claimed — that is
the next stage (real-frames audit of the v0.7 policy).

Evidence rendered by the real game on this machine
(`docs/evidence_v011/`):

| File | Screen |
|---|---|
| `title_interactive.png` | Agetec title — "PRESS 1P OR 2P START" |
| `mode_menu.png` | mode menu: ARCADE MISSION / COMBAT SCHOOL / TIME ATTACK / OPTION |
| `ok_dialog.png` | `OK? YES` confirmation dialog |
| `soldier_select.png` | SOLDIER SELECT (Marco / Eri / Tarma / Fio) |
| `mission1_start.png` | Mission 1 start, full HUD |
| `mission1_right_walk.png` | branch B: world changed after holding RIGHT |

Provenance note: two independent download sessions (different archives)
fetched byte-identical images — sha256 `45cde149…`, 104,315,904 bytes,
`SYSTEM.CNF` boot `SLUS_012.12;1`, license string `SLUS-01212`. The
identity evidence is therefore not tied to a single source file.

## Source-of-truth table (live status of every claim)

| Claim | Evidence today | Status |
|---|---|---|
| Core boots the disc + adaptive nav reaches Mission 1 | v0.4/v0.5 runs: gate `in_mission=true`, 45,000 frames played; **v0.11: the real SLUS-01212 disc boots on this machine and reaches Mission 1 gameplay via real inputs** | TESTED + v0.11 OBSERVED (this machine) |
| Injected inputs control the player | pad-mirror toggle + churn + self-play guard + trajectory divergence; **v0.11: START/UP/DOWN/circle/RIGHT proven causal on the real game (A/B/C save-state branches, deterministic)** | VERIFIED (this machine, real game) |
| Score word `0x0EE318` (u32 LE) | static RE (9 code xrefs) + live +100 increments | PARTIAL — width/encoding not yet cross-checked against the HUD |
| Kills | 33 score events incl. 19 × +100 observed | ESTIMATED only — never independently verified |
| Camera/progress `0xCA2E2` | v0.5 calibration failed monotonic check | UNVERIFIED — cannot support progress claims |
| Bombs anchor (dynamic cluster) | grenade −1 exactly, twice, per anchor | VERIFIED at anchor time; re-validated after every reload in v0.6 |
| Lives / timer translations | never observed non-null in a run | PENDING their own event tests |
| Mission byte `0x0D4213` | it is the unlock bitmask (published GS code) | CANDIDATE signal — clear requires corroboration |
| **Mission 1 cleared** | no run has produced a verified clear | **NOT ACHIEVED** |

## Static reverse engineering (`ps1play/re/`)

The game itself was treated as source code. `scripts/extract_exe.py` pulls the
PS-X EXE from the .bin, `static_re.py` disassembles it with capstone and builds a
2384+ entry xref map, `dump_asm.py` dumps the real functions (`re/asm_*.asm`):

- `SLUS_012.12`: 606 KB PS-X EXE @ `0x80010000`, entry `0x80082A44`
- **Pad array @ `0x800D4948`** (16 code xrefs) — the "are we in control" gate
- **Score P1 @ `0x800EE318`** (9 xrefs), **POW @ `0x80087A78`** (4 xrefs)
- The gameplay cluster (hp/ammo/bombs/lives/timer) is **dynamically placed** — it
  moves every boot and every mission reload, which is exactly why published
  GameShark addresses don't work on this dump; the internal layout matches them,
  so one event-verified anchor + a per-instance delta translates the cluster
- Runtime overlays (`ENEMY.BIN`, `MISSION.BIN`…) are extracted from the ISO and
  located verbatim in live RAM by pattern match

## Results so far (honest)

- **v0.5** (`download/ps1play_v4_mission1/`): 45,000 legit frames @ 113 fps,
  18 continues survived, boot → menu → Mission 1 fully headless. The audit above
  re-interprets its numbers: 33 score events (19 × +100) on the RE-verified score
  word — kill identity and distance claims from that report are ESTIMATED, not
  verified. Bot reliably reached the village section (screenshots; camera word
  unverified). 17 policy iterations root-caused 6 distinct blockers, all documented.
- **v0.6**: correctness revision — the six defects above fixed with 61 unit tests;
  no new live run yet (the current sandbox has no game image / BIOS / core —
  see *Run it* below for the deterministic environment check).
- **v0.7**: frame-scheduled policy (chunk-invariant timelines, explicit stall
  units, unstick recovery, honest frame accounting) + 75 unit tests green +
  first EMULATOR_SMOKE evidence on the current sandbox (core loads; accepted
  BIOS revisions extracted from the core binary itself). Live run still
  blocked on the two copyrighted artifacts.
- **v0.4** (GS-assist session): 27,000 frames @ 215 fps, 25 × +100 score events,
  Invincible + Infinite Bombs freeze codes re-anchored after every mission reload.

<p align="center">
  <img src="docs/death_analysis.gif" alt="death-detection evidence frames" width="360"><br>
  <sub>death-detection evidence: the agent senses death from RAM and recovers</sub>
</p>

- **v0.9**: the decisive BIOS experiment. The user-supplied retail BIOS files
  were proven **invalid** (executed under the core's real name-keyed lookup:
  CPU exception-loops at reset with zero RAM writes; MD5s match no Redump
  revision). In response, the whole evidence chain went **BIOS-free**: a
  hand-assembled MIPS pad-test EXE now boots directly (documented core patch),
  polls the pad through the real SIO hardware registers, and **controller →
  world causality is verified end-to-end** (none/RIGHT/LEFT/again = SW1
  0xFF/0xDF/0x7F/0xDF, repeats). Gate ladder: UNIT 98/98 · EMULATOR_SMOKE ·
  BIOS_BOOT · CONTENT_BOOT · INPUT_CAUSALITY all PASS; only TARGET_GAME
  (the SLUS-01212 disc image itself) remains user-supplied. 13 new unit
  tests pin the assembler, the EDC-correct ISO writer and the load-delay
  discipline.
- **v0.10**: the real game binary enters the evidence chain. The
  exe-direct boot patch is upgraded to **v2** (jump to the header ENTRY
  instead of the text base; SP initialized from the header; NOP-filled
  hazards) and a new `scripts/target_exe_probe.py` boots the
  repository's own `SLUS_012.12` main EXE — BIOS-free, disc-free,
  strictly observational. Result: **the real game dispatches** (stack
  use, 14 KB of low-RAM tables, 75 KB of text self-modification within
  60 frames) and then hits a precisely identified wall: **SYSCALL at
  0x800300A0** — the BIOS kernel service dispatcher is the next
  dependency, and the OpenBIOS BEV handler itself faults on the
  inherited registers. A new autolab gate `TARGET_EXE` records this as
  PARTIAL; gameplay is not claimed. Full ladder re-run on the pinned
  v2 core (`c0207b04…`): UNIT 98/98 · SMOKE · BIOS_BOOT · CONTENT_BOOT ·
  INPUT_CAUSALITY PASS; TARGET_GAME still needs the user-supplied
  SLUS-01212 image.

- **v0.11**: the user-supplied SLUS-01212 disc image joins the evidence
  chain, and the wall falls. Identity verified from the image bytes
  (`scripts/verify_msx_image.py`): PVD `PLAYSTATION`/`METALSLUGX`,
  `SYSTEM.CNF` → `BOOT = cdrom:\SLUS_012.12;1`, license string
  `SLUS-01212` (sha256 `45cde149…`). Booting the real disc through the
  OFFICIAL OpenBIOS override path makes the kernel services available,
  so the game runs FAR past the exe-direct SYSCALL wall:
  title-loading → Agetec "PRESS 1P OR 2P START" → mode menu (cursor
  moves pixel-verified with UP/DOWN) → `OK? YES` dialog → SOLDIER
  SELECT → Mission 1 live with a counting timer and the arcade HUD.
  The decisive experiment `scripts/real_input_causality_game.py` saves
  one state and branches A/B/C: **RIGHT walks Marco into the level
  (final-frame diff 22.60 vs no-input; two enemies engage), LEFT is a
  no-op because Mission 1 starts at the left map boundary, and the two
  held directions diverge by 22.57 — deterministic across re-runs.**
  Verdict: controller → world causality is PROVEN on the real game
  (OBSERVED). Mission clear is still not claimed; the autolab ladder
  now records `TARGET_GAME_SEGMENT` evidence for Mission 1 start.

## Run it

```bash
# 0) deterministic environment gate — prints exactly what is missing
python3 scripts/env_probe.py                       # exit 0 = ready, 2 = blocked

# 1) Level-A unit tests (synthetic RAM, no emulator needed) — ~1 s
python3 -m pytest tests/ -q

# 2) Level-B short integration test (~1-2 min when the environment is ready)
python3 scripts/test_integration_m1.py

# 3) the real Mission-1 run (legal inputs only)
python3 scripts/run_mission1_legit.py \
    --game "/path/to/Metal Slug X (USA).cue" \
    --core /path/to/mednafen_psx_libretro.so \
    --workspace /path/to/emu \
    --evidence-dir download/ps1play_v6_mission1 \
    --chunks 1000

# every flag has an env-var default: M1_GAME, M1_CORE, M1_WORKSPACE,
# M1_EVID, M1_CHUNKS, M1_RESUME — the original absolute defaults are kept.

# other tools
python3 scripts/run_semantic2.py                 # GS-assist semantic session
SEM_ASSIST=0 python3 scripts/run_semantic2.py    # same, assist disabled
python3 scripts/verify_gs_live3.py               # GameShark verification chain
python3 scripts/static_re.py                     # rebuild the xref/source map
python3 scripts/ps1play_demo.py                  # 35-second end-to-end demo
```

**Requirements** (not included — you must own them):

- Python 3.10+, numpy, Pillow, pytest
- Beetle PSX libretro core (`mednafen_psx_libretro.so`)
- SCPH-5501 BIOS (MD5 `490f666e…`) — Beetle rejects other revisions
- Your own `Metal Slug X (USA)` .cue/.bin (SLUS-01212)

The game image and BIOS are copyrighted and are **never committed** to this
repository; `env_probe.py` is the authoritative check for whether a machine
can run the real game.

## Repository layout

```
ps1play/               the framework
  core/                host (libretro ctypes), memory tools, savestates, input map
  agent/               perception, worldmodel, policy, events, progress, lifecycle,
                       report_validate, rewards, discovery, gameshark, memscan,
                       nav (thumb classifier), gsmap (published codes)
  plugins/             universal base + Metal Slug X plugin
  profiles/            learned per-game profile + nav reference thumbnails
  re/                  static RE artifacts (extracted EXE, overlays, asm dumps)
scripts/               runners, RE tooling, diagnostics, env gate, packaging
tests/                 Level-A unit tests (synthetic RAM, no emulator)
download/              evidence: mission-1 reports + gameplay/death frame captures
docs/                  demo GIFs, source-of-truth table
archive/               v0.3 source snapshot
worklog.md             full development diary (English) — every dead end included
```

## Honest limitations

- **Mission 1 is not cleared and no clear has ever been verified.** The policy
  still dies in the village bomber-chopper + soldier-truck section: every tactic
  wins in the savestate lab (`scripts/zone_lab.py`); sustaining them live is the
  next iteration.
- The score representation (u32 LE) still needs a controlled HUD cross-check;
  until then score-derived numbers are PARTIAL (the tracker labels them so).
- Entity-slot classification is heuristic; the static entity-table layout from
  `ENEMY.BIN` disassembly will make it exact.
- Action buttons (Y/A/B) map to a different pad word than the D-pad; locating it
  the same way (probe + disasm around `0x80015714`) is future work.

## Adding a new game

Implement one plugin class (boot script / features / policy) in `ps1play/plugins/`,
add a nav-refs folder if the menus need thumbnails, and let one discovery run build
the profile. Boot, memory tools, savestates, journaling and the agent loop are
universal.
