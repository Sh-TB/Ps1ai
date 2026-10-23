# Helicopter / mortar-rain survival ladder — 10 movement patterns from one checkpoint (Issue #5)

User directive: research what the web says about the Mission-1 chopper
fight ("when the helicopter drops bombs you must move — standing still
kills you"), build ONE savestate ~1 second before the encounter, then
test 10 different movement patterns from it instead of replaying the
level each time.

## Web research (before the run)

- arcadequartermaster.com, MS2 Mission 1: *"focus all your fire on the
  red Masknell chopper: the entire squadron collapses with the demise
  of the red leader"* — attacking the source should quiet the rain.
- Antstream Arcade guide: *"R-Shobu – Enemy Chopper: drops bombs on
  the player. Fast and deadly."*
- metalslug.fandom "Drifting in Desert": the mosque minarets hide
  launchers — a second threat source in the same zone.
- r/metalslug: keep moving; standing still is what kills you.

## Setup

- Checkpoint `chopper_ckpt`: player px 810.3 (the proven lob window),
  grenades 10, game active. Reach used the disclosed
  `hp_pair_freeze` EXPLORATION assist (trace: `reach_trace.jsonl`);
  **every pattern ran UNFROZEN** (no CheatSession exists in the
  pattern phase — deaths are real).
- 10 patterns x 60 fps, all starting from the same savestate.
  First-death endpoint. Per-frame JSONL + GIF per pattern.

## Results

| # | pattern | fate | killer (visual + RAM) |
|---|---------|------|-----------------------|
| 1 | stand_in_corridor | died f286 | mortar shell blast (armed shell ~27px; explosion on player) |
| 2 | walk_right | **SURVIVED 1500f, 810→1164** | — |
| 3 | patrol_tight | died f424 | shell blast at 884 (+500 soldier kill first) |
| 4 | zigzag_forward | died f1082 | **armored-truck ram** at the wall approach (one-shot 257) |
| 5 | hop_advance | died f1037 | truck ram at the clamp (one-shot 291) |
| 6 | run_to_wall_hold | died f609 | **truck ram while IDLE at the clamp** (truck on player) |
| 7 | wall_upfire | died f1037 | sword-soldier pack while STATIC up-fire (0 source kills) |
| 8 | lob_grenades | died f587 | sword soldiers while lobbing LEFT (+200 kill) |
| 9 | retreat_left | died f545 | sword soldiers while retreating (+100 kill) |
| 10 | prone_in_corridor | died f285 | same shell/frame as #1 — **prone does not dodge** |

Web/user predictions matched 10/10.

## Verdicts (defect-ledger labels)

- **H1 CONFIRMED** — standing still in the rain corridor = death
  (~4.8 s). Prone identical (H4 FALSIFIED: prone does not dodge).
- **H2 CONFIRMED** — constant forward movement is the only survivor;
  HP regen recovered all chip damage (hp_dips 224, min 139 -> final
  291).
- **H3 CONFIRMED** — the pursuing armored truck (the user's "jeep
  behind") one-shots players who idle/backtrack at the clamp; holding
  RIGHT at the wall survived 1270+ frames with the truck parked
  ~40 px behind.
- **H5 FALSIFIED-as-static** — static UP-fire at the clamp is a death
  pattern. FIX APPLIED: CombatPolicy clamp_clear up-fire segments now
  include LEFT (w2 protocol B: UP+LEFT+Y sustained) +
  `test_clamp_upfire_never_static`.
- **H6 FALSIFIED** — retreating does not escape (melee chases).
- **H7 FALSIFIED** — no practical in-flight warning: the shell drops
  the last 64 height units in ONE frame, then creeps LEFT along the
  ground (973→925 px, decelerating) with its HP field decaying
  352→101 and arming at saturation; kill radius ~≤27 px.

## Cross-boot determinism note

Pattern 02 vs 06 (identical RIGHT inputs): px/enemy trajectories
identical; the HP word diverged by 3 points at f229 (chip-tick
timing). Position-level determinism holds; HP has a small
cross-boot drift — measurement caveat for HP-based A/B.

## Artifacts

- Evidence + per-frame JSONL + reports: `evidence/heli_ladder/`
  (workspace; scripts: `msx_helicopter_ladder.py`,
  `msx_rain_slot_trace.py`, `msx_heli_summary.py`,
  `curate_heli_gifs.py`)
- Curated GIFs: `docs/gif_evidence/heli_ladder/heli_*.gif`
