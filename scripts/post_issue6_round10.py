#!/usr/bin/env python3
"""post_issue6_round10.py — Issue #6 round-10 report + Issue #7 timer/
spawner evidence note + Issue #8 DoD-closure note."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY6 = """**Round 10 (50/50) — Tetrade Issue-#8 DoD CLOSED through the plugin
contract (complete loop, all 5 items PASS/CAUSAL); MSX Issue-7 gauntlet
attacked with four new instruments (rear spawner REACHABLE, no 1 Hz
timer in RAM, arena is one-pass); PSXMC round-9 mandates FIX-1/FIX-2
CLOSED with the breaking-state oracle VALIDATED and two new aim-model
discoveries.** Suite **521 passed + 1 xfailed** (was 489). All three
lanes hit the Task-tool infra timeout on return (round-8/9 precedent);
every lane's work was recovered from disk and the remaining executions
were driven directly by the orchestrator.

## Tetrade — Issue #8 DoD closed (details on issue #8)

`tetrade_r10_plugin_loop.py`: COMPLETE loop through plugin contract v1,
zero core edits (PS1Play.run_steps/observe/play -> TetradePlayPlugin
hooks only, capabilities negotiated). One boot: boot -> title -> menu
-> Marathon -> **151 pieces / 41 clears** (score gate **41/41 exact**,
level-0 clears zero clear-pts per source) -> **6 natural level flips
0->6** (thresholds exact, no RAM writes) -> next-piece RAM read
**150/152 (98.7%)** -> **natural game over** at level 6 (score 33,582,
struct+2312) -> CONTINUE refused (CIRCLE) -> restart -> fresh Marathon
verified (counters zeroed + live piece). Evidence:
`scratch/round10_tetrade/plugin_loop/` (report.json, 12 PNGs, JSONL).

## MSX — Issue #7 (details on issue #7)

Arena pin regenerated fresh (`msx_r10_cap.py`: 57,482 f, 31 disclosed
continues, `wr9_arena` at px 2212, census 3x 300-HP 0xA0D0 slots
10-12). Four experiments: timergate (fight/kite/hold: front duo
kill-causal +500/slot again, post-clear survival ceiling 1,140 f);
rollover with a **1 Hz countdown hunt** (12 x 60 f exact-decrement
snapshots: **no 1 Hz timer word anywhere in main RAM** — the "300 s
timer" is not a u16 countdown at this arena; engineered survival still
ceilinged at 21.1 s); rear2 surgical turn-lob (**slot-12 REAR_DAMAGE_
CAUSAL** — +200 damage points with zero walking; the trio still cycles
to respawn-pending within ~100 f); continue-landing map (**no checkpoint
past 2212** — the arena is one-pass). Verdicts and next levers on
issue #7.

## PSXMC — place campaign (details in the round-10 worklog)

Round-9's two mandatory fixes both closed. FIX-1: per-attempt bit-exact
stability gates. FIX-2: the R2 breaking-state oracle **VALIDATED x3**
(straight-down in-column/in-reach/world-arbitrated, clean horizon
negative) after three root-causes: (1) **static ABI via capstone disasm
of the fixed binary** — World.chunks @ +0x3144 (ax + 7*az; NULL =
unloaded slots, which broke the r10 '49-consecutive-pointer' runtime
scan), Chunk.blocks @ +0x8C (x + 8z + 64y, x innermost); (2) **id deref
via upstream block.h** — IBlock is a vtable-first interface and
Block.id is a u8 BEHIND the pointer at IBlock+0 (callers do lw+lbu);
(3) fallback base algebra + center-slot sanity. New discoveries: the
spawn FACING differs per boot (+z/-z; calibration implemented), the
ring->ray pitch mapping is non-linear but within-run monotonic, and
the real surface is y=7 (not flatland 4/5). Servo convergence on
world-arbitrated in-reach hits is proven; place7 v2-v5 honestly
FAILED — the one remaining lever is canonical-latch disambiguation
(pick the CURRENT breaking triple among several retained ones).

