# Homebrew Source Ladder r21 — source-linked easy→hard intake doc

Task ID: r21t4 (research-only train — **zero emulator runs**). Supersedes
`docs/simple_games_ranking.md` as the authoritative source-link ladder for the
60% lightweight-games track (user standing policy: 60% very-simple lightweight
games / 40% baseline games).

Verification method (2026-10-27): the shared-egress GitHub API core quota was
exhausted all session (0/60 on IP 8.212.10.159), so every artifact claim below
was verified by **live re-download + SHA-256** (stronger than API metadata),
licenses by fetching the raw LICENSE files (HTTP 200 bodies quoted in
`data/homebrew/manifest.json` cross-checks), releases via the
`releases.atom`/`expanded_assets` HTML endpoints. Local artifact hashes were
recomputed with `sha256sum`. Everything not verified is marked **UNVERIFIED**.

---

## 1. Current standings (statuses copied verbatim from worklog + manifest — nothing invented)

| # | Game | Source | License | Ladder status (exact) | Evidence pointer |
|---|------|--------|---------|----------------------|------------------|
| 1 | hello_pong | github.com/marconvcm/ps1_dev (Actions artifact 9982555693) | MIT | **WON** 5–0 (r19): closed-loop agent pad1 vs disclosed harness sparring bot pad2; per-point RAM `left_delta=1 @0x1FFEB4`; play-again proven through play | manifest `accepted[hello_pong]`; `docs/issue6_r19_report.md` T4; GIF `docs/evidence_gifs/r19_t4_hellopong_win.gif` |
| 2 | FlappyBirdPSX | github.com/IcePanorama/FlappyBirdPSX | Unlicense | **WINNING** (PLAYING+WIN honest taxonomy, r15): 10 RAM-anchored pipe passes, score digits drawn "10", alive at win frame | manifest `accepted[flappybirdpsx].play.status`; `docs/tiny_games_playbook.md` §0/§7 |
| 3 | Poy Poy (USA, retail, local-only) | owner-supplied disc (never committed) | retail | **WON** r19 (charged throw → RETIRE! f1208, 3P hearts 0) + **PLAYING** r20 (live-slot 0x8009F778/F780/F7B0/F7EA, corr ±0.72; 16 charged throws; 3P hearts 2→1; 2nd retire NOT landed — "WON ادعا نمی‌شود") | `docs/issue6_r19_report.md`; ps1ai `worklog.md` r19/r20 (r20-t4); GIF `d.uguu.se/XhQSPUQH.gif` |
| 4 | Tetrade | github.com/Logan-Campbell/Tetrade | MIT | **PLAYING** (r19 RAM-truth bot): 1,816 pieces, 230 line clears, 81 cycles, max 11,240, landing accuracy **99.86%** (2863/2867), 20 game-overs + CONTINUE refusals | manifest `accepted[tetrade]` ROUND-19; `docs/issue6_r19_report.md` T3 |
| 5 | PSX-Minecraft | github.com/EngineersBox/PSX-Minecraft | MIT | **VISIBLE PLACE CONFIRMED** (r19; closes r7 INCONCLUSIVE): stack 10→9, world_px 1,269, persist-60f, UI guard clean; plus BOOTED + INPUT_RESPONSIVE + gameplay causality (r4) | manifest `accepted[psx-minecraft]`; `docs/issue6_r19_report.md` T5 |
| 6 | air_hockey (USA, retail, local-only) | owner-supplied disc | retail | **TITLE_INTERACTIVE** (r20-t5; supersedes r19 ALL_INERT which was a methodology artifact — 240f holds vs 3×-ambient threshold): title→PLAYER SELECT→"FIGHT ME!" gameplay through legal inputs; padbuff 0x09FF58/0x09FF7A (mask u16 BE @0x09FF5A, active-low) | ps1ai `worklog.md` r20-t5; `scratch/r20t5_airhockey/` |
| 7 | autogaz | github.com/egemenkus0/autogaz | MIT | **BOOTED_TITLE** (r20-t2), INPUT NOT RESPONSIVE yet (7 probes × 2 boots zero delta); frame counter u32 @0x800BCC00 +1/f; kernel pad pattern 00 41 ff ff @RAM 0xB008 | manifest `accepted[autogaz]`; `scratch/r20t2_autogaz/` |
| 8 | zenmai | github.com/msonrm/zenmai | MIT + SIL-OFL-1.1 (KH Dot font) + MIT (Zork I ZIL data, historicalsource/zork1) + zlib (MojoZork) | **BOOTED_TEXT** (r20-t3), **INPUT_UNPROVEN** — polls pad via **direct SIO** (0x1F80104x @ ~0x8001B340, no BIOS InitPAD, no 0041ffff padbuff) | manifest `accepted[zenmai]`; `scratch/r20t3_zenmai/` |
| 9 | Metal Slug X (retail, local-only) | owner-supplied disc | retail | Baseline **M1_AGAIN** (r20-t1): u16@0x800D4210 = unlock counter, NOT stage selector (r19 1-based conclusion RETRACTED). Open levers: **(mission,area) table consumer @0x8002CB30** (table @0x80010EE8) or legit MISSION SELECT pause (strings @0x8001019C) | ps1ai `worklog.md` r20-t1; `scratch/r20t1_msx/` |
| 10 | Doukutsu (Cave Story PSX) | github.com/fgsfdsfgs/doukutsupsx | MIT (port mods) / Cave Story freeware (Pixel) | **BOOTED_TITLE** (r13): LOADING→Pixel intro→title menu @f1740 | manifest `accepted[doukutsupsx]`; `scratch/round13_new_games/doukutsu_long/` |
| 11 | HMBTN (Harvest Moon: Back to Nature) | 5-repo community toolchain (hmbtn-decomp CC0, hmbtn-modkit MIT, …) — bring-your-own-disc | retail disc | **BLOCKED_PENDING_DISC** (disc-gated): text tooling READY (89.0% byte-exact corpus r19), boot + dialogue extraction gated on the user's own disc | ps1ai `worklog.md` r17/r19; `docs/hmbtn_text_r19.md` |
| 12 | Nortis | github.com/jbreckmckye/nortis | **NO LICENSE** (re-verified 2026-10-27: raw LICENSE 404 on main/master; repo carries release tag `build` → release.zip but that does not cure the license gap) | LOCAL-ONLY played (title→gameplay, causal chain A6-grade) but **integration refused** — never present a no-license repo as ingestable | manifest `rejected[nortis]` |
| 13 | psxBreakout | github.com/NDR008/psxBreakout | unspecified (CS50 project) | CANDIDATE, boot blocked: EXE_LOAD_CRASH under OpenBIOS; 16-sector single-read cliff (route 4 of the boot tree); `.map` sensors still valuable | manifest `candidates_pending[psxbreakout]`; `docs/tiny_games_playbook.md` §1.4 |
| 14 | BKBS_PSX (Bambi's Knees, one-song rhythm) | github.com/hardrockbluesky/BKBS_PSX (repo-tree EXE route by r21t1; itch.io bin/cue verified by r21t4) | MIT code / **NC** Data+Audio | **RUNNING** (r21t1): boots headlessly, gameplay animates, per-button pad bits proven; note HITS not proven (PLAYING not claimed) | manifest `round21_addendum`; `scratch/r21t1_bkbs/`; GIF `docs/evidence_gifs/r21t1_bkbs_rhythm.gif` |
| 15 | ballistic / Trap Gunner / FFT6 (old-games batch) | owner-supplied | retail | ballistic BOOT_THEN_STALL (r19); Trap Gunner booted + menu-walk mapped, RAM mapping pending; FFT6 boot-verified | `docs/simple_games_ranking.md` session-5 batch; r19 worklog |

Backend facts that gate this ladder (from r20): beetle_psx 0.9.44.1 + OpenBIOS
delivers input through the kernel padbuff (`00 41 ff ff`) for BIOS-pad games;
games that read the pad via **direct SIO** (zenmai, autogaz — and see MSPSX
below) show zero input deltas on this backend; the r21 plan names a
**mednafen backend for direct-SIO games** as the countermeasure. License
sectors 0..15 from the user's own retail disc (MSX) unblock the OpenBIOS
CDChecker boot loop; patched images are local-only, never committed.

---

## 2. Verified source links (known ladder — re-verified live 2026-10-27)

Every artifact below was re-downloaded and SHA-256-matched against
`data/homebrew/manifest.json` this session (files held locally under
`emu/games_homebrew/candidates_r21/known_reverify/`, never committed):

| Game | Repo (default branch) | License file verified | Release tag / artifact | Bytes | sha256 (match) |
|------|----------------------|----------------------|------------------------|-------|----------------|
| autogaz | github.com/egemenkus0/autogaz (main) | `LICENSE` = MIT (c) 2021 ekus447 — HTTP 200 body read | `vStable` → `autogaz-ps1.zip` | 468,721 | `765f1047…2520a46` ✓ |
| zenmai | github.com/msonrm/zenmai (main) | `LICENSE` = MIT (c) 2026 msonrm — HTTP 200; README §License names SIL-OFL-1.1 KH Dot font (`native/vendor/kh-dotfont/`), MIT Zork I ZIL data (historicalsource/zork1), zlib MojoZork (icculus/mojozork) | `ps1-v1.5.0` → `zenmai-zork.psexe` | 700,416 | `7f4be544…9cc2e4e2` ✓ |
| Tetrade | github.com/Logan-Campbell/Tetrade (master) | `LICENSE` = MIT (c) 2024 Logan Campbell | `v1.0` → `TETRADE_PSX.bin` | 3,196,368 | `2f41feba…4640d6eaf8` ✓ |
| FlappyBirdPSX | github.com/IcePanorama/FlappyBirdPSX (main) | `LICENSE` = Unlicense text confirmed | `v0.1.0` → `flappybirdpsx-v0.1.0.iso` (license sectors present) | 571,536 | `b45871d3…2296f0ed` ✓ |
| PSX-Minecraft | github.com/EngineersBox/PSX-Minecraft (main) | `LICENSE` = MIT (c) 2025 EngineersBox | `infdev_2025_04_18` → `infdev_release_2025_04_18T04_35_17_.tar.gz` | 695,797 | `45b076ca…2ab0dd74` ✓ |
| doukutsupsx | github.com/fgsfdsfgs/doukutsupsx (master) | `LICENSE` = MIT for PSX mods (CSE2 lineage, (c) 2019 cuckydev/Clownacy/Gabriel Ravier/2021 fgsfds) + Cave Story freeware notice | `v0.7` → `doukutsu_r7_us.iso` (HEAD content-length 32,565,792 — size verified live; full re-hash not needed this session, r13 hash on record) | 32,565,792 | `bf15559e…5c27554` (r13 record) |
| hello_pong | github.com/marconvcm/ps1_dev (main) | `LICENSE` = MIT (c) 2024 @marconvcm | no tag release; Actions artifact 9982555693 (zip digest API-matched r4/r6; expiry 2026-12-05) | 2,500,176 (zip) | `a592f7ed…15615af247` (r6 re-fetch record) |
| psxBreakout | github.com/NDR008/psxBreakout (master) | none in repo — "unspecified public release" | `v1.0` → `cs50x.exe` | 79,872 | `822a50e6…3cc2425` ✓ |
| Nortis | github.com/jbreckmckye/nortis (main) | **NO LICENSE — raw LICENSE 404 on main AND master (verified 2026-10-27); release tag `build` → `release.zip` exists but is NOT ingestable** | — | — | — |

License-gap flags unchanged: Nortis stays non-ingestable; psxBreakout has no
stated license (sources read-only, artifact candidate only).

---

## 3. NEW candidates (r21 search) — very simple PSX homebrew WITH source

Search method: GitHub repo search (`topic:psx/ps1 + homebrew`, `license:mit`,
plus genre keywords pong/snake/flappy/minesweeper/breakout/chess/sokoban),
releases via atom feeds, READMEs + pad-driver sources read raw. Rejected
non-candidates recorded honestly at the end.

### N1. MSPSX — Minesweeper Plus for PlayStation  **TOP NEW PICK**
- Repo: https://github.com/AcidGunner/MSPSX (branch `main`; single `src/` of
  main.c + pad.c/spi.c + assets + tracks)
