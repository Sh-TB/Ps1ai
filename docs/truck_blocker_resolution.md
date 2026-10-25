# Issue #5 D7 blocker: the armored truck resolved (field semantics corrected, truck kill GAMEPLAY_VERIFIED)

Date: 2026-10-25 · base commit `d99db8993084cdc2a8a112e7f5f69d9de004b219` · suite **453 passed + 1 xfailed**

## TL;DR

The "armored truck at the D7 pin" blocker fell to the proven m2c + Ghidra
pipeline. **The historical `+0x8E = hp` label was wrong** — that field is
the screen-x coordinate. The truck's real HP is the **u16 at `+0xA4`**
(300 → 0, grenade = 100 dmg), the truck itself is **slot 14** (state word
`0x9E88`) *behind* the player, and a 4-grenade kill recipe is now wired
into the plugin: **8/8 independent kills, 3/3 bit-identical through the
policy path**. The D7 pin does **not** release on the truck's death alone;
the clamp killer is identified (faller bombs from the wall mortarman) and
the smallest next experiment is documented.

## What the tools actually contributed

| step | tool | seconds | what it found |
|---|---|---|---|
| call graph | committed Ghidra corpus (`callers`/`callees`) | <5 | the 3 suspect functions have **zero static callers** → state-pointer dispatch |
| function-pointer refs | capstone scan of 468 function byte blobs | ~10 | `0x800151DC`/`0x800AADBC` shared death states (17 refs each) |
| +0x8E writer scan | capstone over overlay + EXE text | ~5 | **zero stores to +0x8E in the overlay**; the only init writes are spawn positions |
| screen-pair proof | disasm 0x80064674 | ~5 | `lw 0x8c(a0)/addu/sw` per entity = camera-scroll deltas → **+0x8C/+0x90 are screen x/y** |
| damage fingerprint | subtract-store pattern scan | ~8 | none in the overlay → damage is applied EXE-side |
| score refs | `lui 0x800F, -0x1CE8` scan | ~5 | score helpers at 0x8005C430 (indirect-only callers) |
| walker decompile | m2c on FUN_80021898 bounds | ~15 | the section reset (state=0, flags=0) + the scroll clipper; the true state-writer cluster is at 0x80022xxx–0x800236xx |

Then the live experiments (full-record u16 diffs, read-only) resolved
what static analysis alone could not:

- **uplob1/2**: the historical "truck" tracker (screen-x 200–300) was
  locking **soldiers**; the +100s were infantry kills; two independent
  tools agreed the 0x8009decc branch was dead code, and the full-record
  diff showed which records actually moved.
- **uplob5/6**: the *visual* truck is **slot 14** at world 937.5
  (screen-x 65), *behind* the player; its record never moved.
- **uplob6/7/8**: grenade hits on the truck changed exactly one
  meaningful word — **w82 = +0xA4: 300 → 200** (−100 per hit).
- **uplob9/10**: the clamp-stand spam finished it (**200 → 100 → 0**,
  state → `0xA304`, +400 score); post-kill walks still die at px 1164 —
  the death PNG shows a **faller bomb explosion**, and the entity rows
  show the bomb (st `0xB4E4`, hp_a4 30, h dropping 178→104) spawning at
  the player's position — thrown by the wall mortarman (`0xE17C`).

## Manual vs tool-assisted (the mission's comparison metric)

