#!/usr/bin/env python3
"""post_issue5_cont_report.py — Issue #5 continuation report (§1-§8)."""
import sys
sys.path.insert(0, "/home/z/my-project/scripts")
import gh_api

BODY = """## Issue #5 continuation — Prove Invulnerability, Trace the Death Path, Cross the Barrier (2026-10-21)

**Baseline:** HEAD `b88aaa2` → **`0aa758d`** (3 commits: `b256b17`, `0aa758d`), tree clean, remote synced. EXE sha256 `1508b532…` (canonical), disc MD5 `37d9e117…`. Tests **289/289** (22 new).

### §1 Latest truth — established
- The previously reported `hp_pair_freeze` verdict artifact (`cheval_20261021_*`) was **NOT present** in the workspace and the canonical runner `issue5_explore_invuln.py` had **never been executed** — the pair was correctly treated as unproven and everything below re-derives it.
- Registry: `hp_pair_freeze` VERIFIED (re-proven below), `lives_freeze_strict_series` FAILED (kept), published `invuln`/`lives`/`time` codes FAILED/BLOCKED (kept).

### §2 Controller & cheat lifecycle — verified, 2 real bugs fixed
- `run_segment_frames` non-pit branch **computed segment buttons and never applied them** (pad latches → the player stood still for whole runs). Fixed: buttons set before frames in both branches.
- Stall ladders / continue rescues / recovery windows ran frames **without the GS tick** — the freeze silently stopped exactly there (the failure mode §2 names). Fixed: single `gs_run` path (set-buttons → per-frame `run_frame`+`tick`), tick threaded through `mission.recover/responsive/ensure_mission/alive_probe` and `recover_v2` (opt-in param, legit callers unchanged), post-`load_state` 2-frame pre-engage added.
- Pit cadence re-based on a **global frame phase** (chunk-partition independent); the per-life death sensor **unwraps the u8** (raw diff false-fired 8× in inv20: +90 forward reads as −166).
- **22 new regression tests** (`test_explore_cadence.py`, `test_issue5_deathpath.py`): buttons applied, tick==frames in every branch, partition-invariance of both schedules, recovery tick threading, KB/adapter invariants.

### §3 Decisive A/B — PASS, reproduced twice (`ab_invuln_ab1/ab2`)
One boot → mission → savestate `cb` → **pair co-drop re-confirmed this boot (31×)** → 4 arms, identical deterministic schedule (RIGHT + Y bursts + hop, global phase), per-frame pair/iframe/per_life/flags/score + screenshots + sha256 manifests:
| arm | frames | damage events | deaths | pair held |
|---|---|---|---|---|
| A control | 3600 | **56** | **1** (g=2293 — the barrier zone; pair→(0,0), per_life reset, flags 0) | — |
| B1 freeze | 3600 | 0 | 0 | YES |
| B2 repeat | 3600 | 0 | 0 | YES |
| C freeze+telemetry | 3600 | 0 | 0 | YES |
**Verdict PASS** (`causal_reduction: true`): baseline demonstrably damaged and died; treatment causally eliminated both; repeat consistent; telemetry arm agrees. The pair 0x800CA2F6/0x800CA2FE is now re-proven from scratch, exactly as §3 demanded.

### §4 The real death mechanism — entity table VERIFIED (static, cross-checked)
New tool `issue5_deathpath.py` (+ consolidation) over the existing `re_index.sqlite` + ENEMY.BIN@0x8009C0E8 (no new index):
- **Entity array base `0x800CA268`, stride `0x14C`, HP `+0x8E` u16 (spawn 0xA0=160)** — overlay disasm: `lhu 0x8e($s1)` with `$s1=0x800CA268` ⇒ entity[0].HP = **0x800CA2F6 = the live-verified freeze word**; `addiu $s2,$s1,0x14c` ⇒ entity[1].HP = 0x800CA442 (cross-checks EXE `lhu -0x5bbe` = 0x800CA442). Root pointer slot `0x800C9A98` (root-relative `sb +0xde` state writes).
- Spawn/reset HP writers: `func_8002DB48` (player, HP:=0xA0), `func_8002F3C4` (respawn/vehicle), `func_8002D3C0` (entity type 0xA00). Damage-entry overlay handler **`enemy_800A41D8`**: collision gate (`jal 0x800196a4`) → player HP +0x40/−0x80/+0x40, field +0x92 ±0x20, state byte +0xDE, handler(+0x0)→0x800A87F8 (dispatch cluster).
- flags_word (0xEE518) writers mapped (`func_8006EFF0` OR-bit block, `func_80071808` GAME-OVER setter candidate).
- **Three death paths distinguished:** (1) HP damage → 0 (frozen, A/B-proven); (2) instant pit/channel (bypasses HP — pit cadence); (3) **mission-timer expiry kills despite the HP freeze** — NEW, captured live (`CONTINUE? 8` screen at nokana_cab cycle 7).
- PENDING honestly: the ~−16/hit attrition store is not among the 6 `sh +0x8e` sites (word-store/base-chain variant).

### §5 Exploration-only immortality — HP tier proven; timer tier demoed
- Tier 1 (survival): `hp_pair_freeze` — §3-verified; survival through the mid-boss arena's sustained fire demonstrated (inv20: 500 chunks, pair constant, cheats_active true every chunk).
- Tier 2 (timer): strict-series down-count scan at the arena converged to 3 words (0xCAD9A/0xCB032/0xCBBDE), frozen, 600f verify **held** — but the title-screen return later shows the real timer word is still unconfirmed (copies frozen, or another path ended the run). Registry: `timer_freeze` **FAILED** (honest) with next probes recorded.

### §6 Map exploration — barrier IDENTIFIED, crossing BLOCKED (precise blocker)
- inv20/inv21: camera advances to **unwrapped 2303 and locks** — the arena is a **camera-lock encounter with a mission timer**.
- **Web research (arcadequartermaster, Metal Slug Fandom, Steam): MSX Mission 1 mid-boss = Iron Nokana**, the heavy armored truck (ported from MS1 M5, replacing the MS1 Harrier) — matches the live visuals (truck + gunner + helicopter).
- 8 controlled probes (boss_hunt, position_sweep, hop_freeze, nokana, nokana_kill, nokana_pointblank, nokana_cab, timer_freeze): grenade volleys (dozens), anti-air bursts, straight/crouch/standing fire, left/center/point-blank/roof/cab positions: **entity slots 14 (247), 17 (223), 18 (160), 5 (254) NEVER take damage**; only soldier slots cycle (kills observed: −138/−254 deltas).
- **Blocker (documented):** Iron Nokana's damageable HP is OUTSIDE the 0x14C-stride entity table (or phase-gated). Survival through the arena is proven; crossing requires the boss-HP structure. Registry: `nokana_midboss` **BLOCKED** with all probe evidence.
- Also fixed this section: stall ladder now triggers on **camera-lock** (inv20 sat 450 chunks at churn 1300-1900 with the old churn-based detector blind), added grenade-volley/anti-air ladder levels.

### §7 RE-evidence adapter
`scripts/re_evidence_adapter.py` — projects the committed KBs into a status-tagged contract (12 refs: hp pair, entity table base/stride, root slot, flags, score, grenade anchor, iframe word, per-life, entity1 HP; overlay mapping) consumed by runners; PENDING entries can never read as VERIFIED (test-enforced).

### §8 Acceptance checklist (honest)
- [x] Causal, reproducible explanation of the death path (3 paths, static + live)
- [x] A/B evidence separating real invulnerability from false positives (×2 runs)
- [x] Repeatable survival run through the previously failing encounter (inv20) — **survival, not crossing**
- [ ] Verified checkpoint after the barrier — **NOT achieved**; blocker documented above
- [x] New map/encounter observations with provenance (arena lock 2303, mid-boss identity, timer death path, entity slots, CONTINUE flow)
- [x] No unsupported addresses promoted (timer_freeze FAILED, nokana_midboss BLOCKED in registry)
- [x] All tests green (289) incl. 22 new regressions
- [x] Worklog + commit SHAs (`b256b17`, `0aa758d`)
- [x] CHEAT_ASSISTED_EXPLORATION vs legit separation maintained (every run opt-in + disclosed; no no-cheat clear claimed)

**Next highest-value actions:** (1) live-diff the boss arena while firing to find Iron Nokana's true HP store (outside the entity table — watcher on 0xCA200-0xCB400 + heap); (2) re-run the timer scan with a healthy timer (>1000) and verify a freeze actually stops the CONTINUE flow; (3) if the boss HP is phase-gated, capture its attack-cycle frames to find the vulnerable window.
"""

s, d = gh_api.req("/repos/Sh-TB/Ps1ai/issues/5/comments",
                  method="POST", payload={"body": BODY})
print("posted:", s, d.get("id") if isinstance(d, dict) else d)