- License: **Unlicense** (public domain) — raw LICENSE body verified live.
  One vendored exception: `src/spi.c` is spicyjpeg's PSn00bSDK controller
  polling example, **(C) 2021 spicyjpeg, MPL-2.0** (file-level copyleft; fine
  for local research use, note if ever redistributed).
- Artifact: GitHub release `v0.1` → `mspsx.bin` + `mspsx.cue` (MODE2/2352
  disc with 4 AUDIO music tracks). **Downloaded + structurally verified**
  (see §4). 117,891,648 B — big because of CD-DA tracks, the data track is
  tiny.
- Genre: **minesweeper** — turn-based, discrete grid, no real-time pressure.
- Why easy: 8 input keys total (arrows + CROSS flag + CIRCLE chord + START),
  fully deterministic board, win/lose conditions are simple flags, board and
  cursor are RAM-localizable integers (cursorX/cursorY/flags straight from
  `main.c`), zero timing requirements — the friendliest verifiable-goal game
  on the whole ladder.
- Boot route: license sectors are **EMPTY** (sector 4 blank — verified) →
  **route 2**: `scripts/make_homebrew_lic.py` local patch from the user's own
  retail disc (SYSTEM.CNF `BOOT=cdrom:\mspsx.exe;1`; PVD volume
  `MINESWEEPERPSX`, system `PLAYSTATION` — genuine PSX image).
