# MSX Enemy-Awareness Defect Ledger (Coder-2 mission, deliverable 1)

Consolidated ledger of every defect reported or discovered for the
Metal Slug X agent, with the mission's evidence labels. Labels:
`CONFIRMED` (instrumented, reproducible), `TESTED` (fix verified by
test/live A/B), `OBSERVED` (user report / GIF evidence, no
instrumentation), `PARTIAL` (some scenarios fixed, others open),
`BLOCKED` (external cause), `SUPERSEDED` (earlier diagnosis replaced).

Baseline: commit `afaee9b` + this ledger's fix batch. Suite
**383 passed + 1 xfailed** (was 375+1 at `afaee9b`).

## Behavioral defects (user-reported gameplay)

| ID | Defect | Label | Instrument source | Root cause | Minimal fix | Repro test |
|----|--------|-------|-------------------|------------|-------------|------------|
| D1 | Fires/advances on a fixed rhythm, walks THROUGH enemies without killing them | `CONFIRMED` (probe0: 400f unarmed walk scored 0, took damage, enemies passed) | `scripts/probe0_addresses.py`, `evidence/probe0/` | RoutePolicy v1 read NO entity data; fire cadence was purely time-based | `ps1play/agent/combat.py` CombatPolicy: nearest-threat selection + point-blank front engage (≤45 px) + forward fire bursts on the run; per-slot engage budget | `tests/test_combat_policy.py::test_front_enemy_faces_right`, `tests/test_msx_regression8.py::test_case1_front_enemy_engaged` |
| D2 | Dies with enemies BEHIND (the "jeep behind" geometry) | `CONFIRMED` (4/4 baseline in-game deaths at the clamp with rear enemies dx −54…−93) → `PARTIAL` | `scripts/gif_run2_capture.py` death_geometry traces | Forward-only policy; rear threats never selected mid-run | Clamp: defensive LEFT rear-clear (live-proven, 5901 clamp kills). Mid-run: NEW bounded rear_check — a pursuer persisting ≤130 px across 4 chunks earns ONE turn+fire chunk (6f LEFT tap → standing LEFT fire → resume). **Offline `TESTED` only; live A/B pending — do not claim live** | `test_case2_rear_pursuer_turns_bounded`, `test_rear_gate_midrun_vs_clamp` |
| D3 | Reaches the map/section end and keeps going; never turns back to clear rear (jeep/grenadier) | `CONFIRMED` (62 clamp chunks held RIGHT, never turned) → `TESTED` | session-3 A/B JSONL (`evidence/combat_before_after.json`, local) | No stage-end signal existed; movement intent never re-checked against progress | DERIVED stage-end: player X stalls while RIGHT intent held (2 chunks) → `clamp_clear` (LEFT fire / UP+LEFT moving fire / hops / grenades / escalation walk-back 180/300/450). No map constants | `test_case3_clamp_rear_defensive_clear`, `test_clamp_detection_and_clear`, `test_clamp_escalation_same_wall` |
| D4 | Never faces the nearest threat — fixed-RIGHT facing, binary forward/back | `CONFIRMED` → `TESTED` | session-3 A/B | Facing hard-wired to traversal direction | Engage/rear_check/clamp_clear face the selected threat's dx sign; up-fire segments always move (heli-ladder pattern 7 fix) | `test_case1`, `test_case2`, `test_clamp_upfire_never_static` |
| D5 | Chopper directly overhead / falling bombs unanswered | `OBSERVED` (user GIF report) + `PARTIAL` | heli-ladder slot trace (`evidence/heli_ladder/`); session-2 mortar decode | No projectile concept: falling shells occupied entity slots and were read as if ground enemies (their HP field is a fuse/phase tag 194/92/73/42, 352→101) | VERIFIED classifier: height word u16 @slot+0x7E > ground contact 64 → `projectile_air`, never an engage target; airborne shell within 60 px → immediate hop. **Disclosed limit: the ARMED ground-creep phase (h==64) is height-indistinguishable — hop cadence + movement remain the defense** | `test_case7_falling_shell_dodged_not_faced`; live dodge validation pending |
| D6 | Mortar-rain silence after the mosque kill reproduced only once | `OBSERVED` → `BLOCKED` (reproduction) | session-2 faller-signature causality ×3 vs `db21e24` session (rain stayed loud) | Kill → rain-quiet chain real but boot-to-boot variance unresolved | Open: re-run the mosque-volley probe with the fixed u32 reader | — |
| D7 | Section scroll clamp at ~988 px camera / 1163 px player — stage-completion condition unknown | `BLOCKED` (independent root blocker, deliberately NOT mixed with enemy awareness per mission scope) | session-2 forensics (handler region 0x800B9F5C+ not resident at lock; ROOT chain generic) | Unknown section-completion condition | Separate investigation (mission rule: scroll-clamp ≠ enemy-awareness evidence either way) | — |

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
- Live-emulator status of the same items: **NOT YET RE-RUN** — the
  offline suite is deterministic; the live A/B rerun is the declared
  next experiment. No live claim is made here.
- Existing green behavior untouched: 375 previous tests still pass.
