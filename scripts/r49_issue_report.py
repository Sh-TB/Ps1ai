#!/usr/bin/env python3
"""r49_issue_report.py — R49 round report (the 60% track to Issues
#5/#9/#10, the 40%-track round to Issue #6).  Same post+read-back-
verify pattern as r48_issue_report.py.  No new issues opened (the
standing constraint)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY_5 = """**R49 — the class-keyed tap protocol (60% track): the +500 surviving-connect payment REPLICATED frame-exact, the +100 kill payments replicated n=4 — and the payment model is REFINED to PLAYER-BULLET-VICTIM-LOCKED: none of the four +100 victims was the aimed target; all four were cycling zone entities registered in the bullet corridor. The strong class-keyed form is FALSIFIED by a +500-vs-+1000 identical-context pair (unresolved residual, n=1). Boot ledger 1/1, no amendments. Evidence: `data/games/SLUS-01212/truck_evidence/r49/`. No new issues; no game bytes; `+0x8E` never in any oracle.**

## 0. Round conditions (all disclosed)

- **No sandbox rollback**: the R47 frontiers `r47_frontier_a/b` SURVIVED on disk (verified pre-boot) — cap 1 disclosed pre-run (the core+rom load ONLY), both passes restore-only; boot 1 clean, 29 s wall.
- **Group shortfall recorded honestly**: the CONNECT group reached **2/4** (both on the frontier-frozen slot20, already mid-0x42bc at restore; 6 connect taps missed — no 0x42bc entry) and the KILL group **0/3** (the census thinned: the spawner zone x≈1277–1351 churns cycling entities — 0xaec8 spawn → walk → 0x515c → 0x4be4 — and the aimed fresh soldiers **one-hit-registered** instead of connecting).

## 1. The verdict (r49_analysis_correct.py v2 — offline, authoritative)