- Input mechanism: **custom direct-SIO driver** — `src/spi.c` talks to
  SIO_CTRL/SIO_DATA (0x1F801040 region) with a custom interrupt, NOT BIOS
  InitPAD. This is the same class as zenmai/autogaz ⇒ expected to show zero
  input deltas on beetle+OpenBIOS; **ideal first client for the r21
  mednafen-backend plan** (turn-based games are the cheapest possible
  causality probes on a new backend).

### N2. BKBS_PSX — "Bambi's Knees / Bambi's Shaking" (one-song rhythm game)  **TOP NEW PICK #2**
- Repo: https://github.com/hardrockbluesky/BKBS_PSX (branch `main`;
  `BKBS/` = MAIN.C, 2D.c, 3D.c, Audio.c, Cine.c, Constants.c, Controller.c,
  ReadCD.c, MAKEFILE.mak, SYSTEM.CNF; a committed `MAIN.EXE` + `main.cpe`
  are in-repo; port to PSYQo exists: hardrockbluesky/BKBS_PSYQo, MIT).
  r19 scouting already fetched the main sources (cached `/tmp/bkbs_*.c`).
- License: **MIT** code (`License.txt` (c) 2024 hardrockbluesky — body
  verified live). **NC restriction on data**: the README grants Data+Audio
  folders **non-commercial use only, credit required, revocable**; PSY-Q
  files are Sony's and not in the repo; `LICENSEA.DAT` excluded (provide
  your own). We run locally and never redistribute bytes — compliant, but
  the NC caveat must stay attached to any artifact reference.
- Artifact: **not on GitHub releases** — prebuilt `.bin`/`.cue` on the
  author's itch.io page (https://hardrockbluesky.itch.io/bambis-knees-bambis-shaking,
  3 zip variants: Duckstation / MiSTer / RealHW).
  **Downloaded + structurally verified** (see §4).
- Genre: one-song rhythm/timing game (notes approach a hit line; buttons on
  beat).
- Why easy: bounded content (exactly ONE song), small input surface (PSY-Q
  pad word; README video shows the full run ≈3 min), score/hit judgement is
  RAM-friendly; the chart data is generated CSV→bin (NoteChartBuilder /
  CSVtoNoteBin, both MIT) so the note timeline is reconstructible from data —
  servo math à la flappy §5 applies directly.
- Boot route: license sectors **PRESENT** in the itch prebuilt ("Licensed by
  Sony Computer Entertainment America" — verified) → **route 1: direct
  mount**, zero patching.
- Input mechanism: PSY-Q `PadInit(0)` + `PadRead(0)` (read live in
  `Controller.c`) = **BIOS pad service class — same as Tetrade/hello_pong,
  expected to work on the current beetle+OpenBIOS backend**. This is the
  strongest input-compatibility bet of the batch.
- **r21 STATUS UPDATE (parallel train r21t1, after this research pass):**
  BKBS was ingested the same day — per the manifest `round21_addendum` it is
  **RUNNING**: 2 boots used, gameplay animates (cine tour + 8–9 falling
  arrow notes), per-button pad-mirror bits proven at the correct PSX bits
  (SELECT 0xFFFE / CROSS 0xEFFF / START 0xFFF7 / UP 0xFFEF — matching the
  `PadInit(0)` prediction above); note HITS not yet proven (PLAYING not
  claimed). r21t1's artifact route differs from ours: repo-tree
  `MAIN.EXE` 172,032 B sha256 `cb0dde6e…bb8e5814` + data files + WAVs,
  wrapped with `scripts/r21t1_bkbs_wrap.py` (CDDA `PlaySyncedTrack()` needs
  TRACK 02 INDEX 01 pinned at MSF 00:22:55). Evidence:
  `scratch/r21t1_bkbs/` + `docs/evidence_gifs/r21t1_bkbs_rhythm.gif`.

### N3. psx-pong — "Pong Ultimate" (stuartaharrison)
- Repo: https://github.com/stuartaharrison/psx-pong (branch `master`;
  main.c, pong.h, controller.h, constants.h, MAKEFILE.mak — ~5 files).
