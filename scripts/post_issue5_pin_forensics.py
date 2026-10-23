#!/usr/bin/env python3
"""post_issue5_pin_forensics.py — D7 pin forensics + D6 kill
reproduction report (2026-10-24)."""
import sys
sys.path.insert(0, "/home/z/my-project/scripts")
import gh_api

BODY = """## D7 pin forensics — the scroll clamp is a section STATE MACHINE, not a static limit (2026-10-24)

**Baseline:** HEAD `b406a16` -> **`cc5667a`** (pushed, API-verified). Suite untouched (384 passed + 1 xfailed). Environment note: the sandbox reset again before this session (local repo rolled back to `6b97fbe`, all savestates + local evidence trees lost) — restored by fetch+reset to origin; committed docs/comments remain the record; a NEW pin-arrival savestate `clamp0` (px 1163) was regenerated. Full write-up: `docs/clamp_pin_forensics.md`. This is the session-2 declared follow-up ("diff the camera-adjacent globals between a clamped walk and a pre-clamp walk") plus poke and behavioural follow-through.

### What ran
clampdiff1/2/3 (full-RAM snapshots at pre-clamp px 715 / pin arrival 1163 / pinned+480f, per-10f trajectories, numpy pin-boundary classification) · capstone EXE reference scan (155,136 instructions) · limit poke (3 disclosed arms) · clean 3-arm pin matrix (P/R/L, per-frame, death-episode accounting) · deep-left arm · mosque gate test (D6 connection).

### Findings (all instrument-established)
1. **No camera stall at ~988 exists** in this boot path: the scroll word `0xEB598` (16.16 fixed) FOLLOWS the player the whole way (player−2.5…+1) and pins at `0x048BFFFF` = 1163.99998 exactly. The historical "988/992" figures are the **checkpoint respawn px (992)** + the truck pin — the number mystery is resolved as respawn geometry.
2. `0xEB598` is a render-side COPY struct (copy sites `0x80022894/0x80022A38/0x80023138/0x80023324/0x800233AC`; fields +4/+8/+0xC, flags u16 @+0x38, state @+0x5C). The clamp decision lives upstream of the copies.
3. **The pin state machine is visible in RAM**: at pin arrival the player-struct function pointers flip (`0xCA268: 0x80034ddc→0x80032d28`, `0xCA2A0: 0x800b860c→0x800b83e0` — overlay/heap), a state word 10→1 (`0xCA2A4`).
4. **No limit constant in RAM**: 0 hits for `0x048C0000`/`0x048BFFFF`/`0x048B0000`; the single u16-1164 hit @`0x8DBF8` is REUSED runtime data (the file has a `sw` instruction there). **The disclosed poke test is NEGATIVE** (1164→2000 + neighbour + no-poke controls: all pinned at 1163).
5. **Clean pin matrix**: P_pure — pin stable 20 chunks; L_leftwalk (to 1100) — no-op; R_respawn — **119 death episodes**: death at the clamp respawns at 992 INSIDE the truck kill zone → instant re-death loop (this resolves the earlier "walk_right dies truck-pinned at 992" observation).
6. **The hp-freeze does NOT stop one-shots** (truck −291 lands after the freeze write in-frame) — the deep-left arm died at the truck despite freeze+hop. Policy consequence: vs one-shot threats only distance/timing helps.
7. The mosque-gate arms' 1483/1486 max-px spikes are **NOT traversal** (no sustained ≥1180 run; a corridor death appears to trigger a FULL MISSION RESTART — score reset 0, px ~120, grenades 10). No traversal claim made.
8. **EXE ground truth**: the `.full` text is PLAIN LITTLE-ENDIAN (byteswap hypothesis tested and rejected via the sane entry prologue at pc0 `0x80082A44`); capstone skipdata required; the ROOT-chain VA `0x80012814` is a POINTER TABLE (`0x8007C38C` ×7), not code.

### D6 gain (PARTIAL)
The **+800&0x20 mosque-kill signature reproduced cleanly** from `clamp0` in one volley campaign (score_delta exactly 800); post-kill faller poll = 0 events (single poll — the sustained rain-quiet measurement is still owed). The lob campaign is now a cheap reliable kill reproduction.

### Verdict + next
D7 stays **BLOCKED** as a root blocker but with a precise shape: pin = section state machine, no static limit to freeze, enforcement in the section handler + overlay pointers. Named next experiments: (a) trace the flipped handlers `0x80032d28`/`0x800b83e0` + the camera-copy source struct; (b) truck-phase-aware deep-left retry; (c) one clean probe of the apparent mission-restart path. Enemy-awareness scope untouched.

**Commands:** `python scripts/msx_clamp_globals_diff.py --tag <tag>`; `python scripts/msx_limit_poke.py`; `python scripts/msx_pin_matrix.py`; `python scripts/msx_deep_left.py`; `python scripts/msx_mosque_gate_test.py`. Evidence local: `evidence/{clamp_globals,mosque_gate,pin_matrix}/`.
"""

st, r = gh_api.req(f"/repos/{gh_api.REPO}/issues/5/comments",
                   method="POST", payload={"body": BODY})
print("HTTP", st, "->", r.get("html_url", r))
