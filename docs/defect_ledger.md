# MSX Enemy-Awareness Defect Ledger (Coder-2 mission, deliverable 1)

Consolidated ledger of every defect reported or discovered for the
Metal Slug X agent, with the mission's evidence labels. Labels:
`CONFIRMED` (instrumented, reproducible), `TESTED` (fix verified by
test/live A/B), `OBSERVED` (user report / GIF evidence, no
instrumentation), `PARTIAL` (some scenarios fixed, others open),
`BLOCKED` (external cause), `SUPERSEDED` (earlier diagnosis replaced).

Baseline: commit `b283b19` + the reproducibility batch. Suite **389 passed + 1 xfailed**
(was 384+1 at the reproducibility batch, 383+1 at `c422606`).

## Behavioral defects (user-reported gameplay)

| ID | Defect | Label | Instrument source | Root cause | Minimal fix | Repro test |
|----|--------|-------|-------------------|------------|-------------|------------|
| D1 | Fires/advances on a fixed rhythm, walks THROUGH enemies without killing them | `CONFIRMED` (probe0: 400f unarmed walk scored 0, took damage, enemies passed) → **session-4 `TESTED` (stop-and-kill + fire discipline)**: user re-reported pass-throughs + "aimless bursts"; ENGAGE_SHORT 45→200 (front soldier inside 200px STOPS the run: standing aimed fire, budget-bounded) + advance fire gated on a real ahead target (FIRE_ON cadence without a target = removed; `advance_silent` counter). Live pass5/6/7: 14/15 advance chunks silent, 5 engage chunks each killed its soldier (+100 score per engage) | `scripts/probe0_addresses.py`, `evidence/probe0/`; live `evidence/heli_ladder/policy_pass{5,6,7}/trace.jsonl` | RoutePolicy v1 read NO entity data; fire cadence was purely time-based; v6 still sprint-past soldiers at 60-150px and fired into empty air | `ps1play/agent/combat.py` CombatPolicy: nearest-threat selection + stop-and-kill window 200px + target-gated on-the-run fire + cluster-gated advance grenades | `tests/test_combat_policy.py::test_midrange_front_enemy_stops_and_engages`, `::test_fire_discipline_silent_when_no_target`, `::test_fire_discipline_fires_only_vs_ahead_target`, `tests/test_msx_regression8.py::test_case1_front_enemy_engaged` |
| D2 | Dies with enemies BEHIND (the "jeep behind" geometry) | `CONFIRMED` (4/4 baseline in-game deaths at the clamp with rear enemies dx −54…−93) → **`TESTED` (direction correction) / `PARTIAL` (kill follow-through)** — the owed reproducible live series is DELIVERED: `policy_pass1..4`, four independent boots from the same `chopper_ckpt`, **4/4 identical rear_check firings at chunk 25** (slot 14 armored truck x 1126.5, dx −37.5, hp 254, h 64 → ONE `B+LEFT+Y` turn+fire chunk, then the backbone resumes; never a walk-toward) | `scripts/msx_ckpt_policy_pass.py`; `evidence/heli_ladder/policy_pass{1,2,3,4}/trace.jsonl` + `report_policy_pass*.json` | Forward-only policy; rear threats never selected mid-run | Clamp: defensive LEFT rear-clear (live-proven, 5901 clamp kills). Mid-run: bounded rear_check — a pursuer persisting ≤130 px across 4 chunks earns a turn+fire chunk (6f LEFT tap → standing LEFT fire → resume); **session-4: the check is now a FOLLOW-THROUGH campaign** (repeat checks while the pursuer persists; hp-unchanged pursuer → grenade escalation after REAR_GRENADE_AFTER checks; REAR_CHECK_MAX → honest disengagement; vanished pursuer → `rear_resolved`). **Session-4 live kill evidence: pass5/6/7 c13 rear fire killed the rear soldiers (+200 score, slot vanished, `rear_resolved: 1`) — kill follow-through WORKS vs soft pursuers; the armored truck still resists Y-fire (grenade escalation unit-tested, live-vs-truck owed)** | `test_case2_rear_pursuer_turns_bounded`, `test_rear_gate_midrun_vs_clamp`, `test_rear_followthrough_escalates_to_grenade`, `test_rear_followthrough_gives_up_honestly` |
| D3 | Reaches the map/section end and keeps going; never turns back to clear rear (jeep/grenadier) | `CONFIRMED` (62 clamp chunks held RIGHT, never turned) → `TESTED` | session-3 A/B JSONL (`evidence/combat_before_after.json`, local) | No stage-end signal existed; movement intent never re-checked against progress | DERIVED stage-end: player X stalls while RIGHT intent held (2 chunks) → `clamp_clear` (LEFT fire / UP+LEFT moving fire / hops / grenades / escalation walk-back 180/300/450). No map constants | `test_case3_clamp_rear_defensive_clear`, `test_clamp_detection_and_clear`, `test_clamp_escalation_same_wall` |
| D4 | Never faces the nearest threat — fixed-RIGHT facing, binary forward/back | `CONFIRMED` → `TESTED` | session-3 A/B | Facing hard-wired to traversal direction | Engage/rear_check/clamp_clear face the selected threat's dx sign; up-fire segments always move (heli-ladder pattern 7 fix) | `test_case1`, `test_case2`, `test_clamp_upfire_never_static` |
| D5 | Chopper directly overhead / falling bombs unanswered | `OBSERVED` (user GIF report) → `TESTED` (classifier + dodge live-verified in 3 instrumented runs) → **session-4 `TESTED` (MOVING dodge)**: user directive "you're jumping up — you must CHANGE POSITION": the verified-faller dodge is now hop + lateral escape AWAY from the shell (faller ahead → LEFT+B, behind → RIGHT+B), never a straight-up in-place hop; frame-level direction offline-TESTED, live proj_dodge 3 events in pass5/6/7 (chunk-union granularity disclosed: the 13 dodge frames are subsumed in chunk btns) | heli-ladder slot trace; live `gif2_combat_live2/3/4`; `evidence/heli_ladder/policy_pass{5,6,7}/` | No projectile concept: falling shells occupied entity slots and were read as if ground enemies (their HP field is a fuse/phase tag 194/92/73/42, 352→101) | Two-stage classifier: scan labels h>64 `projectile_air`; the policy additionally verifies the FALLING trajectory across sightings before dodging (see D8). Never an engage target; verified faller within 60 px → MOVING dodge (hop + escape). **Disclosed limits: 1-frame-fall shells undodgeable (hop cadence + corridor movement are the defense); paradrop soldiers match the falling signature mid-air; armed ground-creep (h==64) height-indistinguishable** | `test_case7_falling_shell_dodged_not_faced`, `test_case7b_static_elevated_object_never_dodged`, `test_moving_dodge_escapes_away_from_faller` |
| D6 | Mortar-rain silence after the mosque kill reproduced only once | `OBSERVED` → `BLOCKED` (reproduction) → `PARTIAL` (2026-10-24: the +800&0x20 mosque-kill signature itself REPRODUCED cleanly from `clamp0` in one volley campaign — score_delta exactly 800; post-kill faller poll = 0 events but a single poll, NOT the sustained quiet proof) | session-2 faller-signature causality ×3 vs `db21e24` session; **2026-10-24: `mosque_gate/report.json` (kill arm: killed=True, score_delta=800, rain_events=43 during lob, rain_after_kill=0)** | Kill → rain-quiet chain real but boot-to-boot variance unresolved | The lob campaign (`msx_mosque_gate_test.py`) is now a cheap reliable kill reproduction from `clamp0`; sustained post-kill faller window is the remaining measurement | — |
| D7 | Section scroll clamp at ~988 px camera / 1163 px player — stage-completion condition unknown | `BLOCKED` (independent root blocker, deliberately NOT mixed with enemy awareness per mission scope) — **2026-10-24 forensics sharpened it: the pin is a section state-machine behaviour, NOT a static limit constant (see `docs/clamp_pin_forensics.md`)**: no camera stall at 988 exists (the "988/992" figures are the checkpoint respawn px 992 + truck pin); the scroll word `0xEB598` follows the player and pins at 0x048BFFFF; at pin arrival player-struct function pointers flip (0xCA268/0xCA2A0, state 10→1); the u16-1164 candidate @0x8DBF8 poke is NEGATIVE; clean 3-arm matrix: pin stable / shallow-left no-op / death-respawn = 119-episode truck-kill loop at the 992 respawn | clampdiff1/2/3 full-RAM diffs, `scan_eb598_refs.py` (8 copy sites), `msx_limit_poke.py` (3 arms), `msx_pin_matrix.py` (P/R/L), `msx_deep_left.py` | Unknown section-completion condition; no static limit in RAM; enforcement inside the section handler (not resident at lock) + overlay pointers | Next: trace the flipped handlers 0x80032d28 / 0x800b83e0 + the camera-copy source struct; truck-phase-aware deep-left retry; one clean probe of the apparent mission-restart path | — |
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
- SESSION-4 batch 2026-10-24 (user feedback round 3):
  * (a) FIRE DISCIPLINE: advance fire only vs a real ahead target;
    advance grenades cluster-gated. `advance_silent` 14/15 live.
  * (b) STOP-AND-KILL: ENGAGE_SHORT 45→200 — front soldiers are no
    longer run past; live: 5 engage chunks, +100 score each.
  * (c) MOVING DODGE: verified faller → hop + escape AWAY from it.
  * (d) REAR KILL FOLLOW-THROUGH: repeat checks vs a persisting
    pursuer; hp-UNCHANGED pursuer → grenades after
    REAR_GRENADE_AFTER checks; REAR_CHECK_MAX then honest
    disengagement (`rear_gaveup`); vanished pursuer →
    `rear_resolved`. LIVE KILL EVIDENCE: pass5/6/7 c13 rear_check
    fired LEFT+Y at rear soldiers (hp 157/133) → +200 score across
    the chunk, the pursuer slot vanished, `rear_resolved: 1` — the
    first kill signal attached to a rear check (soft soldiers;
    the ARMORED truck still resists Y-fire — grenade escalation is
    implemented + unit-tested, live-vs-truck still owed).
  * Live series: chopper_ckpt rebuilt (px 810.3, gren 10), 3
    independent boots policy_pass5/6/7 BIT-IDENTICAL (27 chunks,
    death c26 one-shot −291 truck ram at px 1164 — D7 blocker
    unchanged). Suite 389 passed + 1 xfailed (was 384+1).
  * Games batch: owner-supplied-source downloader reconstructed
    (`scripts/romsfun_fetch.py`: k_get_download referer-path flow,
    Range streaming, re-mint resume); TWO small retail games
    acquired + identity-verified + BOOTED with input causality:
    Poy Poy (USA) SLUS_004.86 (title→transition diff 181.4) and
    Trap Gunner (USA) SLUS_006.79 (START → 512-wide mode switch,
    diff 56.6) — category ②③④ candidates pending RAM mapping.
