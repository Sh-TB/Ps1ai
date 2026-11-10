#!/usr/bin/env python3
"""r71_issue_report.py — post the evidence-grade R71 round report to
issue #9 (the R67-R70 precedent), read back byte-identical."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY = """**R71 round report (the capsule lever executed: the chip-connect kill schedule + the corridor-feed map + the watchpoint pass) — badges: IMPLEMENTED / TESTED / OBSERVED / VERIFIED.** Evidence: `truck_evidence/r71/` (3 product boots, the ledger disclosed below · the watchpoint JSONLs) · policy `1.8.5 -> 1.9.0 (K1)` · adapter `0.5.1 -> 0.5.2` · push [`d9f01ad`](https://github.com/Sh-TB/Ps1ai/commit/d9f01ad13926) · suite **924 passed + 10 skipped + 1 xfailed**.

**The product ledger (3 boots, disclosed pre-run, 3/3 spent):** boot 1 = the v1.9.0 chip-connect kill probe; boot 2 = the adapter 0.5.2 re-run; boot 3 = the ONE-VARIABLE falsification arm (`TRUCK_CHIP_FIRE=False` — the exact v1.8.5 idle-hold semantics on the 0.5.2 adapter, disclosed in the probe's BOOT event). Every boot is a read-only product-loop probe: legal inputs only, zero RAM writes, no training, no runtime LLM.

## The product track — three findings, one connect

1. **THE AIMED CHIP PATH (CONFIRMED, boot 1).** The K1 aimed cooldown chip-fire reaches the parked truck: 3 of the 8 chips landed while the `truck_chip_wait`/`truck_chip_fire` rules owned the posture (f833/f861/f1015) — the player's OWN bullets chip -10 a4 / +100 score at the hold posture, on top of the R70 escort-stray path. The kill math's second damage path is now player-controllable.
2. **THE CONNECT (boot 3, ON THE GRID).** With the chip-fire OFF (the falsification arm), ALL THREE grid throws fired clean and **THE CONNECT LANDED: a4 280 -> 180 at f1659 — the land = freeze + 506 ± 2f, ON the phase grid (178 + 164×2 = 506, tolerance 2f)** — the phase law's LOCAL validity confirmed at k=2.
3. **THE PHASE LAW IS STREAM-DEPENDENT (FALSIFIED as a stream-invariant).** The k=0/k=1 throws (freeze+178/342, ON the grid, at dx -133.5 EXACT) MISSED in the same boot; the chip-fire stream (boots 1-2) never connected (0/2 phase-exact throws); the r69b volley stream connected 2/7. The R67 cadence law generalizes to the meta level: **the input stream is part of the deterministic trajectory** — a law measured on one stream does not transfer verbatim to another.

## The perception fixes (adapter 0.5.2, the a4-aware liveness filter)

- **THE GHOST BLOCKER:** the boot-1 k=0 window was withheld by slot23 — st `0x6730`, x 995.0, h 64, **a4 0**: an unknown dead-walk state NOT in `CORPSE_ST` blocking the corridor while dead (the R66 predicate violated by the observation). Fix: unknown `a4 == 0` rows leave the observation; the KNOWN states keep the committed semantics.
- **THE INVISIBLE THIEF:** the boot-1 phase-exact k=1 lob (f1123, dx -133.5) was stolen by the LIVE stack at x 1062.3 (`0xb4e4` a4 30 h 102 / `0xabdc` a4 300 h 205 / `0xb4e4` a4 30 h 142) that the `h > GROUND_HEIGHT` drop hid. Fix: the LIVE (a4 > 0) rows in the chaser-throw band are PACKED; the dead-airborne rows stay dropped.
- **THE PROJECTILE GUARD:** the R66 `projectile_air` states (`0xbdf8/0x2950/0x9558/0xac64`) stay excluded regardless of a4 — the committed gate-starvation fix must not regress. `0x1be0` is resolved to the R70 walker semantics (the R66 dump listed it among the projectile rows while the committed R70 packing test treats it as a soldier walk state — the evidence conflict disclosed in the constant block).
- Boot 2 verified the fixes in-game: the k=0 corridor was CLEAN (the ghost gone — the throw fired), the k=1 was correctly WITHHELD (the thief now visible, the guard held it).

## The corridor-feed map (offline, zero boots)

The walker spawn zone is **POSITION-KEYED, not frame-keyed**: the sanitized spawn x concentrates in the world band ~969-1180 (the corridor + the rear zone; the posture is 1071) across boots 2-3. The corridor occupancy at the grid lands is STREAM-DEPENDENT: the chip-fire stream left the k=1/k=2 lands OCCUPIED (the guard correctly withheld both throws, boot 2) while the idle-hold stream kept ALL FOUR lands clean (boot 3). Evidence: `truck_evidence/r71/r71_corridor_feed_map.json`.

## The experiment track — THE WATCHPOINT PASS (restore-only)

- **Stage 1:** the frontier rebuild **BYTE-EXACT AGAIN** (the R47/R66/R68 recipe verbatim: `frontier_px 1254.8` = the record — the determinism dividend is now **8-for-8**).
- **Stage 2:** the verbatim R66 pass B tap replay with the WATCHPOINT telemetry patched at the disclosed R52 seam (`R50T.frame_walk`): **THE +500 CAPTURED AT THE WATCHPOINT** — tap 6 verbatim (slot16, st_pre `0x1e38`, dx +20.3, score 7702 -> 8202) at flight TAIL f1 — the pay-frame law is now **3/3**.
- **THE PAYMENT CLUSTERS** (the co-changing RAM regions at the pay frames): the +1000 cluster is COMPLETE (1034 B, 200 regions) **including the score-word region `0xEE318-0xEE31A` (2 B)**; the +500 cluster (2695 B churn) had its 2-B score-word region cut by the top-N cap (the tool limit, disclosed — the delta itself is arithmetic: 2 bytes).
- **THE WRITER FOOTPRINT:** both payments churn the STACK band `0x1FFD00-0x1FFF00` (the call frames), the ENTITY TABLE rows `0xCA6xx-0xCBDxx` and the score/HUD neighborhood `0xEE3xx-0xEF4xx` — consistent with the R69 narrowed writer set (the overlay damage tail executing through the credit tables).
- **THE PC QUESTION — ANSWERED HONESTLY:** a literal payment-writer PC is **NOT readable** on the beetle/libretro stack (no CPU state export — the tool limit). The store site STAYS NARROWED (the R69 static verdict); the runtime pass pins the payment timeline + the clusters; the follow-up is the CPU-instrumented oracle (the PCSX-Redux debugger, the R64 tools matrix). **This is the honest answer to the capsule's R71 PC lever — not a claimed PC.**
- The tap-6 replay reproduced **BYTE-IDENTICAL across three boots** (the same frontier state + the verbatim protocol).
- **The ledger disclosure:** cap 2 -> 4 by two amendments — boot 3 was a NO-OP env-var tool bug (the R71WP_TOP patch never reached `diff_regions`), honestly labeled; boot 4 re-ran with the fix.

## The honest outcome: NO kill — the bottleneck is named

- The best boot ran **1 connect + 5 chips (a4 300 -> 160 at the death)**; the chips flow reliably (8-13 per boot, both paths); the connect is the bottleneck: **1/3 on-grid in the idle-hold stream, 0/2 in the chip-fire stream, 2/7 in the r69b volley stream**.
- Boot 1 set the **score record 2400** (+300 over the R70 best) WITHOUT the kill.
- Zero-overlap re-run: NOT triggered (the watchpoint pass paid the recorded +500 from the verbatim replay — the class stands n=2, no new capture class).

## The suite

924 passed + 10 skipped + 1 xfailed (up from 903: **21 new R71 tests** — the K1 chip-fire semantics 15 + the adapter a4-aware perception 6; the R69/R70/R66 truck tests re-anchored on the v1.9.0 committed rules — zero weakened, the re-anchoring disclosed in the test docstrings). The 8 failed + 11 errors in `test_r61/r62/r64` are the PRE-EXISTING flappybird ONNX environment regressions of THIS sandbox (verified on the clean tree before the R71 changes; the R61/R70 post-recycle precedent) — not the R71 footprint.

The capsule: +3 consolidated R71 events (68 total), `next_experiment = R72` (the volley+phase hybrid — the gre40 cadence gated by the phase tolerance — + the Ghidra xref on the watchpoint cluster addresses). The final-mile compact per the r66 precedent: the full narratives archived in `event_narratives_archive.json` (committed), the canonical serialization is compact JSON, **65,508 B < 65,536** — the shipped-validation bound holds. m2_gate unchanged. No issue closed."""

s, d = req(f"/repos/{REPO}/issues/9/comments", "POST", {"body": BODY})
print("HTTP", s, "comment id:", d.get("id"))
if s == 201:
    s2, comments = req(f"/repos/{REPO}/issues/9/comments?per_page=100")
    mine = [c for c in comments if c["id"] == d["id"]]
    print("read back byte-identical:",
          bool(mine) and mine[0]["body"] == BODY)
