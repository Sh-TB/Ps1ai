# Mission 2 Baseline Report (Issue #9 §1 — Deliverable A)

Date: 2026-10-24 · Audit scope: live repo state, environment, assets, issues, and the
*actually active* gameplay call chain. Historical report claims are treated as
hypotheses to reproduce, not proof (per §1 "Important").

## 1. Repository and environment

| Item | Value (verified this session) |
|---|---|
| HEAD | `dd392c471562f763818717941af35714f7cf364e` == `origin/main` (worklog: session-5 issue reports) |
| Dirty files | none (`git status` clean) |
| Python | 3.12.15 (`/home/z/.venv`), numpy + capstone importable |
| CPU / RAM / disk | 2 cores · 3.9 GB RAM (sandbox; mission budget says 16 GB — we record what is real) · 3.1 GB free |
| Emulator binary | `emu/mednafen_psx_libretro.so` (Beetle PSX libretro core) + full source tree `beetle-psx-libretro-df2b53b…` |
| Ghidra | absent (Java 21 present) — static-decompile path blocked |
| cmake | absent — PCSX-Redux / ps1recomp C++ builds blocked |
| Issues | #5 open/20c · #6 open/8c · #7 open/1c · #8 open/1c · #9 (this mission, created this session) |
| Test suite | **400 passed + 1 xfailed in 7.86 s** (reproduced this session) |

## 2. Game identity and legal assets

| Asset | Identity (verified) | Status |
|---|---|---|
| Metal Slug X (USA) | 104,315,904 B, sha256 `45cde149…`, volume `METALSLUGX`; EXE 622,592 B, md5 `c33d4b6f…`, SLUS_012.12 | user-owned disc image, local-only, never committed |
| Tetrade | MIT homebrew | accepted plugin #1 (Issue #8) |
| PSX-Minecraft | MIT homebrew, prebuilt release | accepted plugin #2 (session 5) |
| Nortis | no license file | boot+input proven, adoption license-blocked |
| Poy Poy (USA) / Trap Gunner (USA) | SLUS_004.86 / SLUS_006.79 | retail, local-only; boot+input proven, RAM mapping pending |
| FFT6 World of Ruin hack | 29.7 MB, sha256 `6fc04405…` | boots, pad causality live |
| Homebrew BIOS gap | OpenBIOS CDChecker loops on discs without license sectors | fix: `make_homebrew_lic.py` borrows 16 license sectors from the user's own MSX disc (local-only patch) |

## 3. Actually-active MSX gameplay call chain (source-inspected + runtime-verified)

Driver: `scripts/msx_ckpt_policy_pass.py` (the live policy runner used by all
session-4/5 passes). Verified flow:

```
issue4_controller.boot()            # beetle core in-process (1 boot per process — 2nd boot SEGFAULTs)
  └─ load_state(chopper_ckpt)       # px 810.3 savestate, ~1 s before the chopper/rain encounter
  └─ settle 2 frames; abort unless flags_word u32@0x0EE518 == 0xFF (in-mission gate)
  └─ per 60-frame chunk:
       px = px_of(mem)                              # RAM position (fx-scaled)
       scan = scan_entities(mem, px)                # ps1play/agent/combat.py:177 (contract rev 2)
       CombatPolicy.observe(px, advanced, intent)   # rolling memory / clamp state
       segs = CombatPolicy.decide(60, px, scan, grenades, hp)   # combat.py:299
       for s in segs: core.run(s["frames"], s["btns"])          # controller execution
       census.poll + hp/px re-read                  # outcome verification
       death guard → JSONL chunk record             # honest attrition ledger
```

Active policy branches confirmed in source (`combat.py`): `advance`,
`engage_short` (front stop-and-kill, ENGAGE_SHORT=200, ENGAGE_BUDGET=6),
`rear_check` (clamped-rear defense, REAR_ENGAGE=300, REAR_CHECK_MAX=6 → honest
disengagement), projectile dodge (two-sighting decreasing-height contract,
FALL_MAX_PER_CHUNK=1200), clamp_clear grenade escalation, hop/escape macros.
Modes that *exist but never fire* in the chopper-zone checkpoint context:
`REAR_ENGAGE_RUN` mid-run rear defense (constant 0) — flagged as
source-only/dead-by-configuration.

## 4. Reproduced baseline behaviour (checkpoint + budget)

Checkpoint `emu/ws/states/chopper_ckpt.state` (px 810.3, Beetle savestate,
local-only). Determinism evidence: three independent boots of the identical
policy pass (pass5/6/7, session 4) were **bit-identical** through the first
death. Known caveat: px-matched savestates do **not** pin script phase
(checkpoint-phase variance, D6) — the rain phase may or may not trigger.

Repeated outcome (4/4 passes, sessions 4–5): policy engages rear slot 14 at
chunk 25 (truck dx −37.5 hp 254), fires B+LEFT+Y, hp 254→254 (Y immune),
dies chunk 26 at the scroll clamp (px 1164) to a one-shot −291 truck ram.
Best MSX result so far: grenade-vs-armor damage 254→207 reproduced 3×,
score +700 with grenade counter 10→0 counter-verified; full kill blocked by
clamp/rear-zone geometry. Mission 1 **not** cleared — honest status.

## 5. Current best verified gameplay results (evidence levels)

| Result | Evidence level |
|---|---|
| Tetrade complete loop: title→START→menu→CROSS→Marathon, piece moves LEFT/RIGHT (diffs 21.75/0.62/0.54) | EMULATOR_TESTED (Issue #8) — full-game claim pending re-verification (M7) |
| PSX-Minecraft: PSXMCPlayPlugin, 250-chunk session, 232 verified move bursts, patrol vs fall-void halt; player struct live-mapped | EMULATOR_TESTED |
| MSX: grenade damages armor (3×), +700 score; rear_check first kill (+200, rear_resolved) | GAMEPLAY_VERIFIED (counter signals) |
| MSX: 24 verified faller dodges, 0 bogus after rev-2 contract | GAMEPLAY_VERIFIED |
| MSX Mission 1 clear | NOT ACHIEVED (D6/D7 blockers) |
| hp_pair_freeze survival 500 chunks (cheat) | diagnostic only, camera gate still locked — cheat ≠ gameplay |

## 6. Known limitations / unresolved (carried into mission WBS)

1. **D7 scroll clamp** = section state machine in RAM (function pointers
   0xCA268/0xCA2A0 flip, state 10→1; scroll word 0xEB598 pins at 0x048BFFFF);
   not a static camera constant. Death c26 @ px 1164 unresolved.
2. ENEMY.BIN loads verbatim at VA 0x8009C0E8 (0 mismatches, probe-verified);
   MISSION.BIN not resident during Mission 1 (BLOCKED).
3. Ghidra absent → static decompile blocked; cmake absent → PCSX-Redux/ps1recomp
   builds blocked; capstone OK.
4. Historical claims treated as hypotheses: Tetrade full-game loop (Issue #8)
   and session-1..3 MSX reports await current-HEAD reproduction (§10/§9 of the mission).
5. One beetle boot per OS process (in-process re-boot returns tainted state) —
   harness constraint, not a bug.

## 7. Exact commands

```
python3 -m pytest tests/ -x -q                 # 400 passed, 1 xfailed (7.86 s)
python3 scripts/msx_ckpt_policy_pass.py --chunks 60 --tag <tag>
python3 scripts/boot_test_psx_smallgames.py    # 5/5 boot sweep
```

Baseline verdict: **environment and assets sufficient for M3–M8**; the two
hard blockers (Ghidra, cmake) shape M2/M5 tool choices toward pure-Python and
prebuilt-binary paths.
