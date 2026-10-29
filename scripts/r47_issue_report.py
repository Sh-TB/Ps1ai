#!/usr/bin/env python3
"""r47_issue_report.py — R47 round report (the 60% track to Issues
#5/#9/#10, the 40%-track round to Issue #6).  Same post+read-back-
verify pattern as r46_issue_report.py.  No new issues opened (the
standing constraint)."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY_5 = """**R47 — the single-bullet tap protocol (60% track, Issues #5/#9/#10): PER-KILL scoring measured — +600 = 6 corpses × +100, zero surviving-hit payments. The R45 "+100-no-death" confound is closed. Boot ledger 3/3 (two refunds + one cap amendment, all disclosed). Evidence: `data/games/SLUS-01212/truck_evidence/r47/`. No new issues; no game bytes; `+0x8E` never in any oracle.**

## 0. Rollback disclosure + determinism dividend

The sandbox reset lost the R45 frontiers (never committed — no-game-bytes). The capsule contingency applied verbatim (the R45 precedent): a disclosed rebuild boot. Stage 1 then reproduced the rebuild **deterministically for the 4th time**: `r47_frontier_a` px **1224.9** census 13, `r47_frontier_b` px **1254.8** — the *same postures* as R45, restore score **6702** (identical), 6 deaths / 6 continue-rescues counted and disclosed, TAINTED lineage.

## 1. Execution (boot 3/3, 28 s, 12 FULL-kind taps)

Boot 2 crashed after the control tap — a harness defect (the post-tap entity scan **drops a slot that died inside the 3f tap**; the per-tap delta build hit a missing key). Refunded + cap amended 2→3 disclosed (the r46b precedent); two gate-blocked no-boot attempts refunded (the R45 refund precedent); `union_post` direct-table re-reads fixed in-round. Boot 3 clean: 1 zero-input control tap + 11 single-bullet taps (3f Y — one bullet per tap), **FULL-kind census per tap** (air included — the R46 ground-only lesson; burning states 0xa264/0xa414 + wreck excluded AS TARGETS, RECORDED), soft-st preferred targeting.

## 2. The corrected verdict — PER-KILL (kill-locked), one-hit STANDS

The per-tap score table is **all zeros** — yet the cumulative ledger moved **+600 (6702 → 7302)**:

- **Root cause (measured)**: a 3f tap ends before the bullet *arrives* (flight ≈ 8–15 f at dx ≈ +50). The R45/R46 24f bursts masked this by containing the flight. Kills + score land **between taps**.
- **The attribution**: +600 = **exactly 6 dated corpse transitions × +100** (uniform=True; deaths at read-windows 2/2/4/5/7/10 — slots 19, 13, 23, 27, 33, 34; three deaths cluster at x ≈ 1275, where the bullets converge; st 0x515c respawned at the *same* x 1274.5 with h 91→90).
- **ZERO surviving-hit payments**: 11 single bullets, 6 deaths, and **no +100 that is not a corpse**. The soft soldier slot20 never died AND never paid.
- **The R45 "+100-no-death" confound (taps 3/9) is EXPLAINED**: R45 recorded corpses only inside the x-window — out-of-window/out-of-scan kills were invisible. The R47 full-kind tables close it.
- The per-hit alternative survives only in the unfalsifiable corner (every no-death bullet missed AND every connect killed). `r47_analysis_correct.py` (offline, no boot) holds the table + rules.

## 3. Harness lessons (measured, disclosed)

1. **The tap window must contain the bullet flight** — a 3f read after a 3f shot misses the kill entirely.
2. **Per-tap score deltas are invalid for delayed-pay weapons** — the cumulative ledger + corpse dating is the readout.
3. **The entity scan can drop a slot inside the tap** (death removal) — post-tap tables must union re-read missing slots directly from the table.

## 4. Capsule + next_experiment

msx capsule +2 events (42 total, provenance-complete). `next_experiment` = **R48**: per-frame score telemetry (`0x8005883C` machinery) **composed with** the single-bullet taps + a 20f readout tail covering the flight → the frame-exact event table decides per-hit vs per-kill **per event** and reads the identity of each paying entity (the x≈1275 cluster: falling-shell mid-air shoots vs ground soldiers). The INTERACTIVE M2 entry remains gated on a deep deaths=0 source (unchanged)."""

BODY_9 = """**R47 addendum (decision loop) — the round's rule: read the CUMULATIVE ledger, not the window deltas, whenever the actuator's effect arrives after the observation window.**

Commit at HEAD · evidence `data/games/SLUS-01212/truck_evidence/r47/`; capsule +2 events (42).

1. **All 12 per-tap score deltas read 0 while the true total was +600.** The window (3f) ended before the effect (bullet flight 8–15f) arrived. The in-runner table was not *wrong* — it measured the wrong interval. Rule: **when the actuator's latency can exceed the observation window, the cumulative ledger + dated effect transitions is the primary readout; window deltas are a special case that must justify their width.**
2. **The crash taught the same rule at the data layer**: an entity that dies inside the tap leaves the scan before the post-read — the delta build keyed on scan membership and threw. Fix: post-tables union re-read every pre-slot *directly from the entity table*, unconditional. Rule: **a readout keyed on a filter's membership inherits the filter's blind spots** (same family as R46's "a target filter must not shrink the recording set").
3. **The boot-cap gate consumed two entries that never booted** (killed by the cap check during an in-round accounting fix) — refunded per the corrected-filings precedent with the refund reason on each entry. The gate checks *before* `boot_to_demo`; ledger entries are for boots, not for attempts.
4. The R48 protocol encodes all three: per-frame score telemetry (no windows at all), union post-tables, and the ledger discipline unchanged."""

BODY_10 = """**R47 addendum (knowledge/provenance) — two confounds closed by recording wider, not by assuming narrower.**

- The **"+100-no-death" events** (open since R45 taps 3/9) are closed: R45's corpse recording was window-scoped (x 1150–1450); the R47 full-kind tables show the +600 total is **exactly** the 6 corpse transitions — the "no-death" +100s were kills the old recording could not see. The knowledge record now distinguishes *the pay schedule* (+100 per corpse, kill-locked) from *the recording scope* that made pays look orphaned.
- The **per-hit vs per-kill question** (open since the R46 corrected verdict) is narrowed to its unfalsifiable corner by measurement: 11 single bullets produced zero surviving-hit payments. The remaining corner (miss-vs-connect for no-death shots) is exactly what R48's per-frame telemetry falsifies — the protocol is already in the capsule.
- Provenance discipline held: 3 boot-ledger entries carry same-entry `outcome_corrected`/refund amendments (a crash, two gate-blocked attempts); both capsule events are VERIFIED with `{source, evidence}` non-empty; the suite is green (see the commit message); the push is via the Git Data API helper with read-back verification. No game bytes anywhere."""

BODY_6 = """**R47-B — the CAP_F extension (40% track): the climb scales LINEARLY past f1500 — score = survival_frames − 99 — and the dominance recipe takes 1700 and 1800 frames with ZERO hits. Restore-only arms; boot 1 = core+rom + the gs1 checkpoint rebuild (cap 1 disclosed pre-run); the environment was rebuilt internet-first sha-verified (upstream EXE 9b0bfc08… byte-identical re-fetched, wrap output 042b94bb… byte-identical — 0 boots). Evidence: `scratch/r47b/`. No new issues; no game bytes; no RAM writes.**

## Arms (bot_policy5 verbatim — protocol parity, only the frame cap changed)

| arm | frames | score | hits | passes | caused | hp | flaps |
|---|---|---|---|---|---|---|---|
| A1700 | 1700 | **1601** | **0** | 6 | 1 | 5066 | 86 |
| A1800 (extended: A finished 0 hits) | 1800 | **1701** | **0** | 7 | 1 | 5766 | 90 |

## What this decides

- **The mechanism is confirmed and extended**: 1401 @ 1500f → 1601 @ 1700f → 1701 @ 1800f — **score = survival_frames − 99**, the same constant overhead in every run (the 32f ready phase + the rest), now the **4th and 5th independent policy5 reproductions**. The R46 PER_FRAME_TIME mechanism predicts the extension exactly.
- **The oracle score axis (≥ 1550) is CROSSED with 0 hits** — score superiority over the 1401 line is achieved by time alone, as the mechanism demanded.
- **The dominance recipe SCALES WITH TIME**: 6 → 7 wasp passes, zero hits at both caps — the spawn schedule continues at stable density and the guarantee planner holds (the capsule's "real risk" did not materialize at 1800f).
- **HONEST NEGATIVE on the full oracle line**: `caused ≥ 2` NOT met — caused = 1 for the **third consecutive round**. The pickup ledger shows why: the extra pickups land opportunistically (mode=dodge, seek_dur 0) or with seek_dur 8 < the commitment window — the planner reaches flowers by luck, not by committed seek.

## R48 (from the mechanism + the R45-B tier evidence)

`bot_policy8` = the tiered-margin planner (GM 8 pre-danger / GM 12 in-window — the tier measured SAFE at 453 dodge frames in R45-B) **with the flower seek COMMITTED through the pickup window** (hold the seek until pickup or the window opens, instead of re-planning away) at CAP_F 1700, arm A = bot_policy5 verbatim as the control. Oracle unchanged: score ≥ 1550 AND hits 0 AND caused ≥ 2. If B takes a hit, the margin floor files (the R45-B revert protocol)."""


def main():
    posted = []
    for num, body in ((5, BODY_5), (9, BODY_9), (10, BODY_10),
                      (6, BODY_6)):
        s, r = req(f"/repos/{REPO}/issues/{num}/comments", method="POST",
                   payload={"body": body})
        assert s == 201, (num, s, r)
        n = r["id"]
        s2, got = req(f"/repos/{REPO}/issues/comments/{n}")
        assert s2 == 200 and got["body"] == body, (num, s2)
        posted.append((num, n, len(body)))
        print(f"posted + read-back verified: #{num} comment {n} "
              f"({len(body)} chars)")
    print("ALL POSTED:", posted)


if __name__ == "__main__":
    main()
