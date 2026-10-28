# R39 Addendum — the anti-air connect rate: delivery fidelity root cause, v2.2 rule, and the harness corrections

Repository: `Sh-TB/Ps1ai` · Target: Metal Slug X USA PS1, `SLUS-01212` · Round: R39
Issues: #5 (gameplay evidence) · #9 (decision loop) · #10 (knowledge/provenance)
Base commit: `1fa362b0d407e56a6d3793638d4d66a037bd0b56` (R38 close-out)

## 0. Executive status

| Item | Status |
|---|---|
| R38 baseline reproduced on current `origin/main` | **REPRODUCED** (exact pol_stats, deterministic) |
| Connect-rate cause isolated | **IMPLEMENTED + OBSERVED** (delivery fidelity, matched anchor A/B) |
| v2.2 rule connects in-policy | **OBSERVED** (2 boots, verified hp_a4 drops) |
| Helicopter killed in-policy | **PARTIAL** (2 of 3 connects; the gap is quantified) |
| D7 section release | **BLOCKED** (unchanged until the chopper dies) |
| R38 "restart" outcome labels | **CONTRADICTED** (they were deaths; harness fixed) |
| Full suite | **600 passed + 1 xfailed** (xfail preserved) |

Boot ledger: 6 boots, cap amended 2→3→4→5→6 before each run (`scratch/r39/boots_used.json`, committed copy in `truck_evidence/r39/r39_boot_reports.json`).

## 1. Reconciliation (Task 1)

- `origin/main` = `1fa362b`; local main carried bit-identical parallel commits (empty tree diff) — aligned, zero content change.
- Disc SHA-256 `45cde149…667d` matches the R38 report; `r38_ckpt` (frame 13577) alive; Beetle PSX 0.9.44.1 + OpenBIOS.
- Internet-first (golden rule): GameFAQs' MSX walkthrough corroborates "a truck will appear, soon followed by a helicopter. Destroy both of them" — consistent with the R38 finding that the truck alone does not release the pin. No prior bot solution exists for the connect-rate problem.

## 2. Baseline reproduction

The shipped policy from `r38_ckpt` (300×15f chunks) reproduced R38 trialAA1 **exactly**: `aa_kill 56 / aa_miss 10 / aa_connect 1 / aa_bail 1`, end c227, score 4100. The R38 result is real and deterministic on current main.

## 3. The connect-rate cause (boot 1, matched anchor A/B)

From ONE in-run anchor (`r39_anchor`, the first aa_kill chunk with the chopper inside 160px), two diagnostic arms with a matched 2400f budget:

| Arm | Delivery | Throws | Verified hp_a4 drops |
|---|---|---|---|
| DIAG-CHUNK | in-policy 15f-chunked J1 | 8 | **0** |
| DIAG-ATOMIC | Session-3 `chopper_kill.py` J1 verbatim | 12 | **2** (300→200, 200→100) |

**The delivery mechanism is the first-order factor.** The chunked delivery re-aimed per chunk, could be interrupted at chunk boundaries, and its blind `fc%90` rain-hop left the player airborne at cycle starts.

Frame-level capture (44f read-only): the grenade releases on the FIRST `UP+A+aim` frame; the hop apex is ~f20-24; the player drifts ~-35px from bomb-blast knockback (php 248→120→156 oscillation); the chopper patrols at |v|≈0.3-0.8 px/f and **hovers at x 1132-1155 near the clamp wall** (frozen at 1132.3, st flips 0xAA94→0xABDC).

## 4. The design iterations (each failure recorded)

- v2.0 (band gate + 96f plan lock): 2 throws/run — the grid starved the attempt rate.
- v2.1 (short re-lock + grounded guard): the hold plan's own rain-hop re-armed the B-free guard every cycle → 12 chunks of perfect dx −8.7..−27 geometry, **zero throws**. Walk-toward-the-chopper dragged the player into the 992+ wave zone (wrong direction — the chopper HOVERS at the clamp).
- **v2.2 (shipped)**: the S3 recipe at its proven 76f cadence + atomic delivery (aim locked at cycle start; the 19f window finishes once the grenade is out) + band `[10, 35]` + anchor positioning (walk back to px ≥ 1140) + the R38 cooldown rain-hop + queue discipline / bail / quiet resolution unchanged.

## 5. The harness correction (affects R38's outcome labels)

Every `banner_expired_restart` recorded by the trial harnesses (R38 trialA1/A2 c268, trialAA1/AA2 c227, R39 BASE) was a **mid-chunk death** (`RESTART_SEEN px=0.0, sec [0,0]`; the death handler never ran). Those trials measured time-to-first-death; no mission-timer wall at c227/c268 is evidenced. Fixed: the restart/banner checks require `alive()`; deaths wait out the respawn and pass the game's continue screen via the established issue-4 `recover_v2` START tap (counted separately, disclosed). Capsule event `CONTRADICTED` records the supersession.

## 6. v2.2 live results

- Boot 4: connect at c143 (hp_a4 300→200, score +200) — the first in-policy atomic connect.
- Boot 6 (full 300-chunk campaign with the fixed harness): 1 death + 1 continue ("recovery v2: back in control"), 13 throws, 1 verified connect (c271, 300→200).
- The chopper was not killed in-policy: 2 of 3 connects landed. **Remaining causal gap**: throw-opportunity share × connect rate — `aa_kill` held only 76/300 chunks while `engage` held 118 (the policy locks non-queue enemies while the chopper, the queue blocker, waits). Recorded as the capsule's `next_experiment` (R40): census who `engage` locks onto during the pin, rank queue entities above non-queue enemies (or verify whether the mortarman is itself a queue entity), then the existing atomic cadence should land the remaining 2 connects.

## 7. Tests and artifacts

- 15 aa unit tests (identity, band+anchor, cadence, aim-lock vs sign flips, committed window vs soldiers, dodge suppression before the press, kill-connect on vanish, bail bounds, rain-hop survival). Full suite **600 passed + 1 xfailed**.
- Committed evidence: `data/games/SLUS-01212/truck_evidence/r39/r39_boot_reports.json` (ledger + boot reports + per-throw tables + hp_drops); scripts `scripts/r39t1_baseline.py`, `scripts/r39t2_treatment.py`, `scripts/r39_capsule_update.py`; capsule events + replaced `next_experiment`.
- No game bytes, no cheat codes, `+0x8E` never in any oracle; all hp evidence keys on `+0xA4` with the verified chopper identity (st 0xAA94/0xABDC, airborne, hp_a4>0).

## 8. Status labels

`REPRODUCED` (R38 baseline) · `IMPLEMENTED` + `TESTED` (v2.2 rule, 15 tests) · `OBSERVED` (delivery A/B, band, hover, in-policy connects) · `CONTRADICTED` (R38 restart reading) · `PARTIAL` (chopper kill 2/3 connects) · `BLOCKED` (section release, unchanged)
