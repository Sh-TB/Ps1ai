#!/usr/bin/env python3
"""post_issue5_truck_session2.py — Issue #5 final comment: the truck
blocker session-2 report (revival, wreck blocker, chopper identity,
dead progress-gate hypothesis, the policy armor-class fix)."""
import sys
sys.path.insert(0, "/home/z/my-project/scripts")
import gh_api

BODY = """## Issue #5 — truck blocker session 2: the wreck blocker, the chopper identity, and the dead progress-gate hypothesis (2026-10-25)

**Baseline → HEAD:** `73c172d` → **`8c05cfb`**, tree clean, pushed. Suite **456 passed + 1 xfailed**. The sandbox reset had wiped the `truck_engage` savestate, the evidence tree and the local m2c — everything below is re-derived live or re-cloned (m2c re-cloned; no tool reinstall beyond that).

### §1 What was proven this session (all live unless noted)

- **Truck kill re-verified 5×** from the revived anchor: hp 230 → 130 → 30 → 0 (u16@+0xA4, grenade = 100 dmg re-confirmed), +800 score, player alive. The lob connect band is **|dx| 53..135** — wider than the historical 50..62 hit band, which is a subset, not a requirement.
- **Route discovery:** the truck on this route **parks AHEAD (x 1126.5, `0x9E88`, hp_a4 230 = route attrition)** — not behind at 937.5 as in the historical anchor. Soldiers ride ON the truck; their contact push (~−0.7 px/f) defeats reposition walks — the working pattern is throw-lobs-immediately.
- **NEW BLOCKER — the wreck (CONFIRMED).** A truck killed while parked ahead leaves a persistent corpse (`0xA304 → 0xA44C`, no further transition in >1500f) whose left edge **physically blocks the road at px ≈ 1058**: post-kill walks freeze there and hop-advance/hop-dodge are **no-ops** (kr_rep9: four consecutive dodge hops, px frozen 1058.1). This cleanly explains why historical post-kill walks reached the 1164 pin (their truck parked BEHIND — clear road) while every ahead-parked kill this session froze at ~1058.
- **The chopper identified (CONFIRMED).** The `hp_a4 = 300, h 206–228` slot cycling `0xaa94/0xabdc` is the **chopper** (PNG: renders at screen top), it tracks the player and drops the `0xB4E4` faller bombs. UP+Y bullets (7+ bursts) and UP-lobs (dx −8..−25) never connect at h≈210. It is the last live combatant in every blocked attempt and kills any clamped player. The historical `0xE17C` wall mortarman does **not** exist in this route state (the wall entities are `0xe19c` and vanish without explicit kills).
- **The progress-threshold pin hypothesis is CONTRADICTED.** The advance store `0x80023308` (fn `0x800230e0`) requires a **signed** `PROGRESS(0x800EB5D4) < a0`; live PROGRESS at the blocker is `0xFFFFFFFF` (−1 signed) → the gate would **pass**. The release fails **upstream**: the dispatch chain never produces the nonzero next-state s0.
- **The pin-flag source found (static, address-exact).** fn `0x80021128` is a 13-opcode section-script dispatcher; requests ≠ 8 execute `ori $v0, $v0, 0x42` (`0x800212a8 / 0x800215a0 / 0x80021700 / 0x800218cc`) — the live pin flags **0x43 = 0x42 | 0x01** (the ticker's advance latch `0x80022c04`); request 8 sets `0x12`. **Zero static callers** for `0x800230e0 / 0x80022500 / 0x80021128` (EXE + overlay jal/j/pointer-build scans all negative) — the chain runs on computed jumps (RAM-only tables).

### §2 Plugin-level change (smallest justified, policy layer only, zero core edits)

The shipped armor class keyed `hp >= 200` on **+0x8E — the screen-x** (a pre-correction leftover): the documented 0x4054 right-side soldier mislock lived in the policy itself. Live cost (paired trial, same deterministic core, same script — `scripts/truck_zone_probe.py`):

| arm | armor_hold stalls | death | furthest px | score at c40 |
|---|---|---|---|---|
| baseline (screen-x key) | 58 chunks at ~900–1033 | c67 @ ~900 | ~1033 | 5300 (never pinned) |
| fixed (`hp_a4` key + ground contact) | 0 | c42 (in the pin zone) | **1164.0 by c10** | +1800 |

`ps1play/agent/combat.py`: the armored class now keys the **real HP (`hp_a4 ≥ ARMOR_HP_MIN`) + ground contact (h == 64)** — the airborne chopper can never receive the stand-and-fire treatment; the no-progress escalation tracks `hp_a4`. 4 new/updated regressions in `tests/test_mission2_armor_hold.py` (screen-x soldier rejection, airborne chopper rejection, route-damaged truck classification, real-HP softening).

### §3 Honest status (enumerated)

- `GAMEPLAY_VERIFIED` — truck kill (5 reps this session; 13 total across both sessions).
- `IMPLEMENTED + UNIT_TESTED` — the armor-class correction (+ 1 live paired trial observed).
- `CONFIRMED` — the wreck blocker; the chopper identity; `+0xA4` semantics (230→0).
- `CONTRADICTED` — the progress-threshold pin hypothesis; the `0xE17C` mortarman signature (this route state).
- `BLOCKED` — the D7 release. Exact statement: the truck's death does not release the pin (re-confirmed); the release fails upstream of the `0x80023308` store, in the computed-jump dispatch that must produce the next section state; the chopper (unkillable with ground techniques at h≈210) is the last live combatant.
- Not claimed: mission clear, pin release, chopper kill.

### §4 Evidence & repro

- `data/games/SLUS-01212/truck_evidence/truck_resolution_session2.json` + `session2/` (`pin_words.json` — the full 32-bit walker words at the blocker; `truck_parked_ahead_soldiers.png`; `chopper_screen_top_death.png`; `wreck_report.json`).
- Repro: `python3 scripts/truck_wreck_release.py` (kill + wreck wait), `python3 scripts/truck_zone_probe.py` (the paired policy trial), `python3 scripts/state_writer_decompile.py` + `state_writers_scan.py` (the static side). JSONL traces + PNGs land in `evidence/issue5_truck_release/` and `evidence/issue5_truck_reach2/` (local-only, hashes inside the committed JSONs).
- Changed files: `ps1play/agent/combat.py`, `tests/test_mission2_armor_hold.py`, the seven new `scripts/truck_*.py` / `state_*.py` / `pin_words_probe.py`, `docs/truck_blocker_resolution.md` (session-2 addendum), `worklog.md`, the evidence JSON + PNGs.

### §5 The single highest-value next action

**Kill the chopper.** It is the last live combatant and the only entity that can still act on the player at the pin. Two concrete paths: (a) a jumping lob (`UP+B+A` arc) timed to its hover x — the only untried ground-reachable delivery; (b) m2c the overlay's chopper handler to find its vulnerable state/window. If the chopper dies and the pin still holds, table-disassemble the `0x80022500` ticker (its embedded jump table at `0x80022600+` needs table-driven disassembly) and correlate its next-state production with a live trace at the `0x80023308` store."""

s, d = gh_api.req("/repos/Sh-TB/Ps1ai/issues/5/comments", "POST",
                  {"body": BODY})
print("posted:", s, d.get("html_url", d))
