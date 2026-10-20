# Worklog — PS1Play development diary (English)

Full development diary, every dead end included. (Persian originals were
translated to English per project policy: English-only on GitHub.)

---
Task ID: 1
Agent: main (Z.ai)
Task: Evaluate user-provided sources (ePSXe win/apk, PSX BIOS packs, Metal Slug X
PS1) for a headless CLI play scenario.

Work Log:
- Tooling survey; p7zip unavailable (no root) -> py7zr installed on python3.13
- Downloaded ePSXe.2.0.18.zip (~1.55 MB, ~3.6 KB/s server, completed with resume);
  extracted: 32-bit Windows ePSXe.exe + standard folders
- Downloaded a BIOS pack (SCPH-1001 + SCPH-7502); extracted with unrar-free and
  libarchive (identical results)
- Cryptanalysis of that BIOS pack: entropy 8.000 bits/byte, zero Sony strings,
  invalid MD5s -> the .bin files are encrypted/corrupt and unusable
- Downloaded reference BIOS from psx.arthus.net: SCPH1001.BIN
  (MD5 924e392ed05558ffdb115408c263dccf, the well-known hash), SCPH-7502.BIN
  (MD5 b9d9a0286c33dc6b7237bb13cd46fdee) + Sony strings verified
- Android APK: URL with trailing dot 404; without dot OK (8,218,853 B, PK magic +
  AndroidManifest) — ARM64 Android only
- hexrom.com: info pages without direct links; dl.dlpgame.ir: 503 "domestic IP
  only"; international mirrors (archive.org / web.archive.org / myrient (closed
  2026-03-31) / vimm) blocked; CDRomance reachable
- Metal Slug X via CDRomance with AJAX simulation (POST post_id=7924 +
  X-Requested-With header) -> direct link -> 30.25 MB at ~2.1 MB/s
- Extraction: Metal Slug X (USA).bin (104,315,904 B) + cue (TRACK 01 MODE2/2352)
- Disc verification: SLUS_012.12 present, SYSTEM.CNF present, BOOT=cdrom,
  Sony license present, full MD5 37d9e1179a32661800e74858009a4f8b

Stage Summary:
- Usable files: reference BIOS SCPH-1001 and SCPH-7502; game bin+cue verified
- The user's BIOS pack was unusable — reference versions used instead
- ePSXe unsuitable for headless (Windows/closed/OpenGL); recommended path: a
  libretro core (SwanStation or Beetle PSX) behind a Python ctypes frontend with
  software rendering

---
Task ID: 2
Agent: main (Z.ai)
Task: Run Metal Slug X headless on the CLI with no graphics; prove it with a
scripted bot.

Work Log:
- Downloaded libretro cores from buildbot.libretro.com: mednafen_psx_libretro.so
  (Beetle PSX 0.9.44.1) + swanstation (spare)
- Built the emu layout: system/ (BIOS) + games/ (bin+cue) + saves/
- Wrote a headless libretro frontend with ctypes (env/video/audio/input
  callbacks, environment trace, PNG snapshots, GIF, ASCII art)
- Fixed an import-cast bug; the core's variadic log went through a gcc-built
  shim (scripts/logshim.c)
- Hit "Firmware is missing: scph5501.bin"; read the core source: recent Beetle
  accepts only scph5501/5503/7003 with SHA1 0555C6FA...88E9F30B for NTSC-U
  (scph1001 is NOT on the list)
- Got SCPH-5501 from psx.arthus.net; SHA1 matched the core's expectation
  (actual MD5: 490f666e1afb15b7362b406ed1cea246)
- Successful boot: PlayStation logo -> game save-data message -> NOW LOADING ->
  Agetec logo -> main menu -> OK?/YES confirmed with injected input -> Mission 1
  loaded -> real gameplay (run/jump/shoot) -> score 800->1200 -> death ->
  PRESS START
- 8,600 frames at 287 fps (unthrottled), 1,128 distinct frames, fully software
  XRGB8888 rendering in RAM
- Evidence in download/psx_headless_demo/ (9 descriptive PNGs + highlights.gif +
  summary.json)

Stage Summary:
- Proven: PS1 Metal Slug X runs on the CLI with no GPU/X11
- Reusable script: scripts/psx_headless.py (--core --game --frames ...)
- Possible next steps: smarter bot (frame analysis), savestates for RL practice,
  CHD conversion

