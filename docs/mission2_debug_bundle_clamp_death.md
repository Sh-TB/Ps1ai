# Mission 2 Debugger Evidence Bundle — the clamp death (Deliverable E, Issue #9 §8)

Real unresolved failure chosen: **the policy's 4/4 one-shot death at the scroll clamp
(px ~1164, −291 "truck ram")** — the failure that has ended every MSX policy pass since
session 2. Evidence bundle per §8's required procedure.

## 1. Reproduce from a known starting state

Checkpoint `chopper_ckpt` (px 810.3, Beetle PSX savestate, ~1 s before the chopper
encounter). Reproduction: `scripts/msx_clamp_root.py --arm A --chunks 90`.
Result: death at chunk 26, one-shot hp 291→0 at px 1164 — the historical signature,
reproduced. Inputs and frames recorded in `decisions_clamproot_A.jsonl`.

## 2-3. Baseline state + full instrumentation

Arms share the checkpoint; per-chunk CONFIRMED observations: px, hp pair, score,
grenades, flags (u32@0x0EE518), scroll word (u32@0x0EB598), and an **armored-entity
census** (all slots with hp 200..400) with x/hp/h over time.

## 4-5. The relevant change and its provenance (differential, not a dump)

Three arms (same checkpoint, same budget, read-only):

| Arm | Behaviour | Outcome |
|---|---|---|
| A baseline | current policy | dies c26, one-shot −291 at px 1164 (max_px 1164) |
| **B hold-outside** | forbidden to cross px 950 | **0 deaths in 5400 frames**; max_px 998 |
| C slow-approach | engage-first + ≤30 px/chunk beyond 1100 | dies c26/27 identically (max_px 1164) |

Arm B is the discriminating experiment. The armored wave **did** approach (truck slots
x 1134→1092→1071) and took standing fire damage (hp 340→214, 294→235 across sightings)
while the agent held position — **no fatal contact ever occurred**. Provenance: per-chunk
RAM census (`clamproot_B/result.json` armor_timeline), screenshots, decision logs.

## 6-7. Hypothesis + discriminating experiment

**H1**: the fatal contact requires the *player* to be inside the pin zone
(px ≈ 1100-1164) while the truck presses; the kill is position-dependent, not a
time-script. Discriminated by arm B (holds outside → survives; trucks still come).
CONFIRMED.

## 8. Smallest justified change

`armor_hold` branch in `ps1play/agent/combat.py` (policy layer, no shared-core change):
an *ahead* armored foe (hp ≥ `ARMOR_HP_MIN`=200, dx ≤ `ARMOR_ENGAGE_X`=230) stops the
run — 2-frame face-assert, then standing aimed fire; grenade escalation at dx ≤ 110 on
verified hp-unchanged streak (the proven anti-armor kill path 254→207×3, +700 score).
Rear armored foes deliberately stay on the verified `rear_check`/grenade campaign
(regression caught and fixed during development: `test_rear_armored_keeps_rear_check_not_armor_hold`).

## 9-10. Repeat + verify on the original backend

Post-fix live pass from the same checkpoint: **the one-shot −291 pin ram is eliminated**
(max_px 1083.8; the run now dies by attrition 63/29/28 around px 900-930 — a different,
addressable failure mode, next iteration). Suite: 420 passed + 1 xfailed (7 new tests).

## 11. Regression + neighboring scenario

Full suite green; the rear-check, engage-short, dodge, clamp-escalation behaviours
re-verified by their existing tests; Tetrade unaffected (plugin-scoped change).

## Debugger-tooling note (honest provenance)

The diagnosis used **differential in-process RAM forensics on the Beetle path** (the
proven stack), not PCSX-Redux: the Redux headless path boots and loads the game
(Deliverable B) but its gameplay execution currently parks at a vblank-wait — recorded
as PENDING in the tools matrix, exactly the kind of blocker §8 anticipates. The
differential arms B-vs-A provided the causal evidence a watchpoint would have.

## What remains

1. Attrition survival inside `armor_hold` (the standing agent eats 63/29/28 chip
   damage) — next smallest change: reposition-while-holding / prioritize the soft
   shooters instead of pure truck focus.
2. Whether a truck can actually be KILLED from the hold position given enough time
   (chip rate ~14 hp/s observed; grenade escalation should close it — needs a longer run).
