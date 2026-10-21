#!/usr/bin/env python3
"""post_issue5_addendum_report.py — the consolidated evidence report for
the Issue #5 addendum batch (Phase 10)."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req  # noqa: E402

BODY = """## Addendum batch — Evidence-Driven RAM Map, WorldModel Validation, Recon (Phase 10 report)

**Baseline:** `fe39264` -> **`2375a34`** (this batch), working tree clean. Executable identity: `SLUS_012.12` sha256 `1508b532…` (622,592 B), disc MD5 `37d9e117…` (user disc, unchanged). Tests **259/259** (251 + 8 new).

| Item | Status | Evidence |
|---|---|---|
| Existing artifacts reused (no duplicate index/KB) | IMPLEMENTED | `re_index.sqlite` + `overlay_index.json` (ENEMY.BIN live mapping), `cheats.json` registry, `issue4_controller.boot`, `enter_gameplay3` navigator, `mission.responsive/ensure_mission`, `RoutePolicy/StallDetector`, telemetry v3, savestates |
| Published GameShark address audit | TESTED | Only `800398BE 2400` is structurally sound = NOP of `sb $v0,0xB6($a1)` (grenade store). `8002DCE6`→NOPs a `jal` call, `8002962A`→NOPs `lw $s0,0x10($sp)`, `800475AE`→NOPs `lw $ra,0x18($sp)` (return-address corruption), `80047522`→NOPs `addiu $s0,$v0,0x57C0` (pointer arith, not a decrement), invuln trio corrupts a `sw`/`jal`/GTE word. **Conclusion: published lives/ammo/time/invuln codes are invalid for this revision; popularity is not evidence** (`analyze_patch_sites.py`) |
| Overlay mapping | TESTED (unchanged) | ENEMY.BIN verbatim at **0x8009C0E8** (live override, 27-anchor delta-consistent); 331 funcs / 1546 edges / 1418 grefs indexed; hot dispatch cluster `0x800A87F8..0x800A9B1C` |
| RAM map additions (this batch) | OBSERVED/TESTED | grenade u8 **0xEDCF4** freeze = the only surviving VERIFIED cheat; `0xCA2FE` "hp" **FAILED** (false positive — died 4x frozen, recon1); `0xEF13F` blink-like countdown freeze **FAILED** (kill bypasses it); `0xCB225` lives-mirror freeze **FAILED** (game-over still came; word is a mirror) |
| Telemetry corrections | OBSERVED | score word is **LOW-BYTE only** (HUD 1500 vs telemetry 220 = 1500 & 0xFF) — per-life "max_score" metrics in Issues #3/#4 are low-byte readings (SUPERSEDED as absolute values); `flags_word` reads 0xFF even on the CONTINUE screen (unreliable as a game-over detector) |
| Root cause of the first failure | PARTIAL | The **village armored-truck + follower-helicopter encounter (~f2100–2900)**: kill = tall vertical explosion from the helicopter bomb (`frameprobe f2 f002092.png`) plus truck contact/push. Every policy variant died there (see below). Exact kill function **not yet traced** — the single missing observation is the player-damage entry (EXE) / helicopter-bomb entity (overlay) |
| Controlled experiments | TESTED | `issue5_recon.py` recon1..recon10 (up to 869 chunks/52,140 f, 12/12 disclosed recoveries), `deathprobe d1–d3`, `frameprobe f1/f2`, `immortal i1`, `livesprobe2 l2`, `encounter e1–e4`, `truckhop h1/h2`, `acceptdiag ad1`, cross-process savestate test (restore = not viable: RAM returns but world churn fails the control gate) |
| Policy variants vs the wall (A/B, same checkpoint) | OBSERVED | baseline ~960 f; fire-held (RIGHT+Y held) ~1860 f (2×); retreat-pulse/slow-advance ~1860 f; grenade-every-40 ~1140 f; hop 1560 f; hop+grenade survived the 2640 f window but still fell through later. **No variant passes the encounter; the kill is not dodge-shaped by cadence alone** |
| Fix layer + regression tests | IMPLEMENTED | Controller/recovery layer: visual churn death detection (flags/score are unreliable), `recover_full` = START (continue) → `enter_gameplay3` B-select (main menu) with bounded resume-wait — 27/27 recoveries across recon9/recon10, every restart disclosed; `FireHeldPolicy` (operator directive: keep firing while advancing) with chunk-partition-independent timeline. Tests: `tests/test_issue5_addendum.py` (8) |
| Legitimate no-cheat Mission-1 result | **NOT CLEARED (honest)** | No no-cheat run was attempted this batch beyond the recovery validation; no clear claim is made. Cheat-assisted recon reached the wall repeatedly but never past it |
| Remaining blocker | PENDING | The kill mechanism inside the encounter. Next smallest experiment: locate the player-damage/death entry in the EXE (reads around the death anim) and the helicopter-bomb spawn in ENEMY.BIN, then evaluate a damage-path NOP as the *true* invincibility (GS-style per-frame patch, cheat profile only) — that unlocks the full-map reconnaissance the operator asked for |

Honesty notes: `hp_freeze` (VERIFIED before) and `invuln_blink` (VERIFIED mid-session with an unsound 900 f test) are now **FAILED** with their rejection evidence recorded in `cheats.json`; the earlier `lives_mirror` "TESTED" verdict is corrected to **FAILED**. No fabricated progress anywhere; cheat-assisted runs are labelled `CHEAT_ASSISTED_EXPLORATION` with per-interval logs."""

s, d = req("/repos/Sh-TB/Ps1ai/issues/5/comments", "POST",
           {"body": BODY})
print("comment status:", s, "id:", d.get("id"))