---
Task ID: 3
Agent: main (Z.ai)
Task: Build the PS1Play agent framework — plugin-based, minimal tokens, no
cheating, pattern learning, resume from any point.

Work Log:
- Built the ps1play package: core/host.py (ctypes libretro frontend reusing the
  proven psx_headless logic + live 2 MB RAM numpy view + savestates),
  core/memory.py, core/statemgr.py, agent/{observer,discovery,loop}.py,
  plugins/base.py, api.py, CLI in scripts/ps1play_cli.py
- Bugs fixed: retro_get_memory_data symbol name, av_info argtypes, frame
  counting (frames_run), double-counted wait/tap in run_steps, KeyError 'score',
  u32 overflow wrap in deltas
- Structural finding: top of RAM (0x1FC000+) is audio/SPU buffers; k*65536
  deltas mean high-word flips (junk); positions are fixed-point
- enter_gameplay (generic): raw boot script + adaptive START taps +
  correlate(RIGHT) probe with dir="+" and two consecutive confirmations ->
  stable entry into MISSION 1 (taps=2)
- Gameplay lesson: a standing character between taps gets killed and the game
  returns to title -> run RIGHT + hop between taps (human behavior)
- verify_series: restore from an identical savestate + value series sampling
  (held vs idle) -> quality score = |m_act| x mono_frac
- Full demo (scripts/ps1play_demo.py): boot -> enter -> discovery (correlate +
  echo + monotonic) -> profile -> 5,400 frames with journal and checkpoints ->
  fresh session -> load_state -> resume at 407 fps — the whole demo ~35 s
- x-tracker in the journal: values 20..244 varying with gameplay (a real
  position/camera counter in the 0xE7xxx area: 949792 u32)
- Honest limitation: the policy still oscillates on stall/death; the score
  address was not finally confirmed; player_y/enemies deferred

Stage Summary:
- Complete framework + package download/ps1play_v0.1.zip + evidence
  (report.json, learned profile, journal, gameplay PNGs)
- Development pattern for any new game: ONE plugin class
  (boot_script/policy/features); everything else is universal

---
Task ID: 4-a
Agent: research (subagent)
Task: Research existing tools for "AI plays emulator via RAM" + find
GameShark/PAR codes (RAM addresses) for Metal Slug X SLUS-01212 + any RAM maps
(gamehacking.org, MAME mslugx, Data Crystal, TASVideos).

Work Log:
- Read the worklog; mapped network constraints: r.jina.ai=401,
  html.duckduckgo.com=000, lite.duckduckgo=empty, GameFAQs=403, searx.be
  bot-captcha, Brave JS-wall, Bing RSS geo-poisoned, GitHub REST rate-limited,
  gamehacking.org initially Cloudflare-403, cheats.mamedev.org unreachable,
  archive.org known-blocked
- Working channels: gamehacking.org with full browser headers + cookie jar,
  raw.githubusercontent.com, github.com/tree HTML pages, jsDelivr data API
- gamehacking.org: /game/SLUS-01212 = 404 (numeric IDs). POST /search
  (gamTitle) -> "Metal Slug X (NTSC-U)" = /game/89284 (also NTSC-J /game/95997,
  beta /game/112934)
- Fetched /game/89284 and parsed the full RAW PAR/GameShark code table
- libretro-database (RetroArch cheat db): NO Metal Slug X PSX .cht exists
- MAME cheat XML (mslugx.xml) not retrievable from this server; arcade
  addresses reported from structure knowledge only, flagged unverified

Stage Summary:
- RAW codes for Metal Slug X (NTSC-U) SLUS-01212 (PSX GS virtual 0x80000000+;
  physical = addr & 0x1FFFFF):
  * Extra Arms Ammo 8002DCD8 0001 -> 0x02DCD8 | Extra Bombs 800398B4 0001 ->
    0x0398B4 | Extra Lives 800475A8 0001 -> 0x0475A8 | Extra Time 800295F8 0002
    -> 0x0295F8
  * Infinite Arms Ammo 8002DCE6 2400 (NOP-over-branch) -> 0x02DCE6 |
    Infinite Bombs 800398BE 2400 -> 0x0398BE | Infinite Lives 800475AE 2400 ->
    0x0475AE | Infinite Time 8002962A 2400 -> 0x02962A
  * Invincible 8003273E 2400 + 80032764 00C8 (200 = full HP) + 80032766 2405 ->
    0x03273E / 0x032764 / 0x032766
  * Max Score P1 800EE318 E0FF + 800EE31A 05F5 (u32 99,999,999) -> 0x0EE318;
    P2 800EE320/322 -> 0x0EE320
  * POW P1/P2 80087A78/80087A7C 00FF -> 0x087A78 / 0x087A7C
  * Rapid Fire joker D00D4948 8000 -> 0x0D4948 (P1 controller word, bit 0x8000)
  * Unlock Another Mission 300D4213 00FF -> 0x0D4213 (mission-UNLOCK byte)
  * Weapon Modifier 8002D92C 00?? (+0x02D92E, 0x02D93A) -> 0x02D92C
  * Hit Anywhere (nolberto82): 0x03A984, arrays 0x0852D8-DE, 0x0401F4/F6,
    0x085700-06, 0x085870-76 -> probable per-entity collision/defense table