- License: **MIT (c) 2018 Stuart Harrison** — raw LICENSE verified live
  (default branch is `master`, not `main`).
- Artifact: **none** (0 releases; source-only). PSY-Q toolchain build
  (Windows-XP-VM style) — not buildable in this sandbox today.
- Genre: pong (2 paddles, ball, scoreboard).
- Why easy: 2–4 keys, deterministic geometry, explicit scoreboard strings —
  a hello_pong sibling; source is small enough to fully model before boot.
- Boot route: once built, raw PS-EXE → iso9660_min wrap (route 3, now
  boot-verified by zenmai r20) + local license sectors.
- Input: `PadInit(0)` (controller.h, verified live) = BIOS class ✓.

### N4. psx-flappy-bird (mfotzler)
- Repo: https://github.com/mfotzler/psx-flappy-bird (branch `main`; main.c,
  game.c/h, iso.xml, system.cnf; PSn00bSDK cmake build).
- License: **MIT** (search API + LICENSE present in tree; raw body spot-read).
- Artifact: **none** (0 releases; source-only). Build needs PSn00bSDK
  (native Linux build possible via alex-free/psn00bsdk-builder, BSD-3-Clause
  — UNVERIFIED in this sandbox) and the author's own `LICENSA.DAT` note in
  iso.xml (comment-out-able).
- Genre: flappy clone (1-button).
- Why easy: identical genre to our r15 WINNING benchmark; the playbook's
  measured servo band + i16 lessons transfer 1:1; `InitPAD/StartPAD/
  ChangeClearPAD` (main.c, verified live) = BIOS pad class ✓.
- Boot route (once built): iso.xml builds a full PSX image; supply license
  file locally → route 1/2.
- Rank below N1/N2 only because there is no release artifact — the sandbox
  cannot cheaply produce one.

### Search-rejected / noted (do not ingest)
- danhans42/psx_pong — no license; ProFiLeR4100/psx-flappy-bird, haxk34/
  danx2016 ps1snake — no license; netyarouze Dragon's Lair / Time Warp /
  Space Ace ports — no license + huge FMV; fgsfdsfgs/quakepsx (GPL-2.0) and
  vs-sr-dev/psx-lba (GPL-2.0, BYO assets) — far beyond "very simple";
  joyrider3774's MIT puzzle family (waternet/sokoban/znax…) — excellent
  genres but **no PS1 target exists** (GB/GG/SMS/Pocket/embedded only);
  aaronjamt/3-Player-Pong (MIT) — requires TI-86 link hardware;
  Forceh91/psyqo-madnight-engine (LGPL) / KasaBranca/Mipsync (MIT) —
  engines, not games with artifacts.
- `myfate_hellocpp.bin/.cue` (r19 candidates cache) — provenance UNVERIFIED
  (no repo identified; treat as orphan until sourced).

---

## 4. Rough download verification (top 2 new candidates — NO emulator runs)

Held in `/home/z/my-project/emu/games_homebrew/candidates_r21/` (local-only,
never committed):

| File | Bytes | SHA-256 | Live structural checks (parse only) |
|------|-------|---------|-------------------------------------|
| `mspsx_v0.1.bin` | 117,891,648 | `d35a189b1ed14b7f07bf4cc31423ca43d8f34e35e8c3cb40c11bc6d3d0a4c5fa` | MODE2/2352 sync `00 FF×10 00`, subheader `00 02 00 02`; PVD: system `PLAYSTATION`, volume `MINESWEEPERPSX`; SYSTEM.CNF `BOOT=cdrom:\mspsx.exe;1`; **license sectors EMPTY** (sector 4 blank) → route 2 patch needed; 4 CDDA tracks per cue |
| `mspsx_v0.1.cue` | 312 | `89f1c1272a05cc21ca3e474b6fbbecfa911d8b056716ae5d0fd8dc22ceb30541` | TRACK 01 MODE2/2352 + 4 AUDIO tracks |
| `bkbs_duckstation.zip` | 37,315,651 | `f7e1e1173db46a3167ba64f042e4d844ed209767fede9ddd9f2b59c6fd91b4e7` | itch.io upload id 9959709 "Bambi Duckstation Ver.zip"; contains `BKBS (Duckstation).bin` 47,324,592 B + cue 212 B |
| (inner, parsed in-memory) `BKBS (Duckstation).bin` | 47,324,592 | not re-hashed (zip-inner) | sync + PVD `01 CD001`; **license sectors PRESENT**: `Licensed by Sony Computer Entertainment America` → route 1 direct mount; SYSTEM.CNF `BOOT=cdrom:\MAIN.EXE;1, TCB=4, EVENT=10, STACK=801FFFF0`; 2 CDDA tracks (the one song) |

Also re-verified this session (known games, `known_reverify/`): the six
artifacts of §2 — all SHA-256 matched their manifest records on live
re-download.

Honesty notes: MSPSX "v0.1" is the only release; BKBS binaries are
third-party-hosted (itch.io) with an NC data grant — record bytes/hashes as
reference, never redistribute; psx-pong / psx-flappy-bird claims are
source-read only (**no artifact UNVERIFIED**).

---

## 5. 60/40 mapping → r22 intake shortlist

### 60% lightweight track (new names, easy→hard)
1. **MSPSX** (minesweeper) — artifact verified + held; boot route 2 (local
   license patch); FIRST GAME on the mednafen backend (direct-SIO pad),
   doubling as the backend-causality probe; turn-based ⇒ cheapest possible
   observe→decide→act loop and a clean win/lose flag to anchor.
2. **BKBS_PSX** (one-song rhythm) — artifact verified + held (itch route);
   **already RUNNING after the parallel r21t1 intake (pad bits proven) —
   its r22 step is not intake but PLAYING: note-hit causality** (hit
   judgement word + beat-window servo from the CSV-derived chart); BIOS-pad
   class so all of this can run on the CURRENT backend; bounded single-song
   scope.
