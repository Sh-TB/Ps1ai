# Coder-2 Mission — Final Report (four-category verdict)

Mission: "Fix enemy awareness and validate the agent on the simplest
PS1 games first" for the Metal Slug X agent. Everything below is
grounded in `docs/defect_ledger.md` (deliverable 1),
`docs/simple_games_ranking.md` (deliverable 2), the committed test
suite, and the local evidence trees. Labels: OFFLINE-TESTED =
deterministic unit/regression test against the real policy code;
LIVE-VERIFIED = real emulator run with per-chunk instrumentation.

Baseline: `c422606` -> `b283b19` + the reproducibility batch.
Suite: **384 passed + 1 xfailed** (0 regressions; the xfail is the
honest Nortis license-block marker).

## Category A — Fixed + unit-tested (offline, deterministic)

| Item | Evidence |
|---|---|
| D1 no-target fire rhythm -> nearest-threat selection + point-blank front engage | `tests/test_combat_policy.py`, `tests/test_msx_regression8.py::test_case1_front_enemy_engaged` |
| D3 map-end blindness -> DERIVED stage-end (X stalls while RIGHT held, no map constants) -> defensive clamp rear-clear | `test_case3_clamp_rear_defensive_clear`, `test_clamp_detection_and_clear`, `test_clamp_escalation_same_wall` |
| D4 fixed-RIGHT facing -> facing follows the selected threat's dx sign in every mode | `test_case1`, `test_case2`, `test_clamp_upfire_never_static` |
| D5 falling-bomb blindness -> two-stage classifier (h>64 scan label + policy-side DECREASING-height verification across sightings) | `test_case7_falling_shell_dodged_not_faced`, `test_case7b_static_elevated_object_never_dodged` |
| D8 static-elevated-scenery projectile false positive (found live, fixed) -> trajectory-memory dodge gate | `test_case7b` + live A/B (see B) |
| Case 5 unverified objects (hp outside 1..600 window / signed transients / dead) never become enemies | `test_case5_unverified_objects_never_enemies` |
| Case 6 target lost/destroyed -> engage lock released, re-acquisition allowed | `test_case6_target_lost_releases_lock` |
| Case 8 respawn/teleport >300 px -> stale wall/escalation/engage/pursuer state invalidated | `test_case8_respawn_invalidates_stale_state` |
| Case 2 enemy behind mid-run -> bounded `rear_check` (persist <=130 px across 4 chunks -> ONE turn+fire chunk, never a walk-toward, never an infinite turn) | `test_case2_rear_pursuer_turns_bounded`, `test_rear_gate_midrun_vs_clamp` |
| H1 MemoryView u16/u32 low-byte truncation (the historical "phantom camera gate") | `tests/test_memory_widths.py` (5 tests) |
| H4/H5 homebrew boot-loop + one-boot-per-process | `tests/test_config_contract.py` subprocess boot test |
| Tetrade full playthrough loop (category-1 game): 40 pieces, 11 verified line-clears, 0->218 score, natural game over, 2 bit-identical runs | `tests/test_tetrade_play.py` (13 offline tests), Issue #8 |

## Category B — Real-emulator-verified (live instrumented runs)

