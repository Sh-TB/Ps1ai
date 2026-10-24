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
