# Source of truth — PS1Play v0.8

Statuses: IMPLEMENTED, TESTED, OBSERVED, PARTIAL, BLOCKED, PENDING,
SUPERSEDED. Code existing in the repository is not automatically a
verified feature.

| Claim | Source file/function | Current evidence | Status | Next verification |
|---|---|---|---|---|
| Input reaches the actual player | `scripts/mission.py` `responsive()`; `api.py` `control_proof()` | pad-mirror toggle + world churn + self-play guard + trajectory divergence (3 input scripts from one savestate diverge) | VERIFIED (on the original machine, prior runs) | repeat via Level-B gate on any new machine |
| Boot + adaptive nav reaches Mission 1 | `api.py` `enter_gameplay3()` | v0.4/v0.5 runs: gate `in_mission=true`, 45,000 frames played | TESTED | Level-B integration run |
| Score address `0x0EE318`, u32 LE | `ps1play/re/` static RE (9 code xrefs); profile `gsmap.score` | live +100 increments observed in v0.4/v0.5; width/encoding never cross-checked against the HUD | PARTIAL | controlled HUD-vs-RAM correlation (fire one enemy, read HUD, compare bytes) |
| Score resets on continue | v0.5 report: 18 continues with score excursions | telemetry 96..252 vs endpoints 200/200 | OBSERVED (indirect) | watch score across an actual continue |
| Kills | `events.py` `KillClassifier` | 33 score events incl. 19 × +100 — these are SCORE events | ESTIMATED only | independent entity-slot death evidence |
| Camera/progress `0xCA2E2` | `run_mission1_legit.py` `find_progress_addr()` | v0.5 calibration: `verified=false`; frozen at 58 for 250 chunks; 48 resets | SUPERSEDED by `progress.py` contract | re-calibrate; word is unusable until tests pass |
| Bombs anchor (dynamic cluster) | `perception.py` `anchor()` | grenade −1 exactly, twice, at anchor time; v0.5 re-anchors latched wrong words (bombs 0→30) | VERIFIED at anchor time + v0.6 re-validation (range + never-rising) after every reload | keep monitoring across many reloads |
| Lives translation | `run_mission1_legit.py` `validate_lives()` | plausible value only; telemetry `lives=null` all run | PENDING | death event (−1) test |
| Timer translation | `validate_timer()` | telemetry `timer=null` all run (1 Hz test never passed) | PENDING | 1 Hz decay test during real play |
| Mission byte `0x0D4213` = clear signal | v0.5 used any byte change as CLEAR | published GS code `300D4213 00FF` says this is the mission-UNLOCK bitmask, not a state byte | CANDIDATE | observe the byte across title/menu/play/death/continue/boss/clear |
| Player HP | `perception.py` `find_player_hp()` | freeze-verified in v0.4 sessions (address moves per reload) | TESTED (calibration-only, uses writes) | re-derive per boot in legit runs |
| Mission 1 cleared | — | no verified clear in any run | NOT ACHIEVED | — |

## External-reference evidence table (mission review §8)

| Reference | Exact reusable item | Applicable to PS1Play? | Validation performed | Decision |
|---|---|---|---|---|
| BizHawk (TASEmulators/BizHawk) | savestate-based controlled trials; memory-domain discipline; input playback | Potentially | design only — same trial pattern implemented with our own savestates | Approach reused; runtime NOT replaced |
| Metal Slug 6 agent (Wilbertbh-Tan/metalslug6_agent) | reward-component separation + experiment logging methodology | Partially | our `agent/rewards.py` logs separate components, gated by verified sensors | Methodology adapted; formulas NOT copied (different game/emulator) |
| HotMolts posts | research leads (curiosity, pause usage) | Unverified | public code unavailable | Do not treat as proven |
| TASVideos (9399M, 8813M) | legal input sequences / timing | Depends on exact game version | TAS versions/platform not confirmed to match PSX SLUS-01212 | Reject for RAM addresses; inputs only after version check |
| gamehacking.org /game/89284 | published GS code table for SLUS-01212 | Yes, as seeds | addresses verified live (static cluster) or re-derived per boot (dynamic cluster) | Reused as watch-list seeds, never blindly trusted |

## v0.7 additions (frame-scheduled policy + emulator smoke)