| Item | Live evidence |
|---|---|
| D2 direction correction when an enemy is BEHIND (the mission's headline acceptance criterion): `rear_check` fired in **4/4 independent boots** from `chopper_ckpt` — identical geometry (slot 14 armored truck x 1126.5, dx −37.5, hp 254, h 64), identical bounded buttons (`B+LEFT+Y` for one chunk), backbone resumed after | `evidence/heli_ladder/policy_pass{1,2,3,4}/trace.jsonl` + `report_policy_pass*.json`; runner `scripts/msx_ckpt_policy_pass.py` |
| D5 projectile dodges vs verified fallers only (post-D8 fix: 24 verified dodges / 0 static-object hops / 367 honest unverified flags in `combat_live4`) | `evidence/gif2_combat_live{2,3,4}/` |
| D9 death accounting: 13 deaths = 13 real episodes over 134 chunks (corpse-chunk inflation eliminated) | `evidence/gif2_combat_live4/` |
| Case 8 stale invalidation live: 15/11/37 resets per combat run | `gif2_combat_live{2,3,4}` policy_stats |
| D3/D4 live A/B: baseline 62 clamp chunks holding RIGHT never turning -> combat 0; clamp rear-clear kills 5901 vs 5000 incidental | `evidence/combat_before_after.json` + session-3 GIFs (uguu.se mirrors on Issue #5) |
| Helicopter bomb-phase mechanic (user directive, web-researched first): 10 movement patterns from ONE pre-encounter checkpoint, 10/10 web-prediction matches — hold-RIGHT was the only survivor; standing/prone die to shell blast; truck ram one-shots idlers | `evidence/heli_ladder/` (10 GIFs + reports), `docs/heli_ladder.md`; policy fix `test_clamp_upfire_never_static` |
| MSX savestate fast-iteration directive: `chopper_ckpt` (px 810.3, ~1 s before the chopper/rain encounter) drives both the 10-pattern ladder AND the policy-driven passes — no full-level replay | `emu/ws/states/chopper_ckpt.state` (local, never committed) |
| Category-1 simple game: Tetrade full playthrough (2 bit-identical real-emulator runs) | Issue #8 evidence, `docs/tetrade_playthrough.md` |
| Category-5 simple game: PSX-Minecraft booted + input-responsive through the shared core | `docs/simple_games_ranking.md` |

## Category C — Partially verified

| Item | What is proven | What is NOT |
|---|---|---|
| D2 kill follow-through vs armor | The turn+fire chunk fires with correct geometry, 4/4 reproducible | The Y-burst did NOT change the armored truck's hp (254->254 in all 4 passes); forward fire does not kill armor from that geometry — the grenade `clamp_clear` path is the proven kill mechanism. Survival after the turn also not yet achieved (one-shot −291 truck ram at chunk 26) |
| D5 classifier edge cases | Falling-shell rain signature + static-object exclusion live | 1-frame-fall shells undodgeable; paradrop soldiers match the falling signature mid-air; armed ground-creep (h==64) height-indistinguishable — all disclosed, never silently engaged |
| Checkpoint-based testing | Same-px savestate reproduces policy behaviour bit-stably (4/4) | px-matched savestates do NOT guarantee script-phase-matched outcomes (the rebuilt checkpoint's corridor script phase differs — the old ladder's only survivor now dies pinned at the truck wall). Ladder conclusions are checkpoint-phase-dependent |
| Category-2/3/4 simple games | MSX 8-case suite + heli ladder are the working enemy-awareness instruments | No licensed enemy-bearing PS1 homebrew found yet (see D) |

## Category D — Still blocked + why

| Item | Blocker |
|---|---|
| D6 mortar-rain-quiet reproduction | The kill->rain-quiet chain was proven once (session-2 causality x3) but re-runs kept the rain loud; boot-to-boot script-phase variance is the suspected cause (see the checkpoint-phase finding) |
| D7 section scroll clamp (~988 px camera / 1163 px player) | Section-completion condition unknown; handler region not resident at the lock; per mission scope deliberately NOT mixed with enemy awareness |
| Corridor/truck/clamp lethality | 13 real deaths per combat run concentrate at px 992-1164 (truck 992 / clamp 1164); the armored truck one-shots at the clamp; needs the grenade path tuned or a stage-completion unlock (D7) |
| Category-2/3/4 homebrew acquisition | Every checked candidate failed the legal-availability gate: Nortis no license, hello_pong 0 releases (verified 2026-10-23; Docker absent for source build), ButtonMasher/RPS no license+no releases+Windows-only toolchain, Half-Life PSX needs Valve assets (source-only by design) |
| Mission 1 stage clear | Blocked by D7; enemy-awareness work is validated up to the clamp instead |

## Acceptance criteria scorecard

| Mission acceptance criterion | Verdict |
|---|---|
| One simple game boots with a reproducible testable target | **MET** — Tetrade (category 1, full playthrough) + PSX-Minecraft (category 5) |
| Agent identifies targets from verified observations | **MET** — scan contract (hp window 1..600, kind enemy/projectile_air, height h) + case 5/7/7b exclusions, live-verified |
| Agent acts on relative position rather than blind advance | **MET** — front engage / rear_check / clamp_clear facing all follow dx sign; live 4/4 rear_check series |
| >=1 real emulator run confirms actions produce expected results | **MET** — combat_live2/3/4 + policy_pass1..4 + heli ladder + Tetrade runs |
| MSX tests prove enemy-behind triggers direction correction, not infinite forward movement | **MET** — offline case 2 + live 4/4 reproducible series (the previously owed item) |
| Existing tests stay green or regressions explained+fixed | **MET** — 384+1xfail, 0 regressions across all batches |

## Deliverable index (where everything lives)

1. Defect ledger: `docs/defect_ledger.md` (D1-D9 behavioural + H1-H5 historical, all labeled).
2. Simple-games matrix: `docs/simple_games_ranking.md` (+ `data/homebrew/manifest.json` v2).
3. First-game working test: Tetrade plugin + `tests/test_tetrade_play.py` (Issue #8).
4. Reusable loop implementation: `ps1play/agent/combat.py` (scan_entities contract rev 2 + CombatPolicy) + `ps1play/plugins/` contract v1 (zero core edits).
5. MSX regression: `tests/test_msx_regression8.py` (8 cases) + `tests/test_combat_policy.py` (17) + the live series above.
6. Commands: see `docs/defect_ledger.md` per-defect repro column; canonical run commands are
   `python -m pytest tests/ -q` (suite) and
   `python scripts/msx_ckpt_policy_pass.py --tag policy_passN --chunks 60` (live series).
7. This report.
8. Issue updates: #5 (session reports incl. comment 6358374338 + the reproducibility comment), #6 (5-game round + addenda), #7 (wagon sensor batch), #8 (Tetrade full playthrough).