3. **psx-flappy-bird** (mfotzler, MIT) — no release: first step is a
   PSn00bSDK build (psn00bsdk-builder, UNVERIFIED in sandbox) or a polite
   release request upstream; playbook transfers 1:1 once an artifact exists.
4. **psx-pong** (stuartaharrison, MIT) — source-modeled first; needs a PSY-Q
   build path (blocked by toolchain, same class as the old hello_pong
   blocker) — keep as source-reading + sensor-design exercise.

### 40% baseline levers (pick per r21 plan in the worklog)
- **Keep #1 — MSX stage-loader**: disassemble the consumer @0x8002CB30 of
  the (mission,area) table @0x80010EE8 (r20-t1's named "true lever"; the
  unlock-counter block 0x800D4210 is closed). This is the highest-value
  baseline lever and needs no new intake.
- **Keep #2 — air_hockey causality map**: single-button causal battery with
  the CORRECT mask probe (u16 BE @0x09FF5A, active-low) in ONE boot — cheap,
  converts TITLE_INTERACTIVE into PLAYING evidence.
- **Deferred — Poy Poy retire #2/#3**: r20-t4 already spent its 2-run
  emulator budget (disclosed); the next step there is the OFFLINE writer-hunt
  on the 0x8009F7xx cluster readers, which costs zero emulator runs — do that
  desk pass first, then one budgeted live run.
- Cross-cutting: **mednafen backend** for direct-SIO games (zenmai, autogaz,
  MSPSX) is the r21 plan's infrastructure item and is served by the 60% pick
  #1 above.

### Standing-policy check
After r22 executes the shortlist: the lightweight ladder gets 1 new
artifact-backed game (MSPSX) + 1 candidate promoted to PLAYING (BKBS) +
2 build-gated candidates (psx-flappy-bird, psx-pong) = the 60% side; the
40% side keeps MSX + air_hockey moving with zero new intake. Nortis and
every no-license repo stay out. All game bytes remain local-only.

---

# Round 22 addendum (2026-10-28) — r22t4 web scout, round 2

Research-only (no emulator boots). Extends §1-§5 above without rewriting them.
Method: GitHub API core was again 0/60 on the shared egress IP all session, so
discovery used the **search API (separate 10/min quota, ~22 calls)**, raw file
fetches, `releases.atom`/`expanded_assets`, and shallow `git clone` (12 repos,
pinned commits below). itch.io only loads in a real browser (Cloudflare blocks
curl; PS1 has no platform facet — the discovery facet is the **tag**
`itch.io/games/tag-psx`, which is dominated by PS1-*aesthetic* horror games,
not homebrew). **psxdev.net is temporarily shut down (announced Oct 2025,
server migration)** — scene-forum lists were NOT crawlable this round; the
live scene mirror `psx.arthus.net` was crawled instead.

## 22.1 New candidates (round-2 search)

| # | Game | Repo | License (raw file / body verified) | Artifact | Genre | Why easy | Input class (grep, exact) | Boot route | Release evidence |
|---|------|------|------------------------------------|----------|-------|----------|---------------------------|------------|------------------|
| N22-1 | **BuzzyBee** | github.com/NDR008/BuzzyBee | **MIT (c) 2021 NDR008 — file-header license in main.c:1-25; NO standalone LICENSE file (flagged)** | in-tree `BuzzyBee.ps-exe` 299,008 B — parsed: `PS-X EXE`, pc0 0x80010000, t_addr 0x80010000, t_size 296,960, sp 0x801FFF00 ✓ | 1-button flappy-like arcade (X accelerates, SELECT pauses, energy drains / flowers / wasps) | 1 action key + pause; flappy playbook §2-§5 transfers 1:1; open-world energy economy = RAM-friendly | **BIOS class**: `engine/input.c:59 InitPAD(padbuf[0],34,padbuf[1],34)` + StartPAD (doukutsupsx-derived driver, same as flappy) | route 2: CD-wrap the PS-EXE + local license sectors (>32 KB, so NOT the container route) | itch.io page (ndr008.itch.io/buzzy-bee), YouTube gameplay r3NW8sTUX1c, v1.1 image mirrored at psx.arthus.net/homebrew/BuzzyBee_v1.1_image/ — **downloaded + hashed** (22.2) |
| N22-2 | LostPlumber | github.com/NDR008/LostPlumber | **MIT (c) 2021 NDR008 — same in-header-only pattern (flagged)** | in-tree `LostPlumber.ps-exe` 86,016 B — parsed ✓ (pc0 0x80010000, t_size 83,968, sp 0x801FFF00) | jam prototype: scroll-right world walker (Lost Cartridge Jam 2021) | minimal loop (RIGHT scroll only), tiny binary | **BIOS class**: `engine/input.c:59 InitPAD` (same driver) | route 2 (same as N22-1) | repo build only; no itch page found (weak evidence) — **downloaded + hashed**, ranked BELOW BuzzyBee |
| N22-3 | psx-snake | github.com/mfotzler/psx-snake | **MIT (c) 2023 mfotzler — standalone LICENSE verified** | **none — source-only (releases.atom empty)** | snake: 4-dir, wall/tail death, START restart | grid game, 4 keys + START, explicit GAME OVER text | **BIOS class**: `main.c:59-61 InitPAD/StartPAD/ChangeClearPAD` (padbuff[2][34]) | needs a PSn00bSDK build first (psn00bsdk-builder UNVERIFIED in sandbox); iso.xml ships license tag **commented out** → route 2 after build | README build steps only — **artifact UNVERIFIED** |
| N22-4 | psx-simple-pong | github.com/jlbeard84/psx-simple-pong | **MIT (c) 2021 Josh Beard — standalone LICENSE verified** | none — source-only; PSY-Q/libgs build (Wituz-derived framework) | pong, but **1P vs a static wall — no AI, no scoring** (main.c: playerTwo never moves; ball resets at x<0) | 2 keys; deterministic geometry | **BIOS class**: `source/controller.h:40 PadInit(0)`, `:49 PadRead(0)` (+ SysPadT edge helper) | PSY-Q toolchain build (blocked, same class as psx-pong) | none — source-modeled exercise only |
| N22-5 | VoXide v0.1.11 | game: github.com/EBonura/voxide (Rust); audited distribution: github.com/tuuchen/ai-game-portal-ps1 | game code **GPL-2.0-or-later** (LICENSE inside release zip verified), assets **CC0 per the portal's own audit doc**, portal wrapper MIT, emulator PSoXide GPL-2.0-or-later | release `voxide-v0.1.11.zip` 384 KB → `voxide.bin` 2,511,936 B — parsed: MODE2/2352 sync ✓, PVD volume `VOXIDE`, SYSTEM.CNF `BOOT=cdrom:\PSX.EXE`, **license sectors 0..15 EMPTY → route 2** | Minecraft-style voxel survival sandbox (PSX-Minecraft sibling) | not "very simple" — 40%-side-adjacent candidate | Rust psx-sdk-rs (BIOS or custom pad — UNVERIFIED at source level) | route 2 (empty license sectors) | GitHub release tag `ps1-homebrew-2026-09-14` + exemplary per-game license audits (LICENSE-AUDIT-VOXIDE.md) — **downloaded + hashed** |
| N22-6 | Cortex Ignition Tech Demo | bonnie-studios.itch.io/cortex-ignition (source: PSoXide-editor @0f12f4d) | **GPL-2.0 release** (per portal audit); **provenance gap on author voice/weapon recordings disclosed by the audit itself** | release `cortex-ignition-2026.09.05.zip` 23.2 MB (not downloaded this round) | 3D action tech demo — too heavy for the 60% track | — | — | ships with PSoXide notice + SHA-256 receipt | official itch + release — noted, not intake |

