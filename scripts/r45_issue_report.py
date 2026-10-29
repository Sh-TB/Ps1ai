#!/usr/bin/env python3
"""r45_issue_report.py — R45 round report (the 60% track to Issues
#5/#9/#10, the 40%-track round to Issue #6).  Same post+read-back-
verify pattern as r44_issue_report.py.  No new issues opened (the
standing constraint)."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

PUSH_SHA = os.popen(
    "git -C /home/z/my-project/ps1ai rev-parse HEAD").read().strip()

BODY_5 = """**R45 — the 0x4054 soft-soldier HP-word readout (60% track, Issues #5/#9/#10). Sandbox rollback disclosed and survived per the capsule contingency; boot cap 2/2, every filing + refund disclosed. Evidence: `data/games/SLUS-01212/truck_evidence/r45/`. No new issues; no game bytes; `+0x8E` never in any oracle.**

## 1. The sandbox rollback + the disclosed rebuild

The R43/R44 workspace states (`r43_postkill`, `r44_postkill`, `r44_frontier_a/b`) are **LOST** to the sandbox filesystem rollback; the session-5 anchor `issue5_m1_start` (Oct 20) **survived** on disk. The R45 capsule budget anticipated exactly this contingency ("a rebuild boot only if a frontier is lost, disclosed"). Two background launches died silently inside `boot_to_demo` (ledger + `RUN_START` only — no boot completed) and were **refunded per the corrected-filings precedent**; the two-stage **foreground** protocol then ran clean inside cap 2/2 (48 s + 29 s wall):

- **stage 1 (the tainted frontier rebuild)**: restore `issue5_m1_start` → the shipped policy with continue-rescues (deaths allowed, counted, disclosed) → **eager** rolling frontier saves past px 1200 → `r45_frontier_b` (**px 1254.8, census 13 live in the x 1150–1450 window**) + `r45_frontier_a`; 6 deaths / 6 continue-rescues — **TAINTED lineage, never a clean claim**.
- **stage 2 (the readout, restore-only from `r45_frontier_a` px 1224.9 score 6702)**: 1 zero-input control tap + 14 aimed taps.

## 2. The readout — BOUNDED NEGATIVE on the 3 candidates + a constructive finding

Per-tap u16 deltas at the candidates (+0x8E/+0xA4/+0x9E) plus the **disclosed exploratory wide net** (0x88..0xA8 step 2), against verified score gains:

| candidate | verdict |
|---|---|
| +0xA4 | **0 throughout** for the soldier — armored-only (the truck 300→0 semantics hold); REFUTED for the soft class |
| +0x9E | **silent** across all 15 taps; REFUTED |
| +0x8E | screen-x again (drifts with movement; the 0x8C/0x94 shadow words move in sync); the known mislock re-confirmed |

**Constructive**: the slot-20 soldier (st `0x4054`, dx +60.8, ground) died on the **2nd aimed tap** with the **flat +100 at the death tap** and **no decrementing word anywhere in 0x88..0xA8** — the soft soldier behaves as the **ONE-HIT kill class** (n = 1 soldier; cap 2/2 spent). Score events: **+500** (tap 1 — attribution unresolved, OBSERVED: a projectile gone + an off-census spawn gone), **+100 × 3** (soldier-class kills). Protocol note for R46: after the ground entities died, the tap fallback engaged AIRBORNE projectiles (dscore 0 — shells are not damageable by gunfire); R46 filters `kind=='enemy'`.

## 3. Capsule + next_experiment

msx capsule +3 events (38 total): the rollback+rebuild (VERIFIED), the tainted frontier rebuild (OBSERVED), the readout (VERIFIED). `next_experiment` = **R46**: replicate the one-hit finding across ≥ 3 ground-only kills from the **SAVED** r45 frontiers (restore-only, cap 1 — the frontiers survive on disk); any multi-tap kill or any decrementing word REFUTES the one-hit reading and reopens the HP-word hunt. The **INTERACTIVE M2 entry remains gated on a deep deaths=0 source** — no such source exists after the `r38_ckpt` loss; producing one is a later round's problem, not a fallback lever."""

BODY_9 = """**R45 addendum (decision loop) — the two-stage foreground protocol is the crash-resilient form of the savestate round; the readout protocol earned a target-filter rule.**

Commit at HEAD · evidence `data/games/SLUS-01212/truck_evidence/r45/`; capsule +3 events.

1. **The background-launch failure mode measured**: two `setsid nohup` launches died **silently inside `boot_to_demo`** (no traceback, no jsonl event beyond `RUN_START`) while a foreground boot probe succeeded — the round lost ~10 min to silent background death. The fix is procedural, not technical: **the two-stage foreground protocol** (stage-1 rebuild / stage-2 readout as separate invocations, each inside one wall-clock budget, the savestate files as the hand-off medium) ran clean at 48 s + 29 s. The boot ledger's ghost entries were refunded via same-entry `outcome_corrected` amendments (the corrected-filings precedent, third round running).
2. **The eager-frontier rule worked as designed**: rolling saves every ≥ 25 px past px 1200 captured **combat-live** postures (census 13 at `r45_frontier_b` px 1254.8) — the R44 boot-7 loss class (exit-without-save) is structurally closed: the rebuild saves *during* the fight, not at a quiet moment.
3. **The readout's decision-loop lesson**: the tap-target selector (nearest, soft-st-preferred) fell back to **airborne projectiles** once the ground entities died — 8 of 14 taps produced dscore 0 noise against undamageable shells. The rule going forward: **aimed probes carry a kind filter** (`kind=='enemy'`, ground contact) — a probe's target set is part of the probe's validity, like the sensor-order rule for chunk ends.
4. The one-hit finding (flat +100 at the 2nd-tap death, no decrementing word in the disclosed wide net, n=1) now gates the next round: R46 replicates across ≥ 3 ground-only kills BEFORE any HP-word hunt resumes."""

BODY_10 = """**R45 addendum (knowledge/provenance) — the capsule contingency executed verbatim; the soldier class bounded; the frontiers survive as reusable evidence.**

Commit at HEAD · evidence `data/games/SLUS-01212/truck_evidence/r45/`; capsule +3 events (38 total).

1. **The capsule contingency executed as written**: the budget line "a rebuild boot only if a frontier is lost, disclosed" anticipated the sandbox rollback exactly — the loss was disclosed pre-run in the ledger note, the rebuild lineage was labeled **TAINTED** (6 deaths / 6 continue-rescues counted), and the INTERACTIVE M2 gate is explicitly untouched. The knowledge trail: loss → disclosure → contingency → tainted lineage label, with zero silent substitutions.
2. **The last unknown word is now a bounded negative**: +0xA4 = 0 for the soldier (armored-only — the truck semantics hold), +0x9E silent (15 taps), +0x8E = screen-x re-confirmed (shadows in sync). The soft soldier reads as the **one-hit kill class**: flat +100 at the death tap, no damage-tracking word in the disclosed 0x88..0xA8 net (n = 1; the cap is spent — replication is R46's job, restore-only cap 1 from the SAVED frontiers).
3. **Provenance discipline held under rollback**: the refunded ghost ledger entries carry same-entry `outcome_corrected` amendments; the frontier states are named `r45_frontier_*` (never re-using the lost `r44_frontier_*` names — no state overwrites a lost predecessor's identity); the jsonl `RUN_START` carries the full rollback disclosure.
4. **Reusable evidence**: `r45_frontier_a/b` survive on disk with their census recorded in the committed jsonl (px 1224.9/1254.8, census 9/13) — R46 runs restore-only against them (cap 1)."""

BODY_6 = """**R45-B (buzzybee, the 40% track) — the tiered margin preserves dominance at zero cost, and 1401 is a STRUCTURE: honest NEGATIVE, the third consecutive score tie.** Environment rebuilt internet-first sha-verified (disclosed, 0 boots: upstream EXE `9b0bfc08…` byte-identical, committed wrap-script output `042b94bb…` byte-identical); boot 1 (cap 1/1) rebuilt the gs1 checkpoint in-process (the r42b precedent). Arms (1500 f each, restore-only, shared checkpoint): arm A = `bot_policy5` verbatim; arm B = `bot_policy7` (TIERED margin: GM 8 pre-danger t_enter>20 / GM 12 in-window; the policy6 flower selection + bail unchanged). Result: **B 0 hits / 6-of-6 / score 1401 TIE / caused 1 (<2)** — the tier genuinely engaged (**GM8 held 453 dodge frames with ZERO hits** = the looser tier is safe at this checkpoint; the margin-floor revert never fired) but the outcomes CONVERGED with arm A (score 1401, hp 5666, 6 passes, flaps 82/81). **Constructive: the 1401 line is invariant across FOUR policy families** (A recipe, policy5, policy6, policy7) = the checkpoint's fixed reward structure (6 wasp passes per 1500 f), NOT a policy deficit; flowers drive HEALTH (+997), not score. Breaking ≥ 1550 requires leaving the dodge axis: capsule `next_experiment` = **R46** — per-frame score telemetry (0x8005883C readable per frame) to localize the score source, then the lever (a longer horizon or the source directly). Full report: `docs/issue6_r45b_report.md`."""


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
    ids["5"] = post(5, BODY_5, "r45-gameplay")
    ids["9"] = post(9, BODY_9, "r45-decision-loop")
    ids["10"] = post(10, BODY_10, "r45-knowledge")
    ids["6"] = post(6, BODY_6, "r45b-buzzybee")
    print(json.dumps(ids))
    os.makedirs("/home/z/my-project/ps1ai/scratch/r45", exist_ok=True)
    with open("/home/z/my-project/ps1ai/scratch/r45/"
              "issue_comment_ids.json", "w") as f:
        json.dump({"push_sha": PUSH_SHA, "comments": ids}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
