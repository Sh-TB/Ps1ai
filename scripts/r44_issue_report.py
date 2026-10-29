#!/usr/bin/env python3
"""r44_issue_report.py — R44 round report (the 60% track to Issue #5,
a short 40%-track pointer to Issue #6).  Same post+read-back-verify
pattern as r43_issue_report.py.  No new issues opened (the standing
constraint)."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

PUSH_SHA = os.popen(
    "git -C /home/z/my-project/ps1ai rev-parse HEAD").read().strip()

BODY_5 = """**R44 — the clean-resolve chain round (60% track, Issues #5/#9/#10). Boot ledger cap 4/4, every filing + outcome correction disclosed. Evidence: `data/games/SLUS-01212/truck_evidence/r44/` (4 boot jsonl + reports + `boots_used.json`). Suite 611 passed + 1 xfailed. No new issues; no game bytes; `+0x8E` never in any oracle.**

## 1. Headline: the stage-1 premise is FALSIFIED — by deterministic reproduction

The R44 capsule hypothesis: *the end-of-mission chain fires only from a clean (deaths=0, no-restart) resolve posture — rebuild it from `issue5_m1_start` with the dynamic restart guard.* Boots 1–2 ran that rebuild twice. Both died at the **same chunk c86** (armor zone, px 951.1, php 79 at c80, score 2700, mid-engage) — and the world traces are **bit-identical** to **R43 boot-5** through the divergence point:

| c | 0 | 20 | 40 | 60 | 80 | death |
|---|---|---|---|---|---|---|
| px | 279.0 | 487.9 | 770.2 | 1044.7 | 951.1 | 0 (php 0) |
| score | 0 | 900 | 1200 | 2100 | 2700 | 2700 |

Three independent boots across two rounds (R43 boot-5 c87 chunk-start sensor; R44 boots 1+2 c86 chunk-end sensor) = the c86/87 death is a **deterministic property of the shipped policy from the shallow anchor**, not variance. Consequences:

- The **deaths=0 rebuild is unreachable from `issue5_m1_start`** under the shipped policy. The only deaths=0 rebuild on record (r42t1) rebuilt from the **lost deep anchor `r38_ckpt`** and never walked this zone — which also sharpens the R43 reading: boot-5's "rebuild" carried deaths ≥ 2 (c87, c157), so its gate save was tainted for two independent reasons.
- The R43 negative therefore **generalizes**: until a deep deaths=0 posture source exists, the INTERACTIVE M2 entry stays unclaimable. Producing such a source is a later round's problem, not a fallback lever.

## 2. Harness lessons (all measured, all fixed in-round, all disclosed)

1. **Sensor order at BOTH chunk ends**: the alive/death check must precede the restart-leak check. Boot 1 (c86) and boot 3 (c21) were the same defect mirrored — a mid-chunk death / a dead transition world mislabeled `restart_leak`. Ledger entries 1–3 carry same-entry outcome corrections (the corrected-filings precedent extended).
2. **The WRAP signature named**: px 65494–65535 is the scene-transition world — seen ALIVE at R43 boot-5 c160 (php 242) and at R44 boot-3 c20-end. It must never feed `max_px`, the leak guard, or a frontier save. The sane-world clamp (0 ≤ px < 5000) now gates all three; the boot-3 frontier save that fired on the wrapped px (65494.4) was **invalidated and preserved** (`r44_wrap_junk_boot3`, forensics).
3. The dynamic restart guard + the depth-conditional gate + frontier saves all held otherwise: no false positives after the fixes.

## 3. Fallback (b) executed (boots 3–4 reallocated, disclosed; cap 4/4)

Boot 4 = the full 900-chunk latch attempt from the on-disk **tainted** `r43_postkill` (post-restart checkpoint-respawn lineage, never a clean claim): 8 continue-rescued deaths (counted + disclosed), score **4501 → 13704** (the R43 boot-7 deterministic reproduction, second independent run), the policy held at the **1272 clamp** (`clamp_clear`), **mission_end never latched** (0 latches) — the R43 negative re-confirmed.

**The boot-7 frontier loss is REPAIRED**: frontier postures saved with the sane-world clamp — `r44_frontier_b` (**px 1275.2**) and `r44_frontier_a` (**px 1341.2**, past the 1285–1310 wave).

## 4. Capsule + next_experiment

msx capsule +3 events (35 total): the falsification (VERIFIED), the harness lessons, the fallback-b push (OBSERVED). `next_experiment` = **R45 = fallback (a)**: the deferred **0x4054 soft-soldier HP-word readout** from the saved frontier postures (restore-only, cap 2; per-tap word deltas vs verified score gains; oracle unchanged).

## 5. Internet-first (the golden rule)

The round opened with searches (PS1 emulator deterministic real-play E2E, DuckStation save-state/restore determinism, MSX automation prior art). Recorded relevant prior: save-state restores snapshot the memory card state too and restore points are not guaranteed deterministic across harness contexts — consistent with our cross-process restore pattern + bit-identical-trace verification discipline. No prior SLUS-01212 automation found (re-confirmed).

## 6. The 40% track (60/40 discipline)

The buzzybee R44 score-superiority round also ran this session (restore-only, 1 disclosed load): honest **NEGATIVE** — score tie 1401, caused 1 (< 2), dominance stands (0 hits / 6-of-6), bail geometry named (partial-column positionable, 0 full-column sweeps). Report: `docs/issue6_r44b_report.md`; see the Issue #6 comment."""

BODY_6 = """**R44 (buzzybee, the 40% track) — score superiority: honest NEGATIVE.** Restore-only (the preserved R43-B gs1 checkpoint; 1 disclosed core+rom load, cap 1/1), 1500f/arm, same runner. Arm A (bot-A recipe verbatim) 2 hits / 3-of-5 / score 1401 / caused 0; arm B (`bot_policy6` = the guarantee planner with the flower seek widened INTO the dodge windows: among GUARANTEED candidates pick the hold-y nearest the reachable flower; the filter untouched) 0 hits / 6-of-6 / score **1401 TIE** (≥1500 missed) / caused **1** (< 2). `SCORE_SUPERIOR: false`; **dominance stands**. Secondary: bail geometry NAMED — 0/100 full-column sweeps; the shape is **partial-column, positionable** (a planner-reachability limit, not unavoidable geometry). Reading: the tie is a flower-SUPPLY limit — the candidate that would reach the flower is exactly the one the guarantee filter rejects; widening the seek inside the guarantee cannot add supply. Capsule +1 event; next_experiment = R45: seek-timing pre-position during the dodge tail + tiered margin (GM 8 pre-danger / 12 in-window; any hit ⇒ revert to 12 and file the margin floor). Full report: `docs/issue6_r44b_report.md`."""


def post(issue, body, tag):
    s, c = req(f"/repos/{REPO}/issues/{issue}/comments", method="POST",
               payload={"body": body})
    assert s == 201, (issue, c)
    cid = c["id"]
    s, lst = req(f"/repos/{REPO}/issues/{issue}/comments?per_page=5")
    assert s == 200
    ok = any(x["id"] == cid and x["body"] == body for x in lst)
    print(f"issue #{issue}: comment {cid} posted; read-back "
          f"{'VERIFIED' if ok else 'MISMATCH'} ({tag})")
    return cid


def main():
    ids = {}
    ids["5"] = post(5, BODY_5, "r44-gameplay")
    ids["6"] = post(6, BODY_6, "r44-buzzybee")
    print(json.dumps(ids))
    with open("/home/z/my-project/ps1ai/scratch/r44/"
              "issue_comment_ids.json", "w") as f:
        json.dump({"push_sha": PUSH_SHA, "comments": ids}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