Flag-only (no license in tree — never ingestable; raw LICENSE 404 verified via clone trees): **vivi168/mrbskb** (Sokoban on PSX via mruby — turn-based grid puzzle, EXACTLY our genre, PSY-Q+mkpsxiso build, no release; **if upstream ever grants a license this jumps near the top**), reaksiyon/Psy-Q-SDK-Nyorai-PSX-Game (endless RPG; ships `NYORAI/cdimage/game.iso` in-tree but no license), Hidden0-prj/PSX-Snake-Alpha-V2, squidnugget07/flappybird-psx, martpalder/psx-pong (PSn00bSDK), grundhofer/pong-psx "7Pong" (PSY-Q, 2P-only), itsAfeat/PSX-bong, jasonknoll/PSX-Pong (PsyQo C++), NewNova88/PSXPong, StanislavSeregin/ps1-rs-game (Rust demo), Jarwesbub/un-game-psx-demo.

Rejected false positives (name-matched but not PSX games): Becker-LG/Sudoku-PS1 (PowerShell scripts), Selim20011/Time_Warp_II (Python grading tool), M-Matthew/PS1-Memory (Android app), Dr3pz/BlackJack.ps1 (PowerShell), silentroadgame/afterlight (Unity PC game). Noted-not-intake: fgsfdsfgs/rawpsx (Another World port, MIT, PSn00bSDK — cinematic, heavier than "very simple"; future 40%-side candidate).

## 22.2 Downloaded + hashed (candidates_r22, local-only, never committed)

`/home/z/my-project/emu/games_homebrew/candidates_r22/` + `sha256_candidates_r22.txt`:

| File | Bytes | SHA-256 | Live structural checks (parse only) |
|------|-------|---------|-------------------------------------|
| `BuzzyBee.ps-exe` (raw GitHub HEAD) | 299,008 | `9b0bfc08…c909a8ba` | `PS-X EXE` magic ✓ pc0 0x80010000 t_size 296,960 sp 0x801FFF00 ✓ |
| `LostPlumber.ps-exe` (raw GitHub HEAD) | 86,016 | `413d315a…fbc863f8` | `PS-X EXE` magic ✓ pc0 0x80010000 t_size 83,968 sp 0x801FFF00 ✓ |
| `buzzy_v11_scene.bin` (psx.arthus.net v1.1 mirror) | 38,692,752 | `d5d7a629…f7acc32d` | sync ✓, PVD volume `BUZZYBEE`, SYSTEM.CNF `BOOT=cdrom:\BUZZYBEE.EXE` @LBA23, 1 CDDA track; **license sectors are CUSTOM ("32bit Jam / PSX Development / Scene is Alive" + waveform blob), NOT "Licensed by Sony" → expect the OpenBIOS CDChecker loop; patch locally (route 2) or use the PS-EXE** |
| `buzzy_v11_scene.cue` | 133 | `fe9e76a6…7168f7e07` | TRACK 01 MODE2/2352 + TRACK 02 AUDIO (pregap 00:02:00) |
| `voxide_v0.1.11.zip` (portal release) | 393,263 | `a9f20b0d…45dd12bb` | zip-inner: LICENSE (GPL-2.0-or-later text), voxide.bin 2,511,936 B (sync ✓ PVD `VOXIDE`, SYSTEM.CNF `BOOT=cdrom:\PSX.EXE`, license sectors EMPTY), voxide.cue |

Inner-file hashes (voxide zip) are in `sha256_candidates_r22.txt` too. Honesty
notes: the buzzy scene-mirror bytes are reference-only (NDR008's own game, MIT
code; image provenance = scene mirror); BuzzyBee/LostPlumber licenses live as
file headers, not LICENSE files — fine for local research, flag before any
redistribution.

## 22.3 Deepened entries (what the internet added)