| Claim | Source file/function | Current evidence | Status | Next verification |
|---|---|---|---|---|
| Policy button timeline is chunk-invariant | `run_mission1_legit.py` `RobustLegitPolicy` (v0.7) | 14 unit tests incl. identical timelines for chunk sizes 1/13/30/59/60/61/120 (`tests/test_policy_frames.py`) | TESTED (UNIT) | EMULATOR_SMOKE + REAL_GAME_SEGMENT once content is present |
| Grenade presses are frame-exact (4-frame window, 1 per 300 f) | v0.7 scheduler | poison-chunk test: aligned chunk yields 1 press, v0.6 emitted 60 A-frames | TESTED (UNIT) | live grenade-count vs bombs counter delta |
| stall thresholds are chunk-denominated and named | `STALL_SHRED_AFTER_CHUNKS`, `STALL_PAUSE_AFTER_CHUNKS` | boundary tests: no shred at 60, shred at 61 chunks | TESTED (UNIT) | tune only from measured live stall data |
| Beetle PSX 0.9.44.1 loads on the current sandbox | `core/host.py` + `scripts/emulator_smoke.py` | EMULATOR_SMOKE PASS: retro_init ok, env wiring ok, embedded BIOS table = SCPH-55xx/7003 only | OBSERVED (this machine) | load_game with real cue + scph5501 |
| SCPH-1001/7502 BIOS cannot boot this core | core binary's own embedded BIOS names | `strings` + emulator_smoke: no 1001/7502 in the accepted set | SUPERSEDED by v0.8 executable tests | obtain scph5501.bin (MD5 490f666e…) |

## v0.8 additions (executed BIOS decision table + autolab)

| Claim | Source file/function | Current evidence | Status | Next verification |
|---|---|---|---|---|
| The core SILENTLY falls back to an embedded OpenBIOS when the region-listed firmware is absent | `libretro.c` (beetle-psx @ df2b53b) `firmware_is_present()` → `memcpy(BIOSROM, openbios, …)`; runtime log `Firmware is missing: %s` | `scripts/bios_probe.py` rows 2–4: SCPH-1001/7502 (authentic MD5s) boot to the OpenBIOS cube with `firmware_fallback=true` | VERIFIED (this machine) | retail runs must pin `firmware_override_found/fallback=false/…` |
| SCPH-1001/7502 are rejected by name+SHA1 region gate, not by hash crash | `libretro.c` `firmware_is_present()` (NTSC-U list: scph5501/5503/7003, SHA1 `0555C6FA…`) | source inspection + executed boot tests | VERIFIED | — |
| OpenBIOS boots via the OFFICIAL firmware path, retail-BIOS-free | `third_party/openbios/openbios.bin` (MIT, © PCSX-Redux; MD5 `664ee444…` byte-identical to the core's embedded blob) + `beetle_psx_override_bios=openbios` | bios_probe: `override_found=true`, BOOTED, real frames | TESTED | use for lawful CONTENT_BOOT-style gates |
| The OpenBIOS shell cannot host INPUT_CAUSALITY | OpenBIOS ROM strings (`SYSTEM.CNF;1`, `No boot file !`) + `scripts/input_causality.py` A/B + `scripts/frame_scan.py` | 1800-frame scan: no pad response, no exe flash; input diffs exactly 0 | OBSERVED | needs pad-interactive content (retail BIOS + game) |
| The host input path is correct on this machine | `core/host.py` `input_state` callback | per-frame trace: `port0/device1/id7 → 1` during holds, 32 polls/frame; savestate branches byte-identical without input | VERIFIED (host side) | end-to-end causality awaits interactive content |
| Lawful content fixtures exist and load through the real path | `scripts/make_audio_fixture.py`, `scripts/make_padtest.py` | audio disc + hand-assembled MIPS pad-test EXE/disc; CONTENT_BOOT = PARTIAL (mount + TOC + shell render; exe dispatch not reached) | PARTIAL | fix exe dispatch or obtain retail BIOS + game |
| One command runs the whole gate ladder unattended | `scripts/autolab.py` | executed: UNIT PASS / EMULATOR_SMOKE PASS / BIOS_BOOT PASS / CONTENT_BOOT PARTIAL / INPUT_CAUSALITY BLOCKED / TARGET_GAME BLOCKED; JSONL ledger + fingerprint dedup (10 tests in `tests/test_bios_truth.py`) | TESTED | run with real artifacts when supplied |
| Precise remaining blockers | `scripts/env_probe.py` | (1) scph5501.bin MD5 `490f666e…` for retail NTSC-U; (2) SLUS-01212 image (download geo-gated, HTML block page) | BLOCKED | user-supplied local files (never committed) |
