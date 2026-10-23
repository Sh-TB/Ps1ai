# MSX Enemy-Awareness Defect Ledger (Coder-2 mission, deliverable 1)

Consolidated ledger of every defect reported or discovered for the
Metal Slug X agent, with the mission's evidence labels. Labels:
`CONFIRMED` (instrumented, reproducible), `TESTED` (fix verified by
test/live A/B), `OBSERVED` (user report / GIF evidence, no
instrumentation), `PARTIAL` (some scenarios fixed, others open),
`BLOCKED` (external cause), `SUPERSEDED` (earlier diagnosis replaced).

Baseline: commit `c422606` + this batch. Suite **384 passed + 1 xfailed**
(was 383+1 at `c422606`).

## Behavioral defects (user-reported gameplay)

| ID | Defect | Label | Instrument source | Root cause | Minimal fix | Repro test |
|----|--------|-------|-------------------|------------|-------------|------------|
| D1 | Fires/advances on a fixed rhythm, walks THROUGH enemies without killing them | `CONFIRMED` (probe0: 400f unarmed walk scored 0, took damage, enemies passed) | `scripts/probe0_addresses.py`, `evidence/probe0/` | RoutePolicy v1 read NO entity data; fire cadence was purely time-based | `ps1play/agent/combat.py` CombatPolicy: nearest-threat selection + point-blank front engage (≤45 px) + forward fire bursts on the run; per-slot engage budget | `tests/test_combat_policy.py::test_front_enemy_faces_right`, `tests/test_msx_regression8.py::test_case1_front_enemy_engaged` |
| D2 | Dies with enemies BEHIND (the "jeep behind" geometry) | `CONFIRMED` (4/4 baseline in-game deaths at the clamp with rear enemies dx −54…−93) → `PARTIAL` (mid-run fix live-OBSERVED once; clamp fix live-proven) | `scripts/gif_run2_capture.py` death_geometry traces; **live: `evidence/heli_ladder/policy_pass1` chunk 25** | Forward-only policy; rear threats never selected mid-run | Clamp: defensive LEFT rear-clear (live-proven, 5901 clamp kills). Mid-run: bounded rear_check — a pursuer persisting ≤130 px across 4 chunks earns ONE turn+fire chunk (6f LEFT tap → standing LEFT fire → resume). **Live status: fired once in the chopper-zone pass (rear ground enemy slot 14 dx −38 persisting after clamp_clear release → LEFT+Y+B chunk) = live-OBSERVED; a reproducible live series is still owed** | `test_case2_rear_pursuer_turns_bounded`, `test_rear_gate_midrun_vs_clamp` |
| D3 | Reaches the map/section end and keeps going; never turns back to clear rear (jeep/grenadier) | `CONFIRMED` (62 clamp chunks held RIGHT, never turned) → `TESTED` | session-3 A/B JSONL (`evidence/combat_before_after.json`, local) | No stage-end signal existed; movement intent never re-checked against progress | DERIVED stage-end: player X stalls while RIGHT intent held (2 chunks) → `clamp_clear` (LEFT fire / UP+LEFT moving fire / hops / grenades / escalation walk-back 180/300/450). No map constants | `test_case3_clamp_rear_defensive_clear`, `test_clamp_detection_and_clear`, `test_clamp_escalation_same_wall` |
| D4 | Never faces the nearest threat — fixed-RIGHT facing, binary forward/back | `CONFIRMED` → `TESTED` | session-3 A/B | Facing hard-wired to traversal direction | Engage/rear_check/clamp_clear face the selected threat's dx sign; up-fire segments always move (heli-ladder pattern 7 fix) | `test_case1`, `test_case2`, `test_clamp_upfire_never_static` |
| D5 | Chopper directly overhead / falling bombs unanswered | `OBSERVED` (user GIF report) → `TESTED` (classifier + dodge live-verified in 3 instrumented runs) | heli-ladder slot trace; **live: `gif2_combat_live2/3/4` — dodge stats 33→12→24 with 165/367 unverified flags, `policy_pass1` corridor dodges with fall_near 1–2** | No projectile concept: falling shells occupied entity slots and were read as if ground enemies (their HP field is a fuse/phase tag 194/92/73/42, 352→101) | Two-stage classifier: scan labels h>64 `projectile_air`; the policy additionally verifies the FALLING trajectory across sightings before dodging (see D8). Never an engage target; verified faller within 60 px → hop. **Disclosed limits: 1-frame-fall shells undodgeable (hop cadence + movement are the defense); paradrop soldiers match the falling signature mid-air; armed ground-creep (h==64) height-indistinguishable** | `test_case7_falling_shell_dodged_not_faced`, `test_case7b_static_elevated_object_never_dodged` |
| D6 | Mortar-rain silence after the mosque kill reproduced only once | `OBSERVED` → `BLOCKED` (reproduction) | session-2 faller-signature causality ×3 vs `db21e24` session (rain stayed loud) | Kill → rain-quiet chain real but boot-to-boot variance unresolved | Open: re-run the mosque-volley probe with the fixed u32 reader | — |
| D7 | Section scroll clamp at ~988 px camera / 1163 px player — stage-completion condition unknown | `BLOCKED` (independent root blocker, deliberately NOT mixed with enemy awareness per mission scope) | session-2 forensics (handler region 0x800B9F5C+ not resident at lock; ROOT chain generic); live4 again died 13× at the corridor (truck 992 / clamp 1164) | Unknown section-completion condition | Separate investigation (mission rule: scroll-clamp ≠ enemy-awareness evidence either way) | — |
| D8 | Projectile classifier false positive: STATIC elevated objects (elevated scenery) labelled `projectile_air` → dodge hops burned far from any shell; symmetric half of case 5 (unknown must not become projectile either) | `CONFIRMED` (live `combat_live2`: slot 7 at x=264.0, height AND hp constant for 16 chunks, 33 dodge hops incl. the empty early village) → `TESTED` (fix live: `combat_live4` 24 verified dodges / 0 static-object hops, 367 honest unverified flags) | `evidence/gif2_combat_live2/trace_combat_live2.jsonl` chunks 0–30 slot series | one-shot h>64 classification had no trajectory memory | two-stage: scan carries `h`; policy requires height DECREASING across sightings of the same slot (rain signature at chunk granularity) before dodging; static/rising/first-sighting = unverified (never engaged, never dodged, counted); height memory cleared on stale invalidation; `FALL_MAX_PER_CHUNK=1200` guards slot redefinition | `test_case7b_static_elevated_object_never_dodged` |
| D9 | Runner death-accounting inflation: corpse chunks (px sentinel 0.0, hp 0) of ONE death counted as new deaths (live `combat_live2` deaths 31–34; the 1UP=0 corpse passes flags/gate checks) | `CONFIRMED` (live) → `TESTED` (live `combat_live4`: 13 deaths = 13 episodes over 134 chunks, 0 inflation) | `gif2_combat_live2/3` hp_zero px=0.0 repeat chains vs `combat_live4` clean series | death trigger was level-based, not transition-based | death-episode guard in `gif_run2_capture.py`: count only the episode start; episode exit requires in_mission + flags active + hp>0 + sane px; corpse chunks wait+re-gate without counting | manual A/B across the three live traces (tool change, no unit test — runner is diagnostic tooling) |