### (a) MSPSX — exact source map for the intake train (repo @6d92714, 2026-08-15)
- **Pad driver = spicyjpeg PSn00bSDK SPI example, `src/spi.c` (MPL-2.0 header
  :1-4), custom direct-SIO, takes over the whole SPI bus (spi.h docstring)**:
  - `SPI_Init` **:168-185**: EnterCriticalSection, `ChangeClearRCnt(2,0)`,
    `InterruptCallback(6, _spi_poll_irq_handler)`, `InterruptCallback(7,
    _spi_ack_irq_handler)` (:172-176), `SIO_CTRL(0)=0x0040` reset (:178),
    `SIO_MODE(0)=0x000d` (:179), `SIO_BAUD(0)=0x0088` =250 kbps (:180),
    `SPI_SetPollRate(30)` (:182 — 30 Hz poll; RCnt2-based, `TIMER_CTRL(2)=0x0258`
    :160-165).
  - `_spi_poll_irq_handler` **:70-100**: drains the last RX byte iff
    `SIO_STAT(0)&0x0002` (:73-74), fires the callback (:76-77), then re-arms:
    `SIO_CTRL(0)=0x0010` (:89) → 1000-iter delay → `SIO_CTRL(0)=0x1003|port<<13`
    (:93; 0x1003 = RXIRQen|TXEN|DTR — **no RXEN bit**) → 2000-iter delay →
    sends byte 0x01 (:99).
  - `_spi_ack_irq_handler` **:102-132**: waits `while (SIO_STAT(0)&0x0080)`
    (/ACK low, :106-107), `SIO_CTRL(0)=0x1013|port` (:111; +IRQ-ack), then
    **dummy `SIO_DATA(0)` read on the FIRST byte** (:113-118 — flushes the FIFO
    AND, on Beetle, arms ReceivePending), real byte read :120-123, sends the
    next TX byte or 0x00 (:127-131). Poll TX packet `[01 42 00 00]` (:32-44).
  - Game side `src/pad.c`: custom `pad_buff[2][34]` :10 (**NOT the BIOS
    padbuff**), `poll_cb` :53-59, `Pad_Update` :74-86 (needs
    `pad_buff_len[0]>=4`; `held=~btn` :80; pressed/released edges :82-85),
    `dualshock_init_cb` :35-51 (unused by default), **`DebugOutput()` :103-110
    prints `LEN=… XX XX XX XX` (first 4 SIO response bytes) — drawn on the
    TITLE SCREEN by main.c:542** → the title screen is a live SIO debug
    display for backend bring-up.
- **Board memory layout (`src/main.c` @646 lines)**:
  - `Cell{u8 mine; u8 revealed; u8 flagged; int neighbors; bool
    hasNeighborMines; u8 active; u8 processed}` :78-87 → **16 B/cell** (MIPS
    o32: 3×u8 +3 pad +int(4) +bool(1) +2×u8 +1 pad), `Cell board[24][16]`
    :75-76, :88 → **6,144 B, column-major `board[x][y]`** (x=col 0..23, column
    stride 0x100; y=row 0..15). `RevealNode reveal_queue[384]` (8 B each)
    :94-95.
  - Scalars: `GRID_W=16, GRID_H=12, MINES=32` :97-99; `mine_count` :100;
    `reveal_mode` :101 (0=BFS); `control_disable` :103 (input lock +
    end-state); `lost` :104; `revealed_total` :106; `valid_total` :107;
    `cursorX/cursorY` :109-110; `off_x/off_y=12` :429-430; `FIRST_CLICK` :494.
  - Win: `WinCheck` **:176-208** — `revealed_total>=valid_total` →
    `control_disable=1`, `mine_count=0`, mines auto-flagged. Lose: `lost=1`
    in `RevealIterative` :235-240, `RevealRecursive` :279-284, `Chord`
    :334-339. Restart: START when disabled :628-640 (cursor reset :635-636).
  - Loop: title gate "PRESS START" :536-551 (with "Did controls fix?" :540);
    seed `srand(GetRCnt(RCntCNT2))` :553-554 (**RCnt2 is also the SPI poll
    timer**); edge-triggered cursor :581-584; CROSS reveal/chord :586-605
    (FIRST_CLICK safe-first-click regen :590-598); CIRCLE 3-cycle flag
    :607-620; CDDA `PlayTrack` :496-515, track 2+(rand%4) :560-561/:638-639.
- **Source-derived prediction (UNVERIFIED — needs one boot)**: MSPSX is
  direct-SIO but its handshake is **read-per-byte** (dummy read then TX per
  byte, spi.c:113-131). On Beetle (see (e)) each JOY_DATA *read* arms
  ReceivePending, so the MSPSX pattern may deliver real bytes on
  beetle+OpenBIOS — unlike zenmai's TX-only-then-wait-RXRDY loop. If it does,
  MSPSX needs **no mednafen backend**; if it doesn't, DebugOutput on the
  title screen shows the raw response immediately.

### (b) zenmai — upstream tracker state (all 57 closed PRs searched, incl. bodies)
- **Zero mention of SIO, pad handshake, /ACK quirks, or any emulator pad
  compatibility** (searched pad/SIO/コントローラ/実機 across all PR bodies;
  no open issues exist). The author tests on a hand-written R3000 sim +
  **real hardware** (PS1, PS2/FreeMcBoot+POPStarter, R36H) — emulators are not
  in their test matrix, so our r21t3 Beetle-vs-TX-only finding is new
  information to upstream (courtesy-issue candidate; not filed by us).
- Closest upstream signals: **PR #12** (memory-card save over the same SIO,
  device 0x81; author: "/ACK の間合いや書き込み待ちは [sim が] 模していない。
  実機が最後の砦" — /ACK timing not modeled, real HW is the final arbiter);
  **PR #30** (real-PS2 "No Disk!" fixed by `.VCD` uppercase naming + burning
  license data; author explicitly suspects POPS checks the license region —
  corroborates our license-sector discipline); **PR #13** (the author's own
  pad_prev edge bug — "keep pad reading in ONE place").

