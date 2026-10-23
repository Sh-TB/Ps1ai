# Simple-PS1-Game Validation Matrix (Coder-2 mission, deliverable 2)

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
| 2 | Single player + single identifiable opponent | — none yet | no suitable licensed homebrew found; MSX itself is the current testbed |
| 3 | Directional movement + measurable hit/collision | — none yet | same gap |
| 4 | Reacting to moving obstacles/projectiles | — none yet | same gap; on MSX this is covered by the verified mortar-shell classifier (case 7) |
| 5 | Slightly richer world / generalization | **PSX-Minecraft** | BOOTED + INPUT_RESPONSIVE |

Honest gap statement: categories 2–4 (the enemy-capability ladder) have
NO homebrew representative. The MSX 8-case regression suite
(`tests/test_msx_regression8.py`) + the heli-ladder savestate harness
are today's only instruments for enemy awareness; a category-2/3/4
homebrew (a simple shooter with one identifiable enemy) remains the
highest-value acquisition target.

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

### 4. hello_pong — PENDING (artifact gated)
- Source/license: github.com/marconvcm/ps1_dev, MIT. Actions build
  SUCCEEDED but artifact download needs Actions:read (HTTP 401 with
  the current token); source build needs Docker+PSn00bSDK (absent).
- Would be the smallest input-latency probe once fetched. Cost: XS
  after unblock.

### 5. ButtonMasher / RPS-PS1-v1 — REJECTED
- No license, no releases (API re-verified 2026-10-22); source build
  requires the Windows-only 2012 PSXSDK toolchain — not buildable in
  this CPU-only sandbox.

## Retry/next-acquisition guidance

- Unblock hello_pong (Actions:read token) — cheapest next accept.
- Search for a MIT-licensed simple shooter/platformer homebrew with
  ONE enemy type (category 2/3): the current gap. Acceptance path is
  fixed: SHA-256 → license-patch locally → boot gate → input
  causality → THEN capability tests.
- One boot per process; license patching stays LOCAL-ONLY.