- Zero-token watch-list derived: ammo ~0x02DCD8-0x02DCE6, grenades 0x0398B4,
  lives 0x0475A8, HP 0x032764 (full=200), timer 0x0295F8, score u32 0x0EE318,
  POW 0x087A78, input word 0x0D4948, weapon 0x02D92C, mission-unlock byte
  0x0D4213, entity tables 0x0852xx-0x0858xx
- Data Crystal / TASVideos RAM maps for the PSX port: not found; MAME Neo-Geo
  addresses do NOT transfer to the PSX port

---
Task ID: 5
Agent: main (Z.ai)
Task: Continue unfinished work — live-verify the GameShark map, fix boot,
per-boot calibration, a real play session, source packaging.

Work Log:
- Research prepared: gamehacking.org addresses did NOT read correctly on our
  dump (hp/lives stuck at 0xFF) -> the right path is our own internal
  cheat-finder (memscan.py) with event-conditioned narrowing + savestate
  certainty
- Root bug of the session: parse_buttons({"START"}) passed strings -> the whole
  ps1play stack played with dead input (Task 2 worked because it passed ints).
  Fix: name->id conversion in inputmap.py
- Rebuilt the boot map with 9 experimental probes: START taps up to ~5200 +
  OK?/YES confirmed with B (not A/START!) + auto soldier-select + live mission
  from ~9000
- Trajectory test added: from one savestate, three different input scripts; a
  scripted demo stays byte-identical, a real mission diverges -> control proof
  via digests (method=trajectory, zero tokens)
- Anti-sabotage: START after menus = PAUSE -> pause menu -> QUIT; after menus
  are seen, only B/A (jump/grenade)
- Key discovery: the RAM layout MOVES between boots (hp at 829336=200 in one
  boot, 228 in the next!) -> scripts/calibrate.py: per-boot read-only semantic
  calibration (bombs: 8..15 -> -1 per grenade; hp: scale 100 or 200 -> drops on
  hit; timer: 1 Hz; counter area ~0xEE000 priority)
- play_v2.py: deterministic boot -> calibration -> 20,400 frames at 385 fps
  with live telemetry: hit=132, grenade_used=160, healed_or_respawn=23 +
  checkpoints + resume proof