### (c) BKBS — note/judgment timing constants (repo @6b96f6b, `BKBS/MAIN.C`)
- `#define GOAL_Y 90` :34; **hit window `arrowSprite.y > 83 && < 102`** :651
  (19-px ≈ 316 ms @60 fps — author: "this game is not very picky about
  timing", Audio.c:99). Notes spawn at `y=-240+frameLagTotal` :577 and move
  `y+=frameDiff` with frameDiff≈2 :563-565/:648 (ArrowUpdate ticks at 30 Hz;
  note speed = **1 px/frame @60**; spawn→window = 323 frames ≈ 5.4 s).
- `frameDelay=12` :77 (lead-in before the chart starts); `endingFrame=6060`
  :149 (≈101 s; **win = reaching EndingScreen**); **no score/miss/combo
  counter exists** (grep: none) — a hit only flips `note.hit`, spawns
  effects, and whitens the arrow → r22/r23 PLAYING evidence = per-note
  `hit` bytes/effect state; WINNING = surviving to endingFrame.
- Button map (edge-triggered `padCheckPressed`, Controller.c:7 `SysPadT`):
  u=0 LEFT = Pad1Left|Pad1Square :654; u=16 DOWN = Pad1Down|Pad1Cross :714;
  u=32 UP = Pad1Up|Pad1Triangle :775; u=48 RIGHT = Pad1Right|Pad1Circle
  :811. Chart: 4 nibbles/byte per tick (`ReadChart` :569-576), 30-note pool
  :33/:120. README: "Emulator and real hardware should be essentially
  flawless, assuming your emulator does CD emu properly!" + full playthrough
  video pl0-Lkwz1Hw.

### (d) Nortis — license re-check (fresh clone @8c348e2, 2026-10-28)
- **Still NO LICENSE file** (tree listing + grep; README:550-557 documents the
  author's own license_data.dat gitignore practice). Release zip unchanged
  (local r13 copy). **Stays non-ingestable.**
- NEW fact: Nortis input = **BIOS class** — `psx/game/pad.c:24 InitPAD(pads[2]
  [34])`, `:26 StartPAD()`, `:28 ChangeClearPAD(1)`. Semantics (pad.c:44-66):
  CIRCLE rotate / CROSS drop / START restart fire only on press
  (`btnHeldFor==0`); LEFT/RIGHT auto-repeat every 15 held frames. ⇒ if the
  license gap is ever cured, Nortis lands on the current backend with zero
  input work.

### (e) Direct-SIO block, explained by core sources (fetched raw; parse-only)
- **beetle-psx-libretro @2ba074e (2026-10-27), `mednafen/psx/frontio.c`**:
  JOY_DATA *write* 0x1F801040 only sets `TransmitPending=true` (:861-865);
  JOY_DATA *read* clears RXRDY (`ReceiveBufferAvail=false`) and
  **arms `ReceivePending=true`** (:959-966); transfer starts on
  `(ReceivePending && CTRL&0x4 /*RXEN*/) || (TransmitPending && CTRL&0x1
  /*TXEN*/)` (:802, :799-841); the receive half — bit latch into
  ReceiveBuffer and `ReceiveBufferAvail=true` (:1089) — executes **only if
  `ReceiveInProgress`** (:1067-1092). DTR/port routing by CTRL bit 0x2000
  (:894-899). ⇒ **A TX-only game that waits on STAT&2 (RXRDY) without ever
  reading 0x1F801040 never sees RXRDY** — zenmai's exact stall, now
  source-proven with line numbers. A read arms the next byte's receive path
  (that is why BIOS-pad games work).
- **PCSX-Redux `src/core/sio.cc`**: a TX write runs `transmitData()` :179-199
  → `writePad()` :108 which on IDLE **sets `RX_FIFONOTEMPTY`** ("Transfer is
  Ready") :111 and polls the pad; every response byte is pushed to `m_rxFIFO`
  (:196, :246); JOY_DATA read pops it (`read8` :336-339). ⇒ **Redux drives
  the pad off the WRITE side — TX-only games work there.** (The manifest's
  stale "PCSX-Redux pad scan" note can be expected to succeed for
  zenmai-class games on that core — still needs a live re-test to claim.)
- Net: "direct SIO" is two different classes — **TX-only-wait-RXRDY**
  (zenmai: blocked on Beetle, fine on Redux/real HW) vs
  **read-per-byte full-duplex** (MSPSX/spicyjpeg, BIOS InitPAD handlers:
  expected to work on Beetle — UNVERIFIED prediction). The standalone-
  mednafen backend remains the clean fix for the first class only.

## 22.4 r23 intake shortlist (60/40 policy)

60% lightweight track (easy→hard):
1. **BuzzyBee** (MIT, 1-button flappy-like, BIOS pad class) — artifact held +
   hashed; boot = PS-EXE wrap + local license sectors; playbook §2-§5
   transfers 1:1; sensor = game-side input_held/btn mirror + position u16s.
2. **MSPSX** (Unlicense, turn-based minesweeper) — full source map in 22.3(a);
   its first boot doubles as the (e) prediction test for the read-per-byte
   SIO class; board/cursor/flags are RAM-localizable integers.
3. **psx-snake** (MIT, BIOS pad class) — needs a PSn00bSDK build first
   (psn00bsdk-builder UNVERIFIED); 4-file source, artifact UNVERIFIED until
   built.

40% baseline: MSX stage-loader lever (unchanged), air_hockey paddle anchor
(unchanged), Poy Poy clean retire (unchanged); optional new: **VoXide**
(GPL-2.0+CC0, artifact held) as the PSX-Minecraft sibling if a 40% slot frees
up. Build-gated keeps: psx-simple-pong, psx-pong (stuartaharrison). Watch:
mrbskb (sokoban — request a license upstream; top turn-based candidate if
granted). Nortis and every no-license repo stay out. All game bytes remain
local-only.