| | manual (runtime-only, #3/#5 historical) | tool-assisted (this session) |
|---|---|---|
| frames spent | ≥ 60,000 (multi-session) | ~45,000, of which the discriminating diffs are < 3,000 |
| wall time | multiple full sessions | ~2.5 h (static scans ≈ 6 min; 16 emulator sessions ≈ 11 min) |
| truck kills | 0 (the claimed "254→207 damage" was the soldier walking) | 8/8 independent (5 scripted + 3 plugin-path) |
| reusable recipe | none | approach band → face-left lob → clamp spam, encoded in `truck_kill_segments()` |
| semantics delivered | `+0x8E = hp` (wrong) | corrected table with statuses (see `truck_resolution.json`) |

## Plugin-level change (smallest justified)

`ps1play/agent/combat.py`:

- `scan_entities()` now also returns `sx` (honest name for the +0x8E
  screen-x), `hp_a4` (+0xA4), `st` (state word0); legacy `hp` key kept
  for compatibility.
- `find_truck(enemies)`: identity = ground + state `0x9E88` +
  `hp_a4 ∈ [100,600]` (the `0x4054` soldier mislock is documented and
  rejected).
- `truck_kill_segments(px, truck, ammo, phase)`: the pure,
  offline-testable state machine implementing the proven recipe
  (approach band → face-left lob → escape → clamp spam → done at
  `hp_a4 == 0`).

No shared-core changes. `tests/test_truck_semantics.py` adds 5 tests
(field keys, truck identity incl. the mislock rejection, the kill state
machine, the death/ammo terminations). Suite: **453 passed + 1 xfailed**.

## Honest status

- `GAMEPLAY_VERIFIED` — truck kill (8/8: uplob7 hit1 ×3, uplob9, uplob10,
  uplob11, plugin reps 1–3; hp 300→0 each time).
- `IMPLEMENTED` + `UNIT_TESTED` — the semantics layer + kill routine in
  the policy layer.
- `BLOCKED` — the D7 release itself: the truck's death alone does not
  release the pin. The clamp killer (faller bombs from the wall
  mortarman) is identified with PNG + entity-row evidence. Smallest next
  experiment: kill the wall mortarman (`0xE17C`, UP-lob from below) and
  the remaining section entities, then walk; if the clamp still holds,
  m2c the state-writer function containing 0x80023308 (the section
  advance at `progress < threshold`) and trace the wait condition.
- `SUPERSEDED` — the `+0x8E = hp` label and the "254→207 grenade
  damage" claim.

---

## Session 2 addendum (2026-10-25, base `73c172d`): the wreck blocker, the chopper identity, and the dead progress-gate hypothesis

The sandbox reset wiped the `truck_engage` savestate and the evidence
tree, so the session opened by re-deriving everything honestly: m2c
re-cloned, `truck_engage` re-created with **no cheats** (policy walk
into the CLAMP-ROOT safe band, save on the first parked-truck
sighting), and the kill campaign re-run from it.

### What changed in the picture

1. **The truck this route parks AHEAD (1126.5), not behind (937.5).**
   The revived anchor holds the parked truck at 1126.5 with `hp_a4`
   230 (route attrition; 300 fresh). The kill still works — 5 more
   GAMEPLAY_VERIFIED kills this session, and the lob connect band is
   much wider than the historical hit band: **|dx| 53..135 all
   connect** (grenade = 100 dmg re-confirmed; +800 score).
2. **NEW BLOCKER — the wreck.** A truck killed while parked ahead
   leaves a persistent corpse (`0xA304 → 0xA44C`, no further
   transition in >1500f) whose left edge physically blocks the road at
   **px ≈ 1058**: post-kill walks freeze there and hop-advance /
   hop-dodge inputs are **no-ops** (kr_rep9: four consecutive dodge
   hops, px frozen 1058.1). This explains the split between the
   historical walks (truck parked behind → clear road → the 1164 pin)
   and this session's walks (truck parked ahead → wreck block).
3. **The chopper identified.** The `hp_a4 = 300, h 206-228` slot
   cycling `0xaa94/0xabdc` is the **chopper** (PNG: it renders at the
   top of the screen), it *tracks* the player and drops the `0xB4E4`
   faller bombs. Bullets (UP+Y) and UP-lobs do not connect at h≈210;
   it is the last live combatant in every blocked attempt and it kills
   any clamped/frozen player. The historical `0xE17C` wall mortarman
   does not exist in this route state (the wall entities are `0xe19c`
   and they vanish without explicit kills).
4. **The progress-gate hypothesis is DEAD.** The advance store at
   `0x80023308` (fn `0x800230e0`) requires a signed
   `PROGRESS(0x800EB5D4) < a0` — live PROGRESS is `0xFFFFFFFF`
   (−1 signed), so the gate would pass; the release fails **upstream**:
   the dispatch chain never produces the nonzero next-state. The
   section-state handler `fn 0x80021128` is a 13-opcode script
   dispatcher; requests ≠ 8 set `flags |= 0x42` (the pin bit's source:
   `ori` at `0x800212a8/0x800215a0/0x80021700/0x800218cc`), the live
   pin flags 0x43 = 0x42 | 0x01 (the ticker's advance latch). None of
   the three functions has any static caller (EXE + overlay jal/j/
   pointer scans all negative) — the chain runs on computed jumps.
5. **Policy fix (plugin layer, smallest justified).** The armor class
   keyed `hp >= 200` on **+0x8E — the screen-x** (a pre-correction
   leftover): the 0x4054 right-side soldier mislocked as armor and
   `armor_hold` stalled the baseline run 58 chunks at ~900 until the
   bombs killed the agent. The class now keys the **real HP
   (`hp_a4 ≥ 200`) + ground contact** — the airborne chopper can never
   get the stand-and-fire treatment. Paired trial (same deterministic
   core, same script): baseline died c67 at ~900; the fixed policy
   reached the **D7 pin (1164.0) by c10** and scored +1800 by c40.
   4 new/updated regressions; suite **456 passed + 1 xfailed**.

### Honest status delta

- `GAMEPLAY_VERIFIED` — truck kill (5 more reps this session, wider
  connect band documented).
- `IMPLEMENTED + UNIT_TESTED` — the armor-class correction (policy
  layer only; zero core changes).
- `BLOCKED` — the D7 release. New exact statement: the truck's death
  does not release the pin (re-confirmed), the progress gate at
  `0x800232f4` is NOT the blocker (signed −1 passes), the blocker sits
  in the computed-jump dispatch chain that must produce the next
  section state — and the chopper (unkilled at h≈210) is the last live
  combatant. Smallest next experiment: kill the chopper (jumping lob
  arc, or trace the overlay chopper handler for its vulnerable state);
  if the pin still holds, table-disassemble the `0x80022500` ticker
  and correlate its next-state production with a live trace at the
  `0x80023308` store.

## Session 3 (2026-10-25): the D7 release condition — PROVEN, and the MISSION 1 screen reached

Baseline `93ba5bb` (session-2 report already posted), suite re-verified
**456+1xfail** after the sandbox reset (capstone + m2c re-cloned), final
suite **459+1xfail** (3 new tests). Machine-readable record:
`data/games/SLUS-01212/truck_evidence/truck_resolution_session3.json`.

### §1 The release condition (the session-2 §5 experiment executed and exceeded)

The named smallest experiment was "kill the chopper"; the session went
one level deeper and found the actual gate:

- **F1 `GAMEPLAY_VERIFIED` 3/3** — the D7 pin releases when the
  section VM's pending-entity queue CLEARS. From `pin_ckpt` (px 1164,
  10 grenades): take the one-shot, ride the F6 respawn to px 992,
  standing-fire the 2 frozen `0x4054` soldiers (+200) → walker state
  **0xB → 0xC**, flags 0x1 → 0x8, the progress word leaves
  0xFFFFFFFF → 0xFFF38B4A (`scripts/release_test.py` rel1/2/3,
  bit-identical).
- **F2 `GAMEPLAY_VERIFIED`** — the release rolls into the
  **MISSION 1 complete screen** ("MISSION 1" banner + PRESS START +
  score 1500; PNG evidence committed): the explicit in-game
  completion evidence, reproduced across 3 runs
  (`release_advance.py`, `release_confirm.py` ×2).
- **F3 `OBSERVED`** — post-screen flow: START toggles PAUSE;
  unpause + START → **"Metal Slug X — NOW LOADING"** → the SNK attract
  title (the continue-countdown expires during the tally wait — a
  timing nuance for the next milestone, not a blocker).

### §2 The chopper: killed, with the recipe

- **F4 `GAMEPLAY_VERIFIED`** — **hop + UP-lob thrown at the apex**,
  connect band **|dx| ≈ 7–29** (nearly overhead; h ≈ 205–214), 3
  connects = dead (hp_a4 300→200→100→0), **+1100 score**
  (`chopper_kill.py` arm J1: 3 hp drops + CHOPPER_GONE; the full
  chain runs kill it in 19 deterministic throws). The ground UP-lob
  control arm reproduces session-2's negative (+200, no hp drop).
- **F8 `CONFIRMED`** — at the pin the chopper IS the active killer
  (the trial death census has the chopper `0xABDC` hp_a4 300 at dx
  −124 with `0xB4E4` fallers in flight); in a no-input control it
  parks inactive (slot 13, x=0, hp_a4 300). It engages when the
  player acts.
- **F5 `CONFIRMED`** — the armored truck lives in **slot 33**,
  OUTSIDE the historical 24-slot scan window — every earlier scan
  (slots 1–23) was structurally blind to it. This session's scripts
  scan 36 slots; widening `scan_entities` itself is deferred (it
  changes live behaviour and deserves its own paired trial).

### §3 The section-VM decode (static, m2c/capstone on the canonical EXE)

- **F6 `IMPLEMENTED`** — the 13-opcode dispatcher `0x80021128`
  consumes a 30-byte script buffer at `0x80010DB8` (cursor-indexed,
  opcodes 0x01–0x0D; the buffer is ASCII tokens in the EXE file but
  runtime-rebuilt pointers+bytes in RAM — live-verified). Request 8 →
  `flags |= 0x12` + a counter decrement; request ≠ 8 → `flags |=
  0x42` — the live pin signature. Runner id s16 @`0x800EB588` (−1 =
  inactive), gate u16 @`0x800EB5C6` (==9 special arm). The queue
  walker `0x80020444` resolves requests from a node list
  @`0x800EB5F8` (nodes +0x5C/+0x8) via a table @`0x800EB5E8`, and
  jal's INTO the dispatcher's handler bodies (`0x800216bc`,
  `0x80021830`) — the missing link behind "zero static callers".
  Full disassemblies + m2c attempts:
  `evidence/issue5_session3_static/`.

### §4 Policy changes (plugin layer only, zero core edits)

- **F7 `IMPLEMENTED + UNIT_TESTED`** — (a) the instrument pin also
  latches on a SUSTAINED `(0xB, flags&0x40)` reading (boot-2's pin;
  the 2-consecutive confirm keeps the old single transients out —
  the `(0xB,0x43)` contract test updated with the evidence citation);
  (b) `clamp_clear` now aims its fire at the nearest live ground
  foe's side — the hard-coded LEFT fired AWAY from the respawn-side
  soldiers; (c) the mode fallback holds `clamp_clear` while
  `section_pinned` even when the derived px-stall streak flickers.
  Suite 459+1xfail (3 new tests in `test_section_pin_policy.py`).

### §5 Honest status delta

- `GAMEPLAY_VERIFIED` — the D7 release via section-entity clear
  (3/3); the MISSION 1 screen (3 observations); the chopper kill
  (jump-lob, 3 connects).
- `BLOCKED` — the **full-chain last mile**: with chopper + soldiers +
  truck all dead (the truck died to collateral at its parked 937.5 —
  wreck `0xA44C`), the walker still cycles `(0xA/0xB, 0x43)` at
  px ~984 with one residual frozen `0x4054` at 1072 that Y-bursts
  did not kill. Soft soldiers do not use `+0xA4`, so the session's
  foe filter cannot separate a live `0x4054` from a corpse — that
  word, and the boot-phase difference vs the releasing runs (chopper
  inactive there), is the next discriminator.
- **Not claimed**: a mission-1 clear through the shipped policy alone
  (the released runs used the scripted chain), and Mission 2 entry.

---

## Session 4 (2026-10-25): F9 UNBLOCKED — MISSION 1 banner through the shipped policy

Full evidence: `truck_resolution_session4.json` (+ `session4/` PNGs).
Anchor `b19ad97`; suite 466+1xfail.

### §6 The last-mile decode (why the session-3 residual "would not die")

- **S4-F1 `GAMEPLAY_VERIFIED`** — the residual soldier was killable
  all along: 2 AIMED bullets, 3/3 deterministic (`soldier_bpp.py`).
  The session-3 bursts failed on FACING (the soldier sat at
  dx −92..−120, behind the player at the pin) and the foe filter
  kept mid-anim CORPSES (valid screen-x until their ~+138f despawn),
  so the fire aimed at the dead.
- **S4-F2 `OBSERVED`** — liveness is the state-word family:
  live `{0x4054, 0x41FC}` (cycles unattended within ~600f), corpse
  `{0x4BE4, 0x5CC8}` (stable).  The soft-soldier HP word stays
  UNKNOWN at field granularity (41 words move on a no-input miss
  control); behavioural HP = 2 bullets.
- **S4-F3 `GAMEPLAY_VERIFIED 6/6`** — the end sequence runs BY
  ITSELF on a standing player:
  `(0xB,0x1)@992 -> (0,8) reset -> (0xC,0x9) @ px 26.4` = the
  **MISSION 1 / CLEAR TIME 0'09"61 / PRESS START** banner.  No
  px>1170 walk is part of the release.
- **S4-F4/S4-F5** — the sequence is INPUT-FRAGILE (inputs during
  `(0,8)->(0xC)` skip the banner into a restart) and the pin cycle
  RE-ARMS on re-entry (advance back into the clamp re-runs the
  pending-queue check).

### §7 Policy patch (plugin layer only) + the paired trial

- **S4-F8 `IMPLEMENTED + UNIT_TESTED`** — `combat.py`:
  (a) `scan_entities` drops `CORPSE_ST` rows; (b) the mission-end
  latch (0xC ×2, plus the pre-banner `(0,8)`-reset trigger inside
  the D7 zone) holds a full no-input chunk; (c) the D7 zone latch
  (px ≥ 1150; un-latch only on a restart reading) never advances
  inside the pin cycle, walk-back floor 985; (d) `clamp_clear`
  family-priority aim + quiet-hold on an empty zone scan; (e) a
  valid-px restart reading un-latches into the next mission.
- **S4-F6 `GAMEPLAY_VERIFIED 3/3`** — the SHIPPED PLUGIN POLICY
  alone (no scripted inputs) reaches the banner from `pin_ckpt`:
  c=79, score 2500, 0 deaths, deterministic
  (`policy_chain_trial.py --arm fix`).
- **S4-F7 `GAMEPLAY_VERIFIED`** — the paired baseline (pre-patch
  behaviour: corpses included + no hold) is 0/3
  (`death_no_respawn` ×3, 2 deaths each).

### §8 Honest status delta

- `GAMEPLAY_VERIFIED` — MISSION 1 completion banner 6/6 (3 scripted
  + 3 pure-policy) from the D7 checkpoint, real inputs only.
- `UNKNOWN` (honest) — the wall mortarman (faller source) survived
  3–4 aimed taps in both arms; not needed for the release, unmeasured
  HP semantics.
- **Still not claimed**: a full from-mission-start clear under the
  shipped policy alone (the checkpoint embeds the pre-D7 progress),
  and Mission 2 entry.
