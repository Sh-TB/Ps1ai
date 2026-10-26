#!/usr/bin/env python3
"""post_issue6_round11.py — Round 11 reports (issue #6 main, #7, #5)."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY6 = """**Round 11 (50/50) — three games in parallel, 10 heavy segments.** MSX Issue-#7 >=50-wagon target MET (194 cumulative, 80 disclosed continues) + the arena's kill-aligned progress words found; hello_pong becomes the SECOND complete game played end-to-end (COMPLETE_LOOP_CAUSAL); PSXMC mining chain CLOSED tick-exact (placement blocked one inventory-transfer away, downgraded honestly).

**MSX (issue #7 50% share + #5).**
- `msx_r11_wagons.py`: two live passes, lifecycle-closed wagon tracker (45 f persistence rule, H_SPLIT small/big): **194 wagons crossed cumulative (97+97 persistent; small 88, big 12) — the >=50 target MET 3.8x over**, 80 continues disclosed (40+40), 41+41 deaths, max_px 2212 both passes.
- `msx_r11_progress_watch.py` v2 (the v1 passive-window NEGATIVE archived; v2 indexes the 0x0E7000-0x0E9000 block THROUGH the kill phases via a core.run shim + score-step kill frames): **17 kill_exact words** (0x0E7D9A-0x0E7E68, first flip f13675) and two **kill-aligned global transitions reproduced twice, holding >=5 polls: SECTION_FLAGS 0x0EB5D0 1->67 and world_alive_latch 0x0EB5FC 255->0**. The ~1,100 f post-clear death reproduced with an EMPTY census (the death mechanism is internal — no enemy required). Camera never released (0/N, rounds 9-11 consistent).
- `msx_r11_section_write.py` (disclosed GS writes, restore verified vs pre): holding the observed post-squadron-fell state does NOT open the gate — walk clamps at px 2212 (physical wall), flags67 HELD, latch0 KILLS the player (the world-alive latch is load-bearing), both HELD. The flags/latch pair is necessary context but NOT sufficient.
- `msx_r11_mission_select.py`: attract/gameplay stable-word surveys (1,048,093 / 1,046,963 u16), 2,633 diff candidates; focused m3probe NEGATIVE x2 (SECTION_STATE=2/3, SECTION_PROGRESS=2/3 held, restore verified — no scene change). Fresh-boot M1 section state: [9,1], prog 0xFFFF, FLAGS_WORD 0x1FF.
- `msx_r11_wave_stop.py`: INCONCLUSIVE (slot-12 not killed this boot — the r10 recipe is per-boot timing-sensitive).
- Next lever recorded: the 17-word kill cluster 0x0E7D9A-0x0E7E68.

**hello_pong — the SECOND complete game (issue #6 plugin gallery).**
- `hellopong_r11_fetch_boot.py`: artifact re-downloaded (zip sha match), hello_pong.bin 2,500,176 B sha256 == manifest, volume "ELLO_PONG", locally license-patched (user's own retail sectors; out of VCS), OpenBIOS boot + padbuff + START/X input causality (attempt-1 held-set bug fixed, archived).
- Upstream ground truth (main.c @ dec2f3f0): trigger = is_button_just_released(CROSS); GAME_OVER -(X rel)-> GAME_MENU; win at 5.
- `hellopong_r11_full_loop.py` + corrected grading (`hellopong_r11_grade_fix.py`): **COMPLETE_LOOP_CAUSAL** — start -> play (ball tracked 141/171, 158/195 steps; serves 5-6) -> NATURAL game over x2 (left 4-0, 5-0) -> X-release restart vs idle control legs (control stays GAME_OVER, X arm -> MENU, both games) -> fresh games 2 AND 3 to natural game over. Paddle causality visual (row 123->115 under UP, restored); RAM score sensor absent (recorded, non-blocking).

**PSXMC (place campaign).**
- `psxmc_r11_latch_offset.py` v1 honest LATCH_OFFSET_BROKEN, superseded by the **ELF disasm ground truth**: BreakingState @ player+0x6C (ticks_so_far +0x74 = +=4096 per 20 Hz tick; position +0x78 as 3x s32 — not the s16 VECTOR; block ptr +0x88), verified against updateBreakingState @0x80013c9c in the shipped binary.
- `psxmc_r11_place8.py` v1-v16 honest instrument ladder: flat-world forward rays hit nothing within reach 6; 15-deg ring quantization; vertical ring hits one cell BEHIND the nominal column; post-remesh WorldReader reads unreliable -> **engine-sensed verification (the engine's own breaking.position as the oracle)**.
- **Mining SOLVED**: engine-confirmed break of [0,7,-1] at the source-predicted tick (stone hand-break ~152 ticks; continuous hold required — release resets progress per player.c:402).
- `psxmc_r11_item_survey.py`: **spawn-kit item found — cobblestone id 4 x92 at P+0x64 slot 0 (reproduced x2 boots)**; the r10 find_hotbar missed it (hard-coded expect_item=58).
- Placement: honest **FAILED_PLACE_REJECTED** — the use handler reads the HOTBAR UI (P+0x5C, slot 0 empty) while the cobblestone is in the INVENTORY UI (P+0x64): item-NULL no-op path (stack 92->92, y_rise 0). The v16 run's weak PLACE_CONFIRMED was downgraded on exactly these physical signals. **Recorded next lever: inventory->hotbar transfer** (START opens; R2 cursor-click; L2 split/store-one), then a straight-down refill with stack/y-rise verification. Also recorded: hand cannot harvest stone (blockCanHarvest) -> no drop -> mining cannot bootstrap items.

**Tools:** msx_r11_{wagons,lib,progress_watch,section_write,mission_select,wave_stop}, hellopong_r11_{fetch_boot,full_loop,regrade,grade_fix}, psxmc_r11_{lib,latch_offset,place8,item_survey}; tests test_psxmc_r11_latch.py (raw-step ring math fix) + test_r11_sensors.py. Suite **548 passed + 1 xfailed** (was 521). scratch/ gitignored; no game bytes committed; every write probe disclosed (GS constant codes, disabled + restore verified per arm)."""

BODY7 = """**Round 11 (issue #6 50/50 share) — the >=50-wagon TARGET IS MET.**
`msx_r11_wagons.py`: two live Mission-1 passes (40+40 continues disclosed, 41+41 deaths, savestate restarts counted separately): **194 wagons crossed cumulative (97 persistent per pass; small 88, big 12 — both kinds >1)**, lifecycle-closed crossings with a 45 f persistence rule; the v1 tracker's respawn double-count was archived honestly as an instrument failure and fixed.
Also this round on the blocker chain: the kill-aligned progress words (SECTION_FLAGS 1->67, world_alive_latch 255->0, 17-word cluster 0x0E7D9A-0x0E7E68), the gate write probe (holding that state does NOT open the gate — walk clamps at px 2212; latch=0 kills the world), mission-word m3probe NEGATIVE x2, and the ~1,100 f post-clear internal death reproduced with an empty census. T7 -> the wagon-count goal stands MET; the Mission-1 end-gate remains with the 17-word cluster as the recorded next lever."""

BODY5 = """**Session 13 (round 11) — MSX 50% share.** Wagon-run: **194 wagons crossed cumulative (>=50 target met 3.8x)**; kill-aligned progress words found (SECTION_FLAGS 1->67 + world_alive_latch 255->0 at armored-trio kills, reproduced twice; 17-word kill cluster 0x0E7D9A-0x0E7E68); gate write probe NEGATIVE (holding the observed state doesn't open the gate — the walk clamp is a physical wall; latch=0 kills the world); SECTION_STATE/SECTION_PROGRESS single-word mission writes NEGATIVE x2; the ~1,100 f post-clear death is internal (empty census). Full numbers on issue #6 (round 11) and #7."""


def main():
    for issue, body, tag in ((6, BODY6, "round 11"), (7, BODY7, "r11 #7"),
                             (5, BODY5, "r11 #5")):
        s, d = req(f"/repos/{REPO}/issues/{issue}/comments",
                   method="POST", payload={"body": body})
        print(f"issue #{issue} ({tag}): HTTP {s}",
              d.get("html_url", d)[:120] if isinstance(d, dict) else d)


if __name__ == "__main__":
    main()