Commit: see the push on main. Tools: `msx_r10_{cap,timergate,rollover,
rear2}.py`, `tetrade_r10_plugin_loop.py`, `psxmc_r10_{lib,oracle,
place7}.py`, `psxmc_disasm_offsets.py`, `psxmc_find_id_offset.py`;
16 new mock tests. No game bytes committed."""

BODY7 = """**Round 10 (issue #6 50/50 share) — the px-2212 gauntlet attacked
with four new instruments; the >=50-wagon target stays honestly
blocked, with three structural facts now measured.** Commit: see main.

1. **No 1 Hz mission timer exists in main RAM.** A 12-sample exact
   -decrement hunt (60 f windows, u16, values 1..999) found ZERO
   candidates at the arena. The round-9 "300 s timer" narrative is
   therefore unsupported as a u16 countdown — lever (b) (survive to
   rollover) has no observable clock to roll over. Lever (b) status:
   *untestable as posed; survival ceiling 21.1 s* (engineered kite:
   edge-hold, early jumps, anti-air, grenade lobs) vs the 1,140 f of
   round 9.
2. **The rear spawner (slot 12) is REACHABLE.** `msx_r10_rear2.py`:
   2 f LEFT tap (turn) + stationary grenade lobs (A+LEFT flat / B+
   UP+A+LEFT arc) landed a slot-12 HP drop and +200 damage points with
   ZERO walking (round-10 v1 lesson: direction-held attack arms WALK
   the player, drift px, and the trio respawn-pends). The trio still
   cycles to respawn-pending within ~100 f of engagement and the
   player dies ~16 s in — but the "slot 12 is untouchable" assumption
   from round 9 is now SUPERSEDED.
3. **The arena is one-pass.** The continue-landing map from the fresh
   cap walk (57,482 f, 31 continues): landings at px 1164 (chopper
   pin) and 1424-1525 (truck pin); NONE past 2212. Deaths at the trio
   arena cost the full gauntlet re-walk — lever (c) (land ahead of the
   pin) has no checkpoint to land on and is closed as posed.

Next levers (updated): (a) slot-12-first kill order — if the rear
spawner is the wave SOURCE (now plausible: it is hittable), killing it
FIRST with sustained stationary lobs may stop the respawn cycle and
let the front duo die without waves; (b) capture the wave-source
census at the moment of death (which slots spawn the killers); (c)
treat the walk as a continues-ladder is no longer viable past 2212
(one-pass fact) — the gauntlet must be resolved in one life."""

BODY8 = """**DoD closure for Tetrade — the complete loop now runs through
plugin contract v1 with zero core edits.**

`tetrade_r10_plugin_loop.py` (round 10, commit on main): boot -> title
-> plugin.boot_script (START -> menu -> CROSS -> Marathon) -> REAL
gameplay steered by the plugin's 2-ply policy (Dellacherie + TETRIS
bonus, NEXT piece read from live RAM struct+896) -> **41 clears, score
gate 41/41 exact** (level-0 clears zero clear-pts per source) -> **6
natural level flips 0->6** (thresholds exact) -> next-piece promotion
cross-check **150/152 (98.7%)** -> **natural game over** (stack
overflow, isGameOver @0x1FF5A8, no RAM writes) -> CONTINUE refused
(CIRCLE) -> restart NAV on the persistent menu -> fresh Marathon
verified (counters zeroed + live piece).

Per the issue's Definition of DONE:
1. real pad input, no cheats — **PASS** (one continuous run)
2. real Tetris + verified line-clear counters — **CAUSAL** (41/41)
3. natural game over + return to fresh menu — **PASS** (PNG ring)
4. plugin contract v1, zero core edits — **PASS**
   (capabilities negotiated: boot_script/features/infer_state/policy/
   detectors on TetradePlayPlugin; git diff touches plugins/ + tests
   only)
5. repo hygiene — PASS (no game bytes; disc/workspaces/savestates
   local-only)

Evidence: `scratch/round10_tetrade/plugin_loop/` (report.json with the
full event timeline, 12 PNGs, JSONL). Tetrade remains the only game at
the FULL issue-#8 bar, now through the plugin contract; hello_pong
holds the second-member spot via the round-5 loop."""


def main():
    outs = []
    s, d = req(f"/repos/{REPO}/issues/6/comments", method="POST",
               payload={"body": BODY6})
    outs.append(("issue6", s, d.get("id") if isinstance(d, dict) else d))
    s, d = req(f"/repos/{REPO}/issues/7/comments", method="POST",
               payload={"body": BODY7})
    outs.append(("issue7", s, d.get("id") if isinstance(d, dict) else d))
    s, d = req(f"/repos/{REPO}/issues/8/comments", method="POST",
               payload={"body": BODY8})
    outs.append(("issue8", s, d.get("id") if isinstance(d, dict) else d))
    for name, status, cid in outs:
        print(name, "status", status, "comment", cid)
    return 0 if all(x[1] == 201 for x in outs) else 1


if __name__ == "__main__":
    sys.exit(main())