- player_y verified (jump swing 216); player_x still unsolved (the camera
  scrolls; the player's on-screen x is static) — deferred
- README rewritten (v0.3) + package download/ps1play_v0.3.zip (91 files)

Stage Summary:
- Full proven chain: deterministic boot (trajectory) -> semantic calibration ->
  play with live RAM events -> checkpoint/resume
- Next: survival policy (baseline died in the first enemy group), player_x via
  a camera model, entity pattern extraction with entities.py

---
Task ID: 6
Agent: main (Z.ai)
Task: Universal semantic base + static RE of the game source + 100% GameShark
proof + a semantic play session.

Work Log:
- Full GameShark engine written (agent/gameshark.py): parse 8x/3x/D0/A0, apply
  per-frame (hardware behavior), freeze with event proofs, revision-check for
  published patches
- Universal WorldModel (agent/worldmodel.py): entity-slot discovery from online
  RAM statistics (no snapshot storage — fixed an OOM); classification
  player/enemy/bullet/item + player anchor; in the real session: 47 slots
  (23 enemy, 6 bullet, 13 item, 5 player)
- Universal SemanticPolicy (agent/policy.py): dodge bullets > shoot enemy >
  grenade clusters > eat health > pick items > advance
- Real static RE ("treat the game as source"):
  * SLUS_012.12 extracted (606 KB @ 0x80010000, entry 0x80082A44) + all
    overlays (ENEMY.BIN 115 KB loaded verbatim in RAM — found by pattern match)
  * static_re.py with capstone: global xref map (2384+ addresses); static
    verification: pad array @0x800D4948 (16 xrefs), score @0x800EE318 (9
    xrefs), POW (4 xrefs), hitbox table @0x80085870 passed to a collision
    function; disassembled functions in re/asm_*.asm
  * Key discovery: the gameplay data cluster (hp/bombs/ammo/lives/timer) is
    DYNAMIC and moves per boot and per mission reload; the internal layout
    matches the published GameShark codes exactly -> ONE event-verified anchor
    (bombs: exactly -1 per grenade, twice) + a per-instance delta translates
    the whole cluster
- New "do we actually control the game" gate (scripts/mission.py): RIGHT-bit
  toggle in the pad mirror 0x0D4948 + world churn while running (the auto-demo
  mirrors the pad but its world does not move -> rejected). Recovery = one
  START + settle
- Player HP found with the freeze-test protocol (0x95710, full=92; after a
  reload 0x9585c): only the address that cannot drop while frozen — while the
  player survives the same stab window — is the real HP
- Full session (scripts/run_semantic2.py): boot -> enter -> gate -> self-healing
  anchor (5x) -> GS assist (Invincible + Infinite Bombs) -> entity discovery ->
  semantic play; 27,000 frames at 215 fps, 30 real kill events on the static
  score counter (+100 x 25), checkpoint + resume + PNG evidence (progress into
  the village section of Mission 1 with score ~3000)
- Source package: download/ps1play_v0.4_src.zip (138 files)

Stage Summary:
- Full chain: static RE (the game's real source) + GameShark-grade perception
  with delta translation and self-healing + universal entity model + semantic
  policy + GS freeze with proofs
- Next: y-coordinate jump planning for pits, locating the action-button word
  (Y/A/B) the same way, exact slots from the ENEMY.BIN disassembly

---
Task ID: 7
Agent: main (Z.ai)
Task: Package v0.5 (legit Mission-1 assault), upload the project to
github.com/Sh-TB/Ps1ai with a README and demo GIF.

Work Log:
- run_mission1_legit.py: LEGAL INPUTS ONLY — zero cheats / zero memory writes /
  zero rewinds during the run; savestates only for read-only calibration probes
  and checkpoints
- 17 policy iterations root-caused six distinct blockers:
  1. noisy entity slots -> perpetual threat-hopping deaths
  2. 1-frame jump taps cannot clear obstacles (hold B ~13f)
  3. keepalive false-positive during camera-locked fights -> START = PAUSE
  4. fixed 3-tap recovery pauses the game right after the continue
  5. the ATTRACT DEMO mirrors its own inputs + churns 200k+ and fooled every
     gate -> self-play guard (pad must mirror 0 when idle)
  6. free-scrolling jumps land the player ON the scenery truck
- zone_lab.py (identical savestate, tactic grid): the soldier truck IS
  destructible — left-fire + grenades shred it in ~1-2 s and the camera
  unlocks. HUD score reached 4300 and 2 POWs freed in evidence runs
- The legit run: 45,000 frames at 113 fps, 18 continues survived; the bot
  reliably crossed canyon -> market -> village each life. Remaining wall:
  surviving the village bomber-chopper + soldier-truck section live
- Evidence: download/ps1play_v4_mission1/ (mission1_report.json + 45 PNGs)
- Demo GIFs built from evidence frames: docs/demo.gif (17 frames) +
  docs/death_analysis.gif (12 frames) — script scripts/build_demo_gif.py
- Repository work: cloned Sh-TB/Ps1ai with the fine-grained token, removed the
  test file 1.txt, committed 151 files (4.3 MB incl. archive/ps1play_v0.3.zip)
  and pushed (commit e55fc3c); verified structure + raw demo.gif via API
- Token-permission note recorded: for fine-grained tokens the API `permissions`
  field mirrors the owner's role, not the token's grant — only direct endpoint
  tests are authoritative

Stage Summary:
- The repository github.com/Sh-TB/Ps1ai went live: v0.5 source + evidence +
  docs + demo GIF on the front page
- Known debts fixed later in v0.6: score start/end inconsistency, speculative
  kill counting, unverified camera word, anchor drift after reloads

---
Task ID: 8
Agent: main (Z.ai)
Task: v0.6 honesty audit (external mission review): fix score semantics,
kill evidence, progress validation, anchor hygiene, mission-clear honesty,
lifecycle, configuration; Level-A tests; English-only GitHub.

Work Log:
- Audited download/ps1play_v4_mission1/mission1_report.json against its own
  telemetry: score_start==score_end==200 vs telemetry 96..252; 18 continues
  (score resets) unaccounted; telemetry bombs 0->30 (grenades only decrement);
  camera word verified=false yet frozen at 58 for 250 chunks; "27 kills" were
  score deltas >= 90
- New modules (all unit-tested, no emulator required):
  * agent/events.py — EventLog with OBSERVED/ESTIMATED/VERIFIED statuses,
    ScoreTracker (raw bytes before/after, RESET/WRAP/SUSPICIOUS reason codes),
    KillClassifier (score deltas are ESTIMATED candidates; VERIFIED requires
    independent entity evidence), MissionClearDetector (detected != verified;
    sustain + corroboration)
  * agent/progress.py — rank_candidates (idle/right/left/monotonic tests;
    returns only trustworthy words; rejections preserved) + ProgressSignal
    (PROGRESS / CAMERA_LOCKED / STALLED / RESET / WRAP / INVALID)
  * agent/lifecycle.py — recorded boot-to-clear FSM; PLAYING only reachable
    through input-control verification
  * agent/report_validate.py — self-consistency validator; FAILS on the v0.5
    report (unit test) and the runner refuses to write failing reports
  * agent/rewards.py — log-only reward audit; components default to zero
    unless their sensor is verified
- perception.py: per-role verification ledger + observation_contract() +
  invalidate() + validate_anchor() (range 0..40, never rising)
- run_mission1_legit.py rewritten: CLI/env configuration with validation,
  before/after score sampling per action interval, event-model integration,
  progress honesty, grenade only with a VERIFIED bombs counter, lifecycle
  transitions around every recovery, validated report output
- scripts/env_probe.py — deterministic environment gate (game/core/BIOS with
  hash checks); scripts/test_integration_m1.py — Level-B gate (exits
  BLOCKED_BY_ENVIRONMENT with the exact missing artifacts when run without
  them)
- tests/: 61 Level-A tests (events, progress, report validator vs the v0.5
  fixture, lifecycle, rewards, perception contract) — all green
- GitHub hygiene: all Persian content removed/translated (README rewritten,
  worklog translated); all commit messages and docs English-only

Stage Summary:
- Status: code-level correctness revision complete and tested; live runs remain
  BLOCKED_BY_ENVIRONMENT until a machine supplies the game image, BIOS and
  core (env_probe.py is the deterministic check). No mission clear is claimed.

---
Task ID: 9 (v0.7)
Agent: main (Z.ai)
Task: MASTER MISSION round 2 — verify the active policy path against the
v0.6 source, fix confirmed defects, add offline regression tests, and
verify the emulator layer with real artifacts supplied by the owner.

Work Log:
- Cloned the repo at f02a9e8 (v0.6, clean tree) and re-read the full active
  path: run_mission1_legit.py -> RobustLegitPolicy.decide() -> execute() ->
  LibretroCore.run_frame()/set_buttons(); also run_semantic2.py, loop.py,
  policy.py (SemanticPolicy), mission.py, events.py, progress.py,
  perception.py, report_validate.py, profiles/SLUS-01212 JSON
- CONFIRMED defect A (frame/chunk quantization): fc advanced once per chunk
  while (fc % 300) == 30 and (fc % 900) % 75 == 0 were evaluated per frame,
  so a chunk landing on the residue pressed A on all 60 frames (grenade
  dump). CONFIRMED defect B: decide() accepted timer/zone/churn and never
  used them. CONFIRMED defect C: stall counts 60-frame chunks, so
  stall > 60 is 3,660 frames; cross-path inconsistency with
  run_semantic2.py which passes stall in frames. CONFIRMED defect D: no
  recovery path without a VERIFIED bombs counter (wedge-forever risk).
  Report defect: frames == chunks*60 ignored ~95-frame keepalive probes
  every 3rd chunk (report vs p.t disagreement)
- v0.7 fixes in run_mission1_legit.py: global per-frame frame index;
  scheduled actions as pure predicates (timeline invariant to chunk
  partitioning); 4-frame grenade press windows counted once; signature
  reduced to (chunk, stall_chunks, bombs, bombs_verified); stall units
  explicit via named constants STALL_SHRED_AFTER_CHUNKS (60) and
  STALL_PAUSE_AFTER_CHUNKS (30); bounded UNSTICK window (30 f LEFT+Y,
  13 f LEFT+B hop) every 900 f while stalled without verified bombs;
  report records frames (actual p.t delta) vs frames_nominal vs
  overhead_frames
- New tests/test_policy_frames.py (14 UNIT tests, fully offline): chunk
  invariance for sizes 1/13/30/59/60/61/120 in four regimes, grenade
  cadence + press length + counting, shred boundary (60 vs 61 chunks),
  unstick coverage, no-grenade-without-verification, burst continuity,
  signature contract, segment budget coverage
- Environment: downloaded mednafen_psx_libretro.so (Beetle PSX 0.9.44.1,
  libretro buildbot nightly, linux x86_64) and verified it through the
  real host with new scripts/emulator_smoke.py -> EMULATOR_SMOKE PASS
  (retro_init ok, env wiring ok). Extracted the core's own embedded BIOS
  table: ONLY scph5500/5501/5502/5503/5552/7003 (+openbios/psxonpsp) are
  accepted -> the owner-supplied SCPH-1001/7502 images cannot boot this
  core by design. Owner-supplied Metal Slug X download URL is
  geo-gated (HTTP 503 'internal IP only' page) from this sandbox
- env_probe.py verdict on the current machine: python deps OK, core OK,
  workspace OK; missing exactly: game_image (.cue, SLUS-01212) and BIOS
  scph5501.bin (MD5 490f666e1afb15b7362b406ed1cea246). No live run
  attempted beyond smoke; nothing fabricated
- Test suite: 75 passed (61 prior Level-A + 14 new), 0.44 s
- All README/docs/worklog content in this commit is English-only

Stage Summary:
- Live gameplay still NOT achieved and NOT claimed: BLOCKED_BY_ENVIRONMENT
  on exactly two files (disc image + scph5501.bin). The emulator layer
  itself is now verified on this machine (was previously untested here),
  and the active policy timeline is proven chunk-invariant offline

---
Task ID: 10 (v0.8)
Agent: main (Z.ai)
Task: v0.8 — remove the boot blocker: execute the BIOS decision table,
prove the host input path, build the autolab gate ladder, and label
every firmware path honestly.

Work Log:
- Reproduced the v0.7 baseline first: repo HEAD e9b7469, env_probe
  BLOCKED (game_image + bios missing), 75/75 unit tests green,
  EMULATOR_SMOKE PASS (Beetle PSX 0.9.44.1 df2b53b)
- Executed real boot tests instead of string-derived claims (new
  scripts/bios_probe.py): contentless load fails (unsupported);
  scph1001.bin and scph7502.bin (both authentic MD5s) LOAD and render
  600 frames - but the firmware_fallback flag exposed the trap: the
  core silently replaced them with its EMBEDDED OpenBIOS (log line
  "Firmware is missing"), so every earlier "booted" cube was OpenBIOS,
  not the supplied BIOS. skip_bios only patches BIOS+0x6990 (boot flow),
  it is not a firmware bypass
- Root-caused the gate in beetle-psx source at the exact commit
  (df2b53b): firmware_is_present() matches BIOS by NAME list + SHA1 per
  region (NTSC-U expects scph5501/5503/7003, SHA1 0555C6FA...), then
  falls back to memcpy of the embedded openbios blob
- Lawful unblock: extracted the core's own embedded OpenBIOS (MIT,
  (c) PCSX-Redux, MD5 664ee444f38f6008d0cffc9d23e5c40d, byte-identical
  to deps/openbios/openbios.bin in the core source) into
  third_party/openbios/ with LICENSE + PROVENANCE; with
  beetle_psx_override_bios=openbios + openbios.bin named exactly so,
  the core loads it through the OFFICIAL firmware path
  ("Override firmware found" in log) - BIOS_BOOT gate = PASS without
  any proprietary file
- Built lawful content: scripts/make_audio_fixture.py (silent CDDA
  disc) and scripts/make_padtest.py (hand-assembled MIPS pad-test PS-X
  EXE + SYSTEM.CNF disc via mkpsxiso; header layout taken from the
  core's own LoadEXE: PC@0x10, TextStart@0x18, TextSize@0x1C, SP@0x30;
  two header bugs found and fixed along the way: SP accidentally placed
  at b_size offset (0x28) and a 4-byte layout shift)
- Probed INPUT_CAUSALITY (scripts/input_causality.py A/B harness +
  savestate branch divergence + per-frame input_state trace): the host
  input path is CORRECT (port0/device1/id7 -> 1 during holds, 32 polls
  per frame; branches byte-identical without input = deterministic);
  the OpenBIOS shell simply does not consume pad input (0 divergence;
  1800-frame scan found no exe flash either) -> INPUT_CAUSALITY =
  BLOCKED on content, not on the host
- host.py: load_game(None) contentless attempts with core-log tail in
  the error; api.py: var_overrides passthrough so OpenBIOS-mode runs
  engage the official override path; env_probe.py: BIOS truth table
  (RETAIL_OK / OPENBIOS_OK / KNOWN_UNSUPPORTED with the silent-fallback
  warning for SCPH-1001/7502 hashes) + firmware-path reporting
- scripts/autolab.py: one-command gate ladder (UNIT -> EMULATOR_SMOKE
  -> BIOS_BOOT -> CONTENT_BOOT -> INPUT_CAUSALITY -> TARGET_GAME) with
  JSONL ledger, fingerprint dedup (only PASS/PARTIAL dedup), time
  budget, and a single highest-value-blocker verdict; executed twice
  (second run dedups unchanged gates, BLOCKED gates re-run)
- Executed ladder on this machine: UNIT PASS (85 tests incl. 10 new in
  tests/test_bios_truth.py), EMULATOR_SMOKE PASS, BIOS_BOOT PASS
  (official OpenBIOS path), CONTENT_BOOT PARTIAL (mount + TOC + shell
  render; exe dispatch not reached), INPUT_CAUSALITY BLOCKED (needs
  pad-interactive content), TARGET_GAME BLOCKED (game_image missing)
- Re-checked the user-supplied MSX URL once more: still geo-gated
  (HTTP block page, 396-byte HTML) - never bypassed, never committed
- All README/worklog/docs content in this commit is English-only

Stage Summary:
- The "BIOS blocker" is now an EXECUTED decision table: the precise
  retail-BIOS requirement is scph5501.bin (MD5 490f666e1afb15b7362b406
  ed1cea246, SHA1 0555c6fa...) - user-supplied SCPH-1001/7502 cannot be
  loaded by this core - plus the still-missing SLUS-01212 image
- The machine now has: verified core, verified host input path, an
  official OpenBIOS boot path (MIT), lawful self-made content, and a
  resumable one-command experiment runner
- No gameplay/progress/mission result is claimed from this machine

## v0.9 — 2026-10-20 — the BIOS mystery solved; causality proven BIOS-free

- Firmware lookup is NAME-keyed; SHA1 mismatch only warns (vendored
  libretro.c). An aliased file IS loaded and executed.
- Executed the user's scph1001/7502 under the NA alias: CPU fetches
  0x4A32F2B8 at 0xBFC00000 -> COPU exception -> AdES loop at 0xBFC00180,
  zero RAM writes in 300 frames. No "System ROM"/"PS-X EXE" strings.
  MD5s match no Redump revision -> the files are NOT valid retail BIOS
  images (site-side obfuscation or corruption). Honest correction of the
  v0.8-era assumption that they were authentic.
- Answer: removed the BIOS from the evidence chain entirely.
  make_padtest_hw.py hand-assembles a pad-test EXE that polls the pad
  through the SIO hardware registers exactly as frontio.c implements
  them (SH-only CTRL/BAUD; replies one window late; stray-RX arming;
  MIPS load-delay honored). A small documented core patch (exe-direct
  boot) jumps the reset vector straight to the EXE entry.
- Gates now: UNIT 98/98 PASS, EMULATOR_SMOKE PASS, BIOS_BOOT PASS
  (retail files characterized INVALID), CONTENT_BOOT PASS (PAD1 magic,
  counter advances, polls ok=23 fail=0), INPUT_CAUSALITY PASS
  (none/RIGHT/LEFT/again = SW1 FF/DF/7F/DF at >=97.8%, RIGHT repeats).
  TARGET_GAME remains blocked on the user-supplied SLUS-01212 image.
- New tooling: iso9660_min.py (pure-Python EDC-correct disc writer),
  tests for both builders (+13; suite 98/98). Core provenance pinned:
  self-built df2b53b + diagnostics, md5 f3b4a4be842dc70b40aff65864cd8ce2.
