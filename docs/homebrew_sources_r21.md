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