## Tooling / historical defects (superseded diagnoses kept for honesty)

| ID | Defect | Label | Root cause | Fix | Repro test |
|----|--------|-------|------------|-----|------------|
| H1 | `MemoryView.u16/u32` truncated every read to the low byte (numpy uint8 << 8 wraps) — the entire historical "prog/camera locked at 139" series was `camera_px & 0xFF` | `CONFIRMED` → `TESTED` | numpy dtype wrap in `ps1play/core/memory.py` | int() casts before shifts | `tests/test_memory_widths.py` (5 tests) |
| H2 | "Phantom camera gate" (camera allegedly locked while player moved) | `SUPERSEDED` | Was H1's truncation artifact | H1 fix | — |
| H3 | Published GameShark lives/ammo/time/invuln codes fail on this revision | `CONFIRMED` → `TESTED` (structurally invalid: call-NOP/epilogue-NOP/return-address corruption; only the bombs `sb`-NOP is sound) | Revision split (CheatCC/beta set ≠ retail binary) | Only verified codes used; invuln dropped honestly | `scripts/analyze_patch_sites.py` audit |
| H4 | Unpatched homebrew discs boot-loop in OpenBIOS CDChecker | `CONFIRMED` → `TESTED` | Empty license sectors | Copy the 16 license sectors from the user's own MSX disc into LOCAL copies only (`scripts/make_homebrew_lic.py`) | `tests/test_config_contract.py` subprocess boot test |
| H5 | One-boot-per-process constraint (2nd in-process boot returns stale state) | `CONFIRMED` → `TESTED` | Global state in the core | Subprocess isolation per boot | suite boot tests |

## Labels of THIS batch (fix honesty, mission Phase 5)

- `IMPLEMENTED` + offline `TESTED`: mid-run rear_check (D2), projectile
  classification + dodge (D5), respawn stale-invalidation (case 8),
  target-lost release (case 6), unverified-object exclusion (case 5).
- LIVE batch 2026-10-23 (this session, 4 runs + checkpoint pass):
  * D8 CONFIRMED live → fixed → live-TESTED (`combat_live2` → `live4`).
  * D9 CONFIRMED live → fixed → live-TESTED (death accounting).
  * D5 dodge live-TESTED (verified-faller dodges only).
  * D2 rear_check live-OBSERVED once (`policy_pass1` chunk 25, correct
    geometry + buttons); reproducible live series still owed.
  * Case 8 stale invalidation live (15/11/37 resets per run).
  * Checkpoint-phase variance DISCOVERED: the rebuilt `chopper_ckpt`
    (same px 810.3) sits at a different corridor script phase — the
    old ladder's only survivor (walk_right) now dies pinned at the
    truck wall (px 992). px-matched savestates do NOT guarantee
    script-phase-matched outcomes; ladder conclusions are
    checkpoint-phase-dependent (consistent with D6 variance).
  * The corridor/truck/clamp lethality (D6/D7) remains the open root
    blocker — 13 real deaths per run concentrate at px 992–1164.