The v1 target-slot-only classification was structurally blind to concurrent entity cycles; v2 rebuilds a **global-frame per-slot matcher** per pass (every slot's 0x42bc holds / 0x515c registrations / 0x4be4 corpses dated; every score jump matched within the flight lag window [−2, +6] rows):

| class | n | evidence |
|---|---|---|
| **CONNECT +500 (replicated)** | 1 | a-tap1: the +500 lands with slot20 in **0x42bc at the pay frame** and **ZERO registrations** in [−2, +6]; slot20 then **recovers to 0x5b0c and walks on** — n=2 across R48/R49 |
| **KILL +100 (replicated, refined)** | 4 | **all four co-land EXACTLY (lag 0) on a 0x515c registration** — but none is the aimed target: slot33-re@1284.2, slot23@1351.2, slot10-re@1293.2, slot9@1343.8 — **cycling zone entities in the bullet corridor** |
| **UNRESOLVED RESIDUAL** | 1 | b-tap1: the **identical** connect context paid **+1000** — the +500 extra co-lands 2–4 rows after slot33's zone registration/corpse (outside the lag window); candidates: the 0xae7c-class kill paying +500 / connect magnitude non-determinism / a hidden second pay event |

- **The payment model is PLAYER-BULLET-VICTIM-LOCKED**: only the bullet's actual victim pays. The **11 zone/wound registrations** (slot22, slot18, slot20's wound death, slot33's zone death, …) all paid **0**, and the zero-input control walks show **0 jumps** again (the churn baseline, replicated).
- The no-follow-up connect targets did **not** survive to walk end (slot20 died of the wound 1–3 taps later, dated frame-exact) — but the connect payment itself landed while the target was **alive in 0x42bc**, so the R48 surviving-connect reading stands.
- **The strong class-keyed form is FALSIFIED** (the same 0x42bc connect context paid +500 once and +1000 once — the magnitude does not read deterministically off the class); **the weak form stands** on unconfounded n=1 (+500 connect) + n=4 (+100 bullet-victim kill). Session ledger **+1900** across 11 aimed taps (a: +800, b: +1100).

## 2. Harness lessons (measured, disclosed)

1. **A per-target-slot classifier is structurally blind in a multi-entity window** — the v1 analysis inherited the aimed-target framing and missed the true victims; the v2 global-frame per-slot matcher is the fix (same family as R46/R48's "the recording set must not be smaller than the truth").
2. **The spawner zone (x≈1277–1351) dominates the frontier windows**: cycling entities (0xaec8 spawn → walk → 0x515c → 0x4be4) feed fresh mortals into any bullet corridor — tap attribution without a corridor census is confounded by design.

## 3. Capsule + next_experiment

msx capsule +2 events (46 total, provenance-complete). `next_experiment` = **R50**: the CONTROLLED-CORRIDOR tap protocol — fire only when the census shows the aimed target as the ONLY mortal in the corridor (prefer dx > 100 beyond the spawner cluster), n ≥ 3 clean per class, a movement-only control, and the 0xae7c-class census to settle the +1000 residual. The INTERACTIVE M2 entry remains gated on a deep deaths=0 source (unchanged)."""

BODY_9 = """**R49 addendum (decision loop) — the round's rule: in a multi-entity window, a per-target classifier is blind by construction; match every event against ALL slots' state histories on a global frame line.**

Commit at HEAD · evidence `data/games/SLUS-01212/truck_evidence/r49/`; capsule +2 events (46).

1. **The v1 analysis asked "what did the AIMED slot do?" and got the wrong victims** — all four +100 payments co-land with OTHER slots' registrations. Rule: **an attribution matcher must enumerate every slot's transitions, not the intended target's** — the intended target is a hypothesis, not a measurement.
2. **Frame numbering that restarts per readout window is a silent aliasing trap** — "f_rel 2" meant different real frames across windows; v2 rebuilds one global frame line per pass before matching. Rule: **sequence-relative timestamps must be re-based before any cross-window matching.**
3. **A lag window is a hypothesis about mechanism** — [−2, +6] rows encodes "the payment cannot precede its cause by more than the recorder's granularity". The +1000 residual sits OUTSIDE it (2–4 rows after a zone registration) and is therefore recorded UNRESOLVED, not force-fitted. Rule: **a residual that escapes the mechanism window stays a residual.**
4. The churn discipline held: the zero-input control walks again show **zero** score jumps while carrying natural deaths — the baseline is subtracted before any payment claim."""

BODY_10 = """**R49 addendum (knowledge/provenance) — the payment model is refined to bullet-victim-locked; the residual is kept honest; the environment reproducibility chain extended.**

- **Model refinement by measurement, not interpretation**: R48's "death-registration-locked" becomes **PLAYER-BULLET-VICTIM-LOCKED** — 4/4 +100 payments co-land lag-0 with registrations of cycling zone entities in the bullet corridor, while 11 zone/wound registrations pay 0 and the control churn pays 0. The knowledge record now distinguishes *the aimed target* from *the bullet's victim* — they were conflated in every earlier round because the corridor happened to be clean.
- **The +500 surviving-connect payment REPLICATED** (n=2 across R48/R49) with the cleanest possible context (zero co-landing registrations, target survives and recovers). The **strong class-keyed magnitude claim is FALSIFIED** (identical context, +500 vs +1000) and the residual is recorded with named candidates — the knowledge base carries the open question, not a forced verdict.
- **The spawner zone (x≈1277–1351) is now a named hazard for attribution**: cycling entities (0xaec8 → 0x515c → 0x4be4) feed the corridor continuously; the R50 protocol gates every tap on a corridor census.
- Provenance discipline held: boot ledger 1/1 with no amendments; both capsule events VERIFIED with `{source, evidence}` non-empty; the suite is green (see the commit message); the buzzybee environment re-verified internet-first sha-verified (0 boots). No game bytes anywhere; `+0x8E` never in any oracle."""

BODY_6 = """**R49-B — the caused ≥ 2 pass REPLICATED at CAP_F 1800 (40% track): arm B (bot_policy8) 1701 / 0 hits / 7-of-7 / caused 2 — the FULL ORACLE true for the second consecutive round. bot_policy8 is not a one-cap fluke. Arm A = 1701/0/7/caused 1 = the 7th independent policy5 reproduction, exactly the R47 A1800 control line. Restore-only arms; boot 1 = core+rom load only (the r47b gs1 checkpoint survived on disk, READ-ONLY); the environment re-verified internet-first sha-verified (0 boots); 9 offline policy checks passed BEFORE the boot; 10.7 s wall. Evidence: `scratch/r49b/`. No new issues; no game bytes; no RAM writes.**

## Arms (1700 → 1800 f, protocol parity)

| arm | frames | score | hits | dodges | caused |
|---|---|---|---|---|---|
| A1800 (control) | 1800 | **1701** | **0** | 7/7 | 1 |
| **B1800 (bot_policy8)** | 1800 | **1701** | **0** | 7/7 | **2** |

## What this decides

- **The replication closes the fluke question**: the R48 first-full-oracle-pass reproduces at a SECOND cap with the same mechanism signature — the decisive pickup attributes **seek_dur 134** (≥ the 20f window) in flower mode (the R48 signature replicated) plus one opportunistic seek_dur 8. **Commitment remains the caused bottleneck, by name.**
- **The score = f − 99 prediction is EXACT** (1800 − 99 = 1701, both arms) — the mechanism now predicts across three caps (1401/1601(1701)/1701).
- **Honest notes**: the score axis is structurally tied (both arms 1701 — score is survival time); the caused gain is the ONLY delta, exactly as the capsule predicted. No margin floor needed (B took 0 hits; GM 8 stays safe — the R45-B evidence replicated a third time). Pass density: 7 passes at 1800f (the 8th did not arrive before cap), wasp density stable, the planner held.

## R50 (from the mechanism)

Scale to **CAP_F 2000** (the third extension): arm A = policy5 verbatim @2000 (the 8th reproduction check), arm B = bot_policy8 @2000 — hypothesis: hits 0 AND caused ≥ 2 (the third replication) with score ≥ 1901 predicted. The REAL RISK is late-game wasp density vs the guarantee planner (passes 7 → ~8–9); a B hit files the margin floor (the R45-B revert protocol). Offline checks before any boot (the R48/R49 precedent)."""


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
    sys.exit(main())
