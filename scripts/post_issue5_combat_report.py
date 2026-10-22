#!/usr/bin/env python3
"""post_issue5_combat_report.py — session 3 report: the user watched the
recorded gameplay and reported concrete behavioural defects; this
session instrumented, confirmed, and fixed them (CombatPolicy v6)."""
import sys
sys.path.insert(0, "/home/z/my-project/scripts")
import gh_api

BODY = """## Session 3 — user gameplay feedback → instrumented verdicts → CombatPolicy (2026-10-23)

**Baseline:** HEAD `db21e24`, tree clean. Suite **374 passed + 1 xfailed** (17 new offline policy tests). Everything below is READ-ONLY instrumentation (no RAM writes, no freezes; continues/savestate recoveries disclosed in the JSONL traces).

### §1 The user's report (from watching the session-2 GIFs)
1. walks THROUGH enemies without killing them; 2. dies with a jeep/enemy BEHIND; 3. after the map ends it keeps going forward instead of turning back to clear the jeep/grenadier; 4. never faces the nearest threat (fixed-RIGHT movement); 5. the chopper sits right overhead.

### §2 Probe 0 — address ground truth (`scripts/probe0_addresses.py`, `evidence/probe0/`)
- **slot0 = the player**: X u32 fixed@`0xCA2E0` (== slot0+0x78) moves at walk speed BOTH directions (400f RIGHT: 258.6→838.5; 150f LEFT: −92.5); HP = slot0+0x8E (`0xCA2F6` pair word, 144→36 damaged).
- Entity table live enemies: HP window **1..600** (352 = armored vehicle observed mid-probe; HP≥32768 = signed-negative transients, excluded); scan window 40 slots.
- Confirmed the report live: a 400f unarmed walk scored **0**, took heavy damage, and enemies sat BEHIND the walker (x 770–812 vs player 838).

### §3 Instrumented A/B — the baseline defects CONFIRMED (`scripts/gif_run2_capture.py`, `analyze_combat_runs.py`)
| metric | RoutePolicy v1 (baseline, 100 chunks) | CombatPolicy v6 (150 chunks) |
|---|---|---|
| real (in-game) deaths | **4** — ALL in the clamp region | 11 — ALL in the clamp region, **0 mid-run** |
| deaths with enemy BEHIND | **4/4** (dx −54…−93) | 9/11 |
| clamp chunks holding RIGHT, never turning | **62** | 0 (defensive clear instead) |
| score gained WHILE clamped (kills/pickups) | 5000 (incidental forward fire) | **5901** (deliberate rear-clear) |
| max px / max score | 1164 / 5900 | 1164 / 4500 |
- **D2 CONFIRMED** — every baseline in-game death is at the section clamp with live enemies behind (the jeep/grenadier geometry the user described).
- **D3 CONFIRMED** — the forward-only policy held RIGHT at the clamp for 62 chunks, never turned back.
- **D4 FIXED** — CombatPolicy faces the pressing threat: point-blank front (≤45 px), LEFT defensive fire at the clamp, UP fire at the chopper/rain zone, hop cadence, grenades into packs, damage-triggered dodge.

### §4 What did NOT work (recorded, honestly)
- v3 (engage every enemy in 400 px): 46/46 chunks engaging, 13 deaths — **standing still in this game is death**; the village is a meat grinder.
- v4 (close rear engagement mid-run): turning back mid-run to face chasers = walking into the pursuit pack — deaths at px 330–760 that the baseline never suffers. **Running through IS the survival strategy mid-run**; rear-clearing belongs at the stage-end.
- Final v6 shape = proven run-through backbone + point-blank front reflex + **derived stage-end detection** (player X stops advancing while RIGHT is held — no map constants) → defensive rear-clear (stand, fire LEFT, alternate UP, hop vs rain, grenades) + escalation walk-back (180/300/450 px).

### §5 Evidence GIFs (uguu.se mirrors; also committed under `docs/gif_evidence/`)
- B1 baseline at the wall (holds RIGHT, never turns): https://n.uguu.se/kTNrVWdg.gif
- C1 combat advance (run-through + kills): https://h.uguu.se/kDuvwKdP.gif
- C2 combat clamp rear-clear (turns back, fires LEFT/UP at the pack): https://h.uguu.se/icpQyLYK.gif
- C3 clamp late phase (escalated rounds): https://d.uguu.se/XYCrjzGB.gif

### §6 Honest limits / next
- The clamp battle remains lethal for BOTH policies (renewing mortar rain + pursuit pack) — consistent with session 2's open root blocker: the village-section completion condition that lifts the ~988 px scroll clamp is still unidentified. Highest-value next probe (with the FIXED u32 reader): diff camera-adjacent globals between a clamped walk and a pre-clamp walk.
- UP-fire damage to the chopper: kills during UP phases are not separable at 60-frame chunk granularity — remains **UNVERIFIED** (no claim).
- Restart-loop tax disclosed: each real death sometimes costs extra hp_zero restarts (loop artifacts counted separately: baseline 8, combat 21).
- New files: `ps1play/agent/combat.py` (CombatPolicy + scan_entities, ps1play-combat-scan/1), `tests/test_combat_policy.py` (17 tests), `scripts/{probe0_addresses,gif_run2_capture,analyze_combat_runs,build_combat_gifs}.py`.
- Side workstream: Nortis full play-test (boot/menu/in-game, controls OBSERVED-CAUSAL: move/rotate/soft/hard-drop via savestate-twin A/B) and PSX-Minecraft re-probe (boots; attract-loop trigger UNKNOWN this session; clean negative pad proof recorded) — local evidence only, separate reports.
"""

def main():
    st, r = gh_api.req(f"/repos/{gh_api.REPO}/issues/5/comments",
                       method="POST", payload={"body": BODY})
    print("status:", st, "posted:", r.get("html_url") or r)
    return 0 if st in (200, 201) else 1

if __name__ == "__main__":
    sys.exit(main())
