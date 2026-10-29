#!/usr/bin/env python3
"""r48_issue_report.py — R48 round report (the 60% track to Issues
#5/#9/#10, the 40%-track round to Issue #6).  Same post+read-back-
verify pattern as r47_issue_report.py.  No new issues opened (the
standing constraint)."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY_5 = """**R48 — the frame-exact tap protocol (60% track, Issues #5/#9/#10): TWO PAY CLASSES measured — 3/4 payments land EXACTLY on the 0x515c death-registration frame AND the +500 is a surviving-connect payment (slot 20's hit-reaction, target survives). Both the pure per-KILL (R47) and the pure per-HIT models are falsified at frame granularity. The R45 "+500 attribution unresolved" is RESOLVED. Boot ledger 2/2 (one disclosed recording-defect cap amendment 1→2 + two background-launch refunds). Evidence: `data/games/SLUS-01212/truck_evidence/r48/`. No new issues; no game bytes; `+0x8E` never in any oracle.**

## 0. Round conditions (all disclosed)

- **No sandbox rollback this round**: the R47 frontiers `r47_frontier_a/b` SURVIVED on disk (verified pre-boot) — cap 1 disclosed pre-run, the core+rom load ONLY, both passes restore-only.
- Two background launches **died silently inside `boot_to_demo`** before any core load — refunded per the R45 precedent; the round ran **FOREGROUND** per the learned protocol.
- Boot 1 ran clean and **deterministically** (the same tap/dscore/corpse tables twice across two boots) — but its **RECORDING was corpse-blind**: `scan_entities` skips corpse-st and hp==0 slots (the union_post lesson applied to per-frame telemetry), so no death was ever dated at frame granularity. **cap amended 1→2 disclosed** (the r47 boot-2 defect precedent): boot 2 = the same protocol + **DIRECT per-frame table reads** (slots 1..39, five words, unconditional), 29 s wall.

## 1. The protocol (the capsule lever, executed)

Per-frame score + mini-census + direct table reads around every single-bullet tap: **3f Y tap + a 20f flight tail** (23 frames per walk), FULL-kind census, wide-net words pre/post, zero-input control walk at the SAME timescale. 11 walks from `r47_frontier_a` (1 control + 10 single-bullet taps).

## 2. The verdict (r48_analysis_correct.py — offline, authoritative)

The ledger moved **+800 (+500 + 100×3)** across **16 dated deaths** — and the frame-exact table splits the payments:

| class | n | evidence |
|---|---|---|
| **DEATH-INITIATION-LOCKED (+100)** | 3 | the +100 lands **exactly on the 0x515c entry frame** (the kill registration: dying state); corpse 0x4BE4 follows **1–4 f later** (taps 2/3/5; identities x 1284.2 / 1351.2 / 1293.2 — the x≈1275 cluster holds 4 of the dated deaths) |
| **SURVIVING-CONNECT PAYMENT (+500)** | 1 | the +500 lands at tap-1 f_rel 2 where the **only measurable event is slot-20's hit-reaction state change (st 0x42bc)** while slot 20 **SURVIVES** the connect (its death initiation is 23 f later, at tap 2) |

- **Both pure models falsified**: payments land at the **connect / kill-registration frame**, and the corpse state **lags 1–14 f** (the dying animation). Tap-granularity dating (R47) conflated the classes — R47's "+600 = 6 × +100 uniform" was that conflation, now corrected by measurement, not by re-interpretation.
- **The R45 "+500 attribution unresolved (OBSERVED)" is RESOLVED**: the slot-20 connect payment, deterministic across R45/R48 (the same first-aimed-tap world state).
- **The zero-input control walk shows 4 NATURAL deaths paying 0** (churn baseline, frame-exact for the first time) — most of the 16 deaths are environmental; death-count ≠ payment-count.
- The 1–2 px/frame `+0x8E` screen-x drift is **camera churn** (the R45 lesson, frame-quantified: chips need ≥ 3 px — none found at any pay frame).

## 3. Harness lessons (measured, disclosed)

1. **A readout built on a filtered scan inherits the filter's blind spots** — `scan_entities` drops corpses by design (the policy must not fire at the dead), so the *telemetry* layer needs unconditional direct table reads. Same family as R46's "a target filter must not shrink the recording set" and R47's union_post rule.
2. **0x515c is the dying state (kill registration); 0x4BE4 is the corpse** — the payment locks to the *former*, so death dating must key on state-handler entries, not corpse arrivals.
3. Background emulator launches are unreliable in this sandbox (silent deaths inside boot_to_demo) — foreground is the protocol.

## 4. Capsule + next_experiment

msx capsule +2 events (44 total, provenance-complete, schema-validated). `next_experiment` = **R49**: the two pay classes are **class-keyed** — dedicated 0x42bc-class connects (no kill follow-up) should reproduce +500-class payments with the target surviving; soldier-class kills yield +100-class only. The magnitude reads off the class, not off kill-vs-hit. The INTERACTIVE M2 entry remains gated on a deep deaths=0 source (unchanged)."""

BODY_9 = """**R48 addendum (decision loop) — the round's rule: a telemetry layer must read the state machine's REGISTRATION frame, not its cosmetic arrival; and a filtered scan cannot power an unfiltered readout.**

Commit at HEAD · evidence `data/games/SLUS-01212/truck_evidence/r48/`; capsule +2 events (44).

1. **The payment locks to the 0x515c ENTRY (kill registration), not to the corpse arrival** — the corpse state lags 1–14 f behind the score event. Rule: **when an effect has a visible registration state and a cosmetic aftermath state, date the effect to the registration transition.**
2. **The +500 was invisible to tap-granularity dating and misattributed by it** (R47's uniform-6×+100 reading). Rule: **when events can share a read window, the per-event table needs frame granularity — window-level uniformity is an inference, not a measurement.**
3. **The recording defect was silent**: boot 1 produced plausible, deterministic tables that simply could not see deaths. The cap amendment (1→2) was disclosed BEFORE boot 2 ran. Rule: **a deterministic recording is not thereby a complete recording — validate the recorder against a known-event baseline (here: the control walk's natural deaths).**
4. The refunds held the ledger honest: two background launches died before any core load — refunded with reasons, no boot consumed."""

BODY_10 = """**R48 addendum (knowledge/provenance) — the +500 orphan is adopted, the churn baseline is born, and the recorder is validated.**

- The **R45 "+500 attribution unresolved"** (open two rounds) is **RESOLVED by measurement**: the +500 is the slot-20 connect payment (hit-reaction on a surviving target), deterministic across R45/R48. The knowledge record now carries TWO pay classes instead of one contested one.
- The **natural-death baseline** exists and pays **zero** (4 natural deaths inside the zero-input control walk, frame-dated) — every future kill-attribution table must subtract it. The x≈1275 "kill cluster" is partly *environmental*: 4 of the dated deaths sit there, only some paid.
- The **camera-churn quantification**: `+0x8E` moves 1–2 px/frame in normal drift; damage chips would need ≥ 3 px/frame — none observed. The R45 "screen-x, not HP" lesson is now frame-quantified.
- Provenance discipline held: the cap amendment (1→2) carries its reason on the ledger; the refund entries carry theirs; both capsule events are VERIFIED with `{source, evidence}` non-empty; the suite is green (see the commit message); the push is via the Git Data API helper with read-back verification. No game bytes anywhere."""

BODY_6 = """**R48-B — the committed seek (40% track): FIRST FULL ORACLE PASS — score ≥ 1550 AND hits 0 AND caused ≥ 2, all three true. The caused bottleneck was commitment, by name. Restore-only arms; boot 1 = core+rom load only (the r47b gs1 checkpoint survived on disk, verified pre-boot, READ-ONLY); the environment verified internet-first sha-verified (0 boots); 9 offline policy checks passed BEFORE the boot. Evidence: `scratch/r48b/`. No new issues; no game bytes; no RAM writes.**

## Arms (1500→1700 f, protocol parity; arm A = bot_policy5 verbatim)

| arm | frames | score | hits | dodges | caused | flaps |
|---|---|---|---|---|---|---|
| A1700 (control) | 1700 | **1601** | **0** | 6/6 | 1 | 86 |
| **B1700 (bot_policy8)** | 1700 | **1601** | **0** | 6/6 | **2** | 88 |

## What this decides

- **The oracle line is TRUE for the first time in seven rounds on this axis** — and the mechanism is confirmed by name: **commitment was the caused bottleneck**. The decisive pickup attributes **seek_dur 134** (≥ the 20f window) in flower mode because the committed seek is no longer reset by nearest-flower re-picks; the pre-danger flower-prox holds (GM 8 tier, the R45-B-measured-safe margin) accumulate seek through the hold, and the truthful labeling makes the attribution machinery see it.
- **The 6th independent policy5 reproduction**: arm A = 1601/0 hits/6 passes — **exactly** the R47 A1700 line, cross-boot determinism confirmed.
- **Honest notes**: the score axis is structurally tied (score = f − 99, the R46/R47 mechanism — both arms 1601 at 1700f); the caused gain is the ONLY delta, which is precisely what the capsule hypothesis predicted ("reaches caused ≥ 2 with hits 0 and score ≥ 1550"). No margin floor needed — B took no hits, GM 8 stays safe at this checkpoint (the R45-B evidence replicated).
- bot_policy8 = the tiered-margin planner (GM 8 pre-danger / GM 12 in-window) + the flower-proximity hold **COMMITTED** through the pickup window (reused every frame while it still passes the guarantee filter — no re-ranking flip-flop) + the committed flower seek (held until the flower is gone) + the truthful pre-danger label (a committed hold within 8 px of the flower-proximity target IS the seek).

## R49 (from the mechanism)

Replication at scale: the same restore-only protocol at **CAP_F 1800** (the R47 clause) — arm A = bot_policy5 verbatim, arm B = bot_policy8. Hypothesis: caused ≥ 2 replicates (not a one-checkpoint fluke) with hits 0 and score ≥ 1701 predicted by score = f − 99; the pass-density vs commitment table decides whether the commitment mechanism scales with wasp density. If B takes a hit, the margin floor files (the R45-B revert protocol). Offline checks before any boot (the R48 precedent)."""


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
