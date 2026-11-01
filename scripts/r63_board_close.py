#!/usr/bin/env python3
"""r63_board_close.py — close the five finished-but-open threads with
evidence-grade verdicts: #1, #2, #3, #7, #8. #4/#5/#6/#9/#10 stay open
(genuinely in-progress research). Posts comment -> reads back
byte-identical -> closes as completed -> reads back state."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

C8 = """**R63 RE-DELIVERY — the DoD re-proven on the current stack; closing as completed.**

The Oct-26 round-10 artifacts (`tetrade_r10_plugin_loop.py`, `docs/tetrade_playthrough.md`) were lost to the v0.5/v0.6 repo rewrites and the sandbox rollbacks — they exist in no reachable history — so R63 re-delivered the complete loop as FRESH, committed evidence (commit `c708c03`, `docs/r63_tetrade_redelivery.md`, `data/r63/tetrade_full_loop_summary.json` + per-piece trace).

**One boot, zero memory writes, zero core edits:** boot → title → START → menu → CROSS on ">Marathon Mode<" → START taps → countdown → the `TetradeGame` struct located by signature at **0x1FECA0 — exactly the round-10 prior** (`isGameOver 0x1FF5A8` = base+2312) → anchor map derived from the MIT source and verified live (matrix@+0, current piece type/x/rot @+800/+868/+880, `nextTetriminos[14].type@+896+92k` — the "struct+896" prior, score@+2276, single/double/triple/tetrade @+2280..2292, level@+2304, isGameOver@+2312, isGamePaused@+2316) → **Dellacherie 2-ply policy** (board + current + NEXT from RAM READS ONLY — the loop this issue's text documents) → **28 pieces, 1 VERIFIED line clear** (`single` 0→1; score +0 at level 0 exactly per `SINGLE_LINE_SCORE * level`, matching the source) → **natural game over** (spawn overlap, isGameOver 0→1) → **CONTINUE refused with CIRCLE** → restart → **fresh Marathon verified** (counters zeroed, board empty). NEXT-promotion cross-check **28/28** (vs 150/152 in round 10).

Per the Definition of DONE: (1) real pad input only — PASS; (2) real Tetris with a verified clear — PASS; (3) natural game over + fresh menu — PASS; (4) zero core edits — PASS. Boot ledger 7/7 disclosed (3 entry-variant failures: the PRESS-START/PAUSED key-repeat trap; 1 struct-scan diagnosis; 2 full-loop runs).

Honest notes: the heuristic policy is legal but weak (1 clear / 28 pieces; the stronger round-10 policy is gone, recorded as lost); perception is RAM-read-based per this issue's own documented loop; no training anywhere. Closing as completed."""

C7 = """**CLOSURE — the >=50-wagon acceptance was MET at Round 11 (2026-10-26); closing as completed.**

The R11 report on this thread is the durable record: two live Mission-1 passes (**40+40 continues disclosed**, 41+41 deaths, savestate restarts counted separately) measured **194 wagons crossed cumulative (97 persistent per pass; small 88, big 12 — both kinds >1)**, lifecycle-closed crossings with a 45 f persistence rule; the v1 tracker's respawn double-count was archived as an instrument failure and fixed. That is 97 persistent per pass vs the 50 target — **TARGET MET** (the earlier in-tree `docs/wagon_run_issue7.md` PARTIAL state predates R11 and stands superseded on this exact point).

In-tree deliverables (verified present at HEAD): `ps1play/agent/wagon.py` (the lifecycle sensor: verified entity table base `0x800CA268`, stride `0x14C`, HP `+0x8E`; observational only), `tests/test_wagon_sensor.py` (6 unit tests), `scripts/wagon_run.py` / `wagon_v1.py` / `issue5_explore_invuln.py` (the runners that reached the train yard live). The R11 raw run artifacts were sandbox-local and are lost to the rollbacks — the thread's measurement record + the committed sensor/test code are the surviving evidence, stated as such.

The round also banked the blocker-chain findings (SECTION_FLAGS 1→67, world_alive_latch 255→0, the 17-word cluster `0x0E7D9A-0x0E7E68`; holding the gate state does NOT open the gate). The Mission-1 end-gate remains open on #4/#5. Closing this issue as completed — its own numeric target was met and re-stated here."""

C1 = """**CLOSURE — all phases executed (final report 2026-10-20); superseded-as-roadmap by #6; closing as completed.**

This mission's own final report (the first comment) records every phase executed and verified at commit `183ce90`: baseline reproduction (98→136 tests green), env_probe READY, EMULATOR_SMOKE PASS, the autolab gates, and the Mission-1 policy execution + action-control verification at this generation's bar. The repo history was later rewritten (the v0.5 push) so that commit hash no longer resolves — the WORK was absorbed into the current tree (env_probe / emulator_smoke / autolab all still ship and gate the repo today; the profile discovered here seeded `ps1play/profiles/`).

Roadmap note: #6 declares this issue **superseded-as-roadmap** ("Supersedes-as-roadmap: Issue #1"), with the MSX blocker detail owned by #5. Nothing in this issue remains actionable. Closing as completed."""

C2 = """**CLOSURE — all phases executed (final report 2026-10-20); the artifact survives in-tree; closing as completed.**

The final report's table stands: exact game identity recorded (disc md5 `37d9e117…`, EXE identity matching the public recomp metadata); codes **VERIFIED** (bombs `800398BE 2400`, derived bombs-freeze `300EDCF4 000A`, behavioral HP-freeze `800CABE4 0088` with the full baseline/treatment/disable/repeat protocol ×2) and codes honestly **FAILED live** (the published 3-line invulnerability patch) — the honest rejections were as much the deliverable as the verifications. The commit hash (`59ec381`) predates the v0.5 history rewrite and no longer resolves; the curated result lives in the tree at `data/games/SLUS-01212/cheats.json` (schema'd registry with mechanism + notes), and the deeper mechanisms this issue seeded (the grenade anchor, later the hp_pair_freeze `0xCA2F6/0xCA2FE`) were carried forward and re-verified through Issues #3/#5. Closing as completed."""

C3 = """**CLOSURE — the source-index deliverables are in-tree and have been re-verified by use; closing as completed.**

Delivered and present at HEAD under `data/games/SLUS-01212/`: `re_index.json` (4,915 functions / 8,118 call edges), `overlay_index.json` (ENEMY.BIN module-tagged: 331 funcs / 1,546 edges / 1,418 grefs), `entities.json`, `mission1_map.json` + `mission1_route.json`, `death_path.json`, `cheats.json`, `psyq_labels.json`, `psxrecomp_external.json`, `ghidra/` (the 11.4.2 headless decompile: 3,957 EXE + 468 overlay functions), plus the tools (`scripts/game_rebuild_index.py`, `asset_catalog.py`, `gkb_query.py`, `static_re.py`, `overlay_index.py`) and `ps1play/re/` — every later issue consumed these artifacts (the telemetry anchors, the death-path RE, the camera/static hunts).

The one falsification is on record: the Phase-F text-end mapping `0x800A7800` was **SUPERSEDED** by the live probe (ENEMY.BIN loads verbatim at `0x8009C0E8`; code blob executes `0x800A9268..0x800B83B0`) — see the addendum above. MISSION.BIN is not resident at Mission-1 gameplay (BLOCKED, honestly recorded). Copyright hygiene held: no game binaries in git; extraction commands documented. Closing as completed."""

PAIRS = [(8, C8), (7, C7), (1, C1), (2, C2), (3, C3)]


def main():
    ok = True
    for num, body in PAIRS:
        s, c = req(f"/repos/{REPO}/issues/{num}/comments", method="POST",
                   payload={"body": body})
        print(f"#{num} comment POST:", s, c.get("id"))
        cid = c.get("id")
        s2, c2 = req(f"/repos/{REPO}/issues/comments/{cid}")
        m = s2 == 200 and c2.get("body") == body
        print(f"#{num} comment read-back: {s2} match: {m}")
        ok &= m
        s3, i = req(f"/repos/{REPO}/issues/{num}", method="PATCH",
                    payload={"state": "closed", "state_reason": "completed"})
        print(f"#{num} close:", s3, i.get("state"), i.get("state_reason"))
        s4, i2 = req(f"/repos/{REPO}/issues/{num}")
        m2 = (s4 == 200 and i2.get("state") == "closed"
              and i2.get("state_reason") == "completed")
        print(f"#{num} read-back: state={i2.get('state')} "
              f"comments={i2.get('comments')} ok={m2}")
        ok &= m2
    print("BOARD_CLOSURE:", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
