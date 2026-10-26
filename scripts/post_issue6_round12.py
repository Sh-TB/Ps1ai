#!/usr/bin/env python3
"""post_issue6_round12.py — Round 12 reports (issue #6 main, #9 cross-ref)."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY6 = """**Round 12 (finish-them) — three games in parallel, 10-train round.** GitHub-first recon (origin = Round 11 `60a4678`, issues #9/#10 gates reviewed), then: hello_pong **finished by WINNING** (WIN_CAUSAL), PSXMC placement honestly PARTIAL with the sharpest mechanism map yet, MSX mission-select **menu discovered** (the real M3 gate is a MENU, not a world word). Commit `182b5d5`; suite 548+1xfail; no game bytes; evidence local (scratch/ gitignored), tools committed.

**hello_pong — WIN_CAUSAL (third finished-game milestone).**
- New compact driver `scripts/hellopong_r12_win2.py` (the earlier r12-win flow bug: frozen frames_run during discovery + the game self-played past the window; minimal probe proved the core healthy at 1200 f, so the tool was rewritten on lib primitives).
- Sensor: whole-RAM i32 UP-tap delta pins `Paddle{y,score}` (y `0x1ffeb0`, score `0x1ffeb4`; neighbour `0x1ffea8` does NOT reset across games -> not a score, dropped honestly).
- A 0-0 window requires GAME_OVER first: CROSS is a no-op in PLAYING; chain = in-flight walkover finishes -> GAME_OVER -(B rel)-> MENU -(B rel)-> fresh PLAYING, reset verified.
- **Score 0 -> 1 -> 2 -> 3 -> 4 -> 5** with per-frame `mem.u32` point anchors (f1046/f1086/f1165/f1250/f1335/f1420, PNG per point), paddle y tracks -8/+8 exactly inside the run (control causality), GAME_OVER screen reached, B-release restart -> MENU -> fresh game **score reset 5 -> 0**. 5/5 verdict parts PASS.

**PSX-Minecraft — PLACE_PARTIAL (honest; two chains now CAUSAL, one gap left).**
- Selection CAUSAL: 3-frame R3 tap walks hotbar selection (the v2 failure was 1-frame pad-poll aliasing — same class as the pong 1-frame tap bug).
- Consumption CAUSAL: 3-frame L2 (BINDING_USE) consumes exactly 1 stack per tap with a clean negative control (cobble 10->9, table 26->25).
- World write NOT localized: chunk0 (0x53420) block-pointer array bit-identical pre/post tap (RAW_DIFF=0) on every run; walk/rediscovery/whole-chunk scan/engine re-ray never see the new cell; the table tick-2 modal never opened. The r11 "cobble x92 in the INVENTORY" is CLOSED as a render-x misread (spawn kit already hotbar-side per minecraft.c:155-167; BLOCKID_COBBLESTONE=4 verified from upstream block_id.h).
- Next lever (recorded): engine-ray pitch+yaw sweep to find the consumed blocks' actual cells (the r7 place4 modal-open path), then reverse the chunk-array index formula from the found cell. Tools `scripts/psxmc_r12_place9{,v3}.py`.

**MSX (issue #7 50% share + #5) — mission-select static map.**
- The EXE string table carries "MISSION SELECT" (0x8001019c) + per-mission sequencer files `\ANG\M1\MISS01.BIN` .. `\ANG\M4\MISS16.BIN` (mission n -> MISS(5n-4)).
- 17-entry menu descriptor table @0x80095ef4 ([str_ptr, 0x801e8000, 0, 0] stride 16); menu state machine @0x8007exxx (states byte 0x80095a7d -> handler tables 0x80095a70/0x80095a84/0x80095b24; 5-case state switch @0x8007e268); CONTINUE cluster @0x8005a9xx (pause menu).
- Reading: the round-11 m3probe negatives wrote world words, but the real gate is this built-in MENU. Next lever: trace the states byte (or one disclosed state-byte write probe with screenshots) to open MISSION SELECT, then select M3 through the real UI. Tools `scripts/msx_r12_{hunt,hunt2,msel}.py`.

**Nortis** — upstream rechecked 2026-10-27: still no license (MONITORED-NO-CHANGE).

Manifest `round12_addendum` + hello_pong ROUND-12 note; docs Addendum 4; worklogs updated."""

code, c1 = req(f"/repos/{REPO}/issues/6/comments", method="POST",
               payload={"body": BODY6})
print("issue6 comment:", code, c1.get("html_url", "")[-40:] if isinstance(c1, dict) else c1)

BODY9 = """Round-12 cross-ref (commit `182b5d5`, decision-loop relevant): hello_pong WIN_CAUSAL demonstrates the cheapest reliable finish loop — observe-only score sensor via one-boot whole-RAM i32 delta pinning + per-frame u32 reads, with all control actions as 2-3 frame taps (1-frame taps alias past the pad polls; the same fix unblocked PSXMC hotbar selection). PSXMC placement now fails only on world-write localization (RAW chunk-array diff is the discriminator the walk ABI needed). MSX: the mission gate is the built-in MISSION SELECT menu (state machine mapped), not a world word — probe plan updated accordingly. Details on issue #6 (round-12 report)."""

code2, c2 = req(f"/repos/{REPO}/issues/9/comments", method="POST",
                payload={"body": BODY9})
print("issue9 comment:", code2, c2.get("html_url", "")[-40:] if isinstance(c2, dict) else c2)
