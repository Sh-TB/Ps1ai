# Simple-PS1-Game Validation Matrix (Coder-2 mission, deliverable 2)

> **SUPERSEDED (r21, 2026-10-27):** the authoritative source-linked
> easy→hard ladder for lightweight PSX games now lives in
> **`docs/homebrew_sources_r21.md`** (adds verified source links, 4 new
> sourced candidates — MSPSX / BKBS_PSX / psx-pong / psx-flappy-bird — and
> the r22 60/40 intake shortlist). Everything below is the older ranking,
> kept for history; statuses older than r20 may be stale.

Ranked candidate list for "validate the agent on the simplest PS1
games first". Selection rules from the mission: simplicity, fast boot,
low resource use, easily verifiable goals — NOT popularity. Every
binary is fetched + SHA-256-verified (`scripts/fetch_homebrew.py`),
booted through the SHARED beetle core + OpenBIOS, and license-patched
locally from the user's own retail disc (`scripts/make_homebrew_lic.py`)
because unpatched homebrew discs boot-loop in the OpenBIOS CDChecker
(defect H4, `data/homebrew/manifest.json`). Game binaries are never
committed.

## Mission capability categories vs. current coverage

| # | Capability category | Representative today | Status |
|---|--------------------|----------------------|--------|
| 1 | Minimal movement + deterministic goal | **Tetrade** | FULL PLAYTHROUGH (Issue #8) |
| 2 | Single player + single identifiable opponent | **Poy Poy (USA)** — BOOTED candidate | boot + input causality VERIFIED (owner source); RAM mapping pending |
| 3 | Directional movement + measurable hit/collision | **Trap Gunner (USA)** — BOOTED candidate | boot + input causality VERIFIED (owner source); RAM mapping pending |
| 4 | Reacting to moving obstacles/projectiles | Trap Gunner (trap projectiles) + MSX shell classifier | candidate booted; MSX coverage live-TESTED |
| 5 | Slightly richer world / generalization | **PSX-Minecraft** | BOOTED + INPUT_RESPONSIVE |

Honest gap statement (updated 2026-10-24): categories 2–4 now have
BOOT-VERIFIED retail candidates from the owner-supplied source (Poy
Poy, Trap Gunner — discs local-only, never committed), but NO RAM
mapping yet: the entity-table reverse-engineering campaign (probe →
causality → contract) is the acceptance gate before either becomes a
capability representative. The MSX 8-case regression suite remains
today's only instrument for enemy awareness.

## Ranked list

### 1. Tetrade — ACCEPTED, FULL PLAYTHROUGH
- Source/license: github.com/Logan-Campbell/Tetrade, MIT (LICENSE file
  in repo), release v1.0.
- Binary: TETRADE_PSX.bin 3,196,368 B, sha256 `2f41feba…6eaf8`
  (verified). Cue generated locally; license sectors patched into a
  LOCAL copy.
- Controls/goal: D-pad moves the falling tetrimino, CROSS confirms
  menus; score 200×level per line clear; verifiable state (matrix,
  piece, next-piece, score) localized by INPUT CAUSALITY at
  base 0x1FECA0 (source-layout-verified live).
- Why simplest: single screen, deterministic rules, MIT source
  (main.c read source-first), no enemies, instant boot.
- Verified capability: category 1 — and the FIRST complete
  closed-loop playthrough by this agent: 40 pieces, 11 singles
  verified per-increment, score 0→218, level-up, natural game over,
  CONTINUE refused, 2 bit-identical runs (Issue #8).
- Cost: XS (release binary + 74-byte cue + license patch).

### 2. PSX-Minecraft — ACCEPTED, booted + responsive (no clear goal)
- Source/license: github.com/EngineersBox/PSX-Minecraft, MIT,
  release infdev_2025_04_18.
- Binary: release tar 695,797 B sha256 `45b076ca…dd74` → PSXMC.bin
  329,280 B, BOOT=cdrom:\PSXMC.exe.
- Why here: boots to a real world render (HUD/terrain/hotbar/hearts),
  input-causality-positive (cross/left deltas 49.8/54.4 mean-abs).
  Second accepted game (A6 proven twice through the shared core).
- Limits: sandbox without a discrete verifiable goal; attract-loop
  trigger UNKNOWN; no plugin beyond GenericPlugin yet. Good for
  boot/stability/generalization, NOT for enemy-capability claims.
- Cost: S.

### 3. Nortis — LOCAL TEST ONLY, license-blocked
- Source: github.com/jbreckmckye/nortis. **No LICENSE file anywhere**
  (API re-verified 2026-10-22: 88 files, 0 license files) —
  redistribution rights unverified; integration refused.
- Local evidence (binary never committed): license-patched image
  BOOTS to NOTRIS title, START → gameplay HUD, falling tetromino +
  next-piece preview; 35,270-frame play-test with savestate-twin A/B
  controls (OBSERVED-CAUSAL).
- Value: proves the shared core on a third title; unusable in the
  committed matrix until licensing is resolved. Cost: XS (local).

### 4. hello_pong — BLOCKED (no release artifact exists; build chain absent)
- Source/license: github.com/marconvcm/ps1_dev, MIT. Re-verified
  2026-10-23 via API: **0 releases** (the CI workflow publishes
  artifacts only on tags — none were ever pushed; the earlier
  Actions:read HTTP 401 was not the binding constraint). Source build
  requires Docker+PSn00bSDK; Docker confirmed absent from this
  sandbox (`which docker podman` → nothing, no root).
- Would be the smallest input-latency probe once unblocked (ask the
  maintainer to tag a release, or provide Docker). Cost: XS after
  unblock.

### 5. ButtonMasher / RPS-PS1-v1 — REJECTED
- No license, no releases (API re-verified 2026-10-22); source build
  requires the Windows-only 2012 PSXSDK toolchain — not buildable in
  this CPU-only sandbox.

### 6. Poy Poy (USA) — BOOTED + INPUT-CAUSAL (owner-supplied source)
- Source: the owner-supplied ROM archive (romsfun mirror, the same
  source that produced the byte-identical MSX disc, session 12) —
  retail disc, SCEA license sectors present, SLUS_004.86. Disc
  binaries local-only, NEVER committed (same policy as MSX).
- Binary: `Poy Poy (USA).zip` 166,541,778 B sha256 `76f0784b…` →
  bin/cue; bin md5 `5c1d3783eec9e43d6ca277ae643f333f`.
- Boot gate: BOOTED (SLUS-00486 detected, RAM 2MB); first non-black
  frame @60f; title renders (Konami 1997); START → title transition
  mean-abs diff **181.4** (screenshots in local evidence).
- Agent relevance: arena battle vs 3 opposing players throwing
  boulders — a natural category-② (single identifiable opponent)
  and ④ (dodging thrown projectiles) candidate. Next gate: entity-
  table RAM mapping via the probe→causality contract used on MSX.
- Tool: `scripts/romsfun_fetch.py` (k_get_download referer-path flow,
  Range streaming, re-mint resume; guest cap ≈51 MB per signed URL).

### 7. Trap Gunner (USA) — BOOTED + INPUT-CAUSAL (owner-supplied source)
- Source: same owner-supplied archive; retail disc, SLUS_006.79,
  license sectors present. Local-only, never committed.
- Binary: `Trap Gunner (USA).zip` 420,042,250 B sha256 `644aac0b…` →
  bin/cue; bin md5 `4acc0cc9bf96dc12623d4bb031caf159`.
- Boot gate: BOOTED; title renders (Atlus 1998); START → **512-wide
  mode switch** (320×240 → 512×240) with diff 56.6 — real state
  transition, input causality proven.
- Agent relevance: grid-based trap placement vs an opposing trap
  setter + trap projectiles — category ③④ candidate with discrete
  tactics (rule-based friendly). Same next gate: RAM mapping.

## Retry/next-acquisition guidance

- Unblock hello_pong (Actions:read token) — cheapest next accept.
- Search for a MIT-licensed simple shooter/platformer homebrew with
  ONE enemy type (category 2/3): the current gap. Acceptance path is
  fixed: SHA-256 → license-patch locally → boot gate → input
  causality → THEN capability tests.
- One boot per process; license patching stays LOCAL-ONLY.

---

## Session-5 batch (2026-10-24): the owner directive "test the small
## games we have" — every locally-held <30 MB title exercised

| # | Game | This session's state | Evidence |
|---|------|--------------------|----------|
| 1 | Tetrade (MIT) | COMPLETE PLUGIN + full playthrough (Issue #8) — unchanged, re-booted in the sweep | sweep BOOTED, pad live |
| 2 | PSX-Minecraft (MIT) | **COMPLETE PLUGIN (`PSXMCPlayPlugin`)** — 250-chunk play session, 232 verified move bursts, health/air telemetry live, world-entry + fall-guard + dig experiment | `psxmc_*` evidence dir |
| 3 | Nortis (no license) | PLAYED locally (license-blocked for distribution, status unchanged): boots straight into its field; 188-rule-input autoplay, 67 field-active chunks, 1 score-region change captured | `nortis_play/autoplay_report.json` |
| 4 | Poy Poy (USA) | PLUGIN (`PoyPoyPlugin`, menu-reach scope): title→START→MODE SELECT path data-frozen; cursor nav verified; match-entry confirm button NOT identified (X/O/START/SQ/TR tested, idle-timeout to title suspected) — honest BLOCKED-by-discovery | `poypoy_menu*/` probes |
| 5 | Trap Gunner (USA) | Menu walk mapped: boot→512-wide title→menus→TUTORIAL MOVIE submenu reached; main-game entry not yet isolated | `trapgunner_menu/` |
| 6 | FFT6 — World of Ruin (hack, NEW <50 MB fetch) | Downloaded 29,734,169 B (sha256 `6fc04405…`), boots (license sectors intact, BOOT=SCUS_942.21), pad live, X/LEFT causal (7.1) — boot-verified candidate, RAM mapping pending | `fft6_*` evidence |

Pad-class finding (probe5 matrix, decisive): the beetle DIGITAL pad
(id 0x41) delivers ALL 16 button bits — including L2/R2/L3/R3 — read
at the game's own `input` buffer (PSXMC map symbol). The host gained
an opt-in `INPUT_DEVICE` capability (contract v1, default JOYPAD
unchanged), but beetle 0.9.44.1's ANALOG mode is input-DEAD
(A/B: digital d_z=844038/d_yaw=614400 vs analog all-zero), so no
plugin uses it today.
