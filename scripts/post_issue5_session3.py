#!/usr/bin/env python3
"""post_issue5_session3.py — Issue #5 comment: the session-3 report
(the D7 release condition proven, the MISSION 1 screen, the chopper
kill recipe, the section-VM decode, the policy fixes)."""
import sys
sys.path.insert(0, "/home/z/my-project/scripts")
import gh_api

BODY = """## Issue #5 — session 3: the D7 release condition is PROVEN (the section-entity queue clear), the MISSION 1 complete screen is reached, and the chopper dies to the jump-lob (2026-10-25)

**Baseline → HEAD:** `93ba5bb` → **`f953dc0`**, pushed. Suite **459 passed + 1 xfailed**. The sandbox reset had wiped every savestate again — `pin_ckpt` (the D7 pin: px 1164.0, 10 grenades, score 1200) and `chopper_live` were rebuilt live through the fixed-policy walk. Machine-readable record: `data/games/SLUS-01212/truck_evidence/truck_resolution_session3.json`.

### §1 The release condition — `GAMEPLAY_VERIFIED` 3/3

Session 2's smallest-next-experiment ("kill the chopper") went one level deeper and found the actual gate: **the D7 pin releases when the section VM's pending-entity queue CLEARS.**

From `pin_ckpt`, three arms bit-identical (`scripts/release_test.py` rel1/2/3): take the one-shot → ride the F6-style respawn to px 992 → standing-fire the 2 frozen `0x4054` soldiers ahead (+200) → ZONE_CLEAR → the section walker leaves the pin family: **state 0xB → 0xC**, flags 0x1 → 0x8, the progress word leaves `0xFFFFFFFF` → `0xFFF38B4A`. The truck's death never released the pin because **the truck was never the gate** — the section's soldier wave was.

### §2 The MISSION 1 complete screen — `GAMEPLAY_VERIFIED`

The release rolls into the **MISSION 1 end screen**: the "MISSION 1" banner + "PRESS START" + score 1500 (PNG committed: `truck_evidence/session3/mission1_complete_screen.png`; release scene `release_scene_0xC.png`). Reproduced across 3 runs. Post-screen flow observed: START toggles PAUSE; unpause + START → **"Metal Slug X — NOW LOADING"** → the SNK attract title (the continue-countdown expires during the tally wait — a timing nuance for the next milestone, not a blocker). Not claimed: a mission-1 clear through the shipped policy alone (these runs used the scripted chain), and Mission 2 entry.

### §3 The chopper dies — the jump-lob recipe (`GAMEPLAY_VERIFIED`)

**Hop, and throw the UP-lob at the jump apex.** Connect band **|dx| ≈ 7–29** (nearly overhead; chopper h ≈ 205–214), 3 connects = dead: **hp_a4 300 → 200 → 100 → 0, +1100 score** (`chopper_kill.py` arm J1: 3 hp drops + CHOPPER_GONE; the full chain kills it in 19 deterministic throws, reproduced twice). Ground UP-lob control arm: negative (+200, no chopper hp drop) — session-2's negative result reproduced. Also `CONFIRMED`: at the pin the chopper IS the active killer (the death census has it at hp_a4 300 with `0xB4E4` fallers in flight); in a no-input control it parks inactive (slot 13, x=0) — it engages when the player acts.

### §4 Two structural discoveries

- **The truck lives in slot 33** — outside the historical 24-slot scan window (`scan_entities` SLOTS=24). Every earlier scan was structurally blind to it. This session's scripts scan 36 slots; widening the shipped sensor is deferred (behaviour-affecting — deserves its own paired trial).
- **The section VM is decoded (static, canonical EXE)**: the 13-opcode dispatcher `0x80021128` consumes a **30-byte runtime-rebuilt script buffer @`0x80010DB8`** (cursor-indexed, opcodes 0x01–0x0D; the file holds ASCII tokens, live RAM holds pointers+bytes — verified live). Request 8 → `flags |= 0x12` + counter decrement; request ≠ 8 → `flags |= 0x42` — the pin signature. Runner id s16 @`0x800EB588` (−1 = inactive), gate u16 @`0x800EB5C6` (==9 special arm). The queue walker `0x80020444` resolves requests from a node list @`0x800EB5F8` (nodes +0x5C/+0x8) via a table @`0x800EB5E8`, and **jal's INTO the dispatcher's handler bodies** (`0x800216bc`/`0x80021830`) — the missing link behind the "zero static callers" mystery.

### §5 Policy changes (plugin layer only, zero core edits)

(a) the instrument pin also latches on a **SUSTAINED `(0xB, flags&0x40)`** reading — boot-2 pins there (2-consecutive confirm keeps the old single transients out; the `(0xB,0x43)` contract test updated with the evidence citation); (b) `clamp_clear` now **aims at the nearest live ground foe's side** — the hard-coded LEFT fired away from the respawn-side soldiers; (c) the mode fallback holds `clamp_clear` while `section_pinned` even when the derived px-stall streak flickers. 3 new tests; suite 459+1xfail.

### §6 Honest status

- `GAMEPLAY_VERIFIED` — the D7 release via section-entity clear (3/3); the MISSION 1 screen (3 observations); the chopper kill (3 connects).
- `IMPLEMENTED + UNIT_TESTED` — the section-VM decode; the policy pin/aiming fixes.
- `BLOCKED` — the **full-chain last mile**: with chopper + soldiers + truck all dead (the truck died to collateral at its parked 937.5 — wreck `0xA44C`), the walker still cycles `(0xA/0xB, 0x43)` at px ~984 with one residual frozen `0x4054` at 1072 that Y-bursts did not kill. Soft soldiers do not use `+0xA4`, so the current foe filter cannot separate a live `0x4054` from a corpse.
- Not claimed: a policy-only mission clear; Mission 2 entry.

### §7 The single highest-value next action

**Discriminate the residual `0x4054`'s true HP word** (soft soldiers do not use `+0xA4` — find the word that drops under bullets for THAT slot), kill it, and walk the section with the chopper already dead — the released runs had the chopper inactive, so the entity-gating matrix per boot phase (which pending entities gate WHICH pin) is exactly one controlled experiment away from the full policy-only mission clear."""

s, d = gh_api.req("/repos/Sh-TB/Ps1ai/issues/5/comments", "POST",
                  {"body": BODY})
print("posted:", s, d.get("html_url", d))