- LIVE batch 2026-10-23 (4 runs + checkpoint pass):
  * D8 CONFIRMED live → fixed → live-TESTED (`combat_live2` → `live4`).
  * D9 CONFIRMED live → fixed → live-TESTED (death accounting).
  * D5 dodge live-TESTED (verified-faller dodges only).
  * D2 rear_check live-OBSERVED once (`policy_pass1` chunk 25, correct
    geometry + buttons); **reproducible live series DELIVERED 2026-10-23:
    `policy_pass2/3/4` re-ran the identical checkpoint pass — 4/4
    identical firings (chunk 25, slot 14 dx −37.5 hp 254 h 64,
    `B+LEFT+Y`), suite re-verified 384+1xfail before the series. D2
    direction correction → live-`TESTED`; disclosed limit: the fired
    burst did not change the armored truck's hp (254→254) — kill
    follow-through vs armor remains `PARTIAL` (grenade `clamp_clear`
    is the proven kill path).**
  * Case 8 stale invalidation live (15/11/37 resets per run).
  * Checkpoint-phase variance DISCOVERED: the rebuilt `chopper_ckpt`
    (same px 810.3) sits at a different corridor script phase — the
    old ladder's only survivor (walk_right) now dies pinned at the
    truck wall (px 992). px-matched savestates do NOT guarantee
    script-phase-matched outcomes; ladder conclusions are
    checkpoint-phase-dependent (consistent with D6 variance).
  * The corridor/truck/clamp lethality (D6/D7) remains the open root
    blocker — 13 real deaths per run concentrate at px 992–1164.
    The policy_pass series adds precision: the pass dies at the clamp
    (chunk 26, one-shot −291 truck ram at px 1164) right AFTER the
    rear_check turn — i.e. the bounded turn fires but one chunk of
    LEFT fire cannot stop an armored ram; survival there needs the
    grenade path or a non-armored pursuer scenario.
