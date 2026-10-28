#!/usr/bin/env python3
"""r40_issue_report.py — post the R40 addendum comments to Issues #5,
#9 and #10 and VERIFY each via the list endpoint (never claim a post
without a read-back)."""
import json
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

PUSH_SHA = "5b441d96ddc4bda4649e0055b6708cf390d33d8e"

BODY_5 = f"""## R40 addendum — **THE CHOPPER KILLED IN-POLICY (x4 deterministic)**; the release blocker localized to the section-VM queue

Base `2e28581` (R39 close-out) → push [`5b441d9`](https://github.com/Sh-TB/Ps1ai/commit/{PUSH_SHA}) · suite **611 passed + 1 xfailed** (was 600+1) · boot ledger `scratch/r40/boots_used.json` (7 actual boots; the boot-7 filing-bug series disclosed in the ledger) · evidence bundle `data/games/SLUS-01212/truck_evidence/r40/r40_boot_reports.json` · internet-first: GameFAQs/IGN/TrueAchievements corroborate the human queue-priority strategy ("destroy the truck AND the helicopter", "focus the red leader first"); GitHub has no prior SLUS-01212 automation.

### 1. The census (boot 1) — WHO was stealing the mode

Ran the exact pre-R40 v2.2 behavior via the new `queue_priority=False` A/B flag. **Reproduction gate PASS**: engage 118 / aa_kill 76 / throws 13 / connects 1 / score 5701 = the R39 boot-6 pair exactly. The census answer: the mode thief at the pin is the **TRUCK WRECK complex, not soldiers** — the 0xA45C wreck-fire state alone took **67/81 engage-at-pin chunks** (+0x9E88/0xA44C; armor_hold held 37 more chunks on the wreck's stale row). The soldier family was **absent in all 81 chunks** (fam=0) — the R38 queue discipline never blocked this pin; the chopper was visible in **79/81** engage chunks while the policy shot a dead truck.

### 2. Boot-2 negative (recorded, not hidden): priority alone scatters the geometry

The queue-priority-only treatment (48 takeovers, aa_kill 76→84) connected **0/12** (vs the legacy 1/13) with throws scattered dx 5.6–54.7 — throwing at the chopper's CURRENT position while it patrols at ~1.5 px/f is the wrong gate. Score 3900 vs 5701 (the deterministic trajectory shifted). Recorded **CONTRADICTED** in-code and in the capsule.

### 3. The arrival-band model → v3.1 lead gate

The boot-1 c270 moving connect (release dx −51.7 with the chopper CLOSING at ~1.5 px/f) + the R39 frame capture give **dx_arr = dx + v·T**, lob time-to-altitude T ∈ [11.1, 27.8]f; shipped `AA_LEAD_T=20`. Parked hovers reduce to the v2.2 band exactly. Boot-3: 15 throws, the **first early connect (c99→c100, 300→200)** — the legacy never connected before c270 — 11/15 throws in-arrival-band, the velocity estimator tracking (−1.52..1.56 px/f).

### 4. **The kill** (boot 4, reproduced ×4)

The window-size hypothesis (each run is CKPT-independent, so 3 connects must land in ONE run; 300 chunks ≈ 15 throws ≈ 1 connect) → the **patient 1200-chunk run**: **3 verified hp_a4 connects** (c100 300→200, c387 200→100, vanish kill-connect at c421 — the verified −100 pattern) = **hp_a4 300→0**, kill score +1200 to **6901**, 0 deaths in the kill window. Boots 5/6/7 reproduced the kill **exactly** (resolved c421, score 6901) — the kill is a deterministic property of the shipped v3.1 policy.

### 5. The release is still BLOCKED — and the old hypothesis is dead

With the chopper dead the D7 section did **not** release: 745–780 post-kill chunks with nothing in the engage window (near=None 741/779), no 0xC. Boot-5's full-table watch: **no killable entity remains** (the chopper row persists as an a4=0 wreck shell; 0xA45C = the wreck fire state, a4=0). Boot-6 **falsified** the wave-zone stand: the walk LEFT hit a **hard map barrier at px 1021.8** (no entity there), 5.8 px short of the verified 992–1016 stand zone; the walker re-latched [0xB,0x1] within ~2 chunks. Boot-7 read the session-3 F6 queue RAM map: the node list is a **pointer** (0x800EB5F8 → 0x80084dcc, body unread); walker [0xB, 0x1] (the release flips flags 0x1→0x8 per F1); the progress word accumulates 0x80000000 → 0xFFFFFFFF (the release flips it to 0xFFF38B4A). **"The chopper is the last live queue entity" is CONTRADICTED** for the release.

### 6. Status labels

| item | status |
|---|---|
| chopper killed in-policy (hp_a4 300→0) | **VERIFIED** (×4 deterministic boots, hp_a4 + score agree) |
| queue-priority takeover (the R39 lever) | **IMPLEMENTED** (the census answered WHO; the wreck complex is the thief) |
| current-position throw geometry | **CONTRADICTED** (boot-2, 0/12) |
| arrival-band lead gate | **IMPLEMENTED, TESTED** (T ∈ [11.1,27.8]f from the moving connect) |
| chopper = last queue entity (release) | **CONTRADICTED** (the kill did not release; the blocker is in the section-VM queue) |
| D7 section release | **BLOCKED** — R41: read the node-list body at 0x80084dcc (candidates ranked in the capsule: the RIGHT-side soldier wave at 1285–1310, a non-entity node, the session-3 residual 0x4054 whose true HP word is still unknown) |

Legitimacy: legal inputs only; savestates as labeled diagnostic anchors; the boot-7 pre-boot abort filings (a stale cap-check bug, zero emulator boots consumed) corrected and disclosed in the ledger; `+0x8E` never in any oracle; no game bytes committed."""

BODY_9 = f"""## R40 cross-link — decision-loop changes (Issue #5 has the gameplay evidence)

Push [`5b441d9`](https://github.com/Sh-TB/Ps1ai/commit/{PUSH_SHA}) · suite 611+1xfail.

1. **Queue-priority takeover** (the R40 lever, census-driven): in the pin context the live chopper (the pending-queue blocker) now outranks engage AND armor_hold — the boot-1 census showed the truck-wreck complex (0xA45C et al.) stealing 67/81 engage-at-pin chunks while the chopper hovered in-window, with fam=0 throughout. The engage budget is frozen during the takeover (a budget walkthrough mid-campaign would burn clamp_clear frames in the D7 zone). Telemetry: `aa_priority_takeover` counts the chunks the blocker took away from would-be engage/armor.
2. **Arrival-band lead gate** (v3.1): throws gate on `dx_arr = dx + ch_v·AA_LEAD_T` (T=20f from the moving-connect derivation) — the boot-2 current-position treatment is recorded CONTRADICTED (0/12 scattered). The velocity estimator is chunk-sampled (15f) and capped at ±3 px/f; parked hovers reduce to the v2.2 band exactly.
3. **Committed-window survival fix**: a chopper-vanish chunk mid-commit no longer wipes the campaign (the old code resolved unconditionally and wasted the in-flight grenade); the lob tail finishes quietly and the resolve lands at the first post-commit frame.
4. **The A/B flag**: `CombatPolicy(queue_priority=False)` reproduces the exact pre-R40 v2.2 semantics (verified by tests) — behavior forks for honest baselining are explicit, never silent.
5. **The census contract**: every `decide()` now records `last_scan` (pin_ctx / chopper identity / fam count / near identity / armor slot / takeover booleans / ch_v) — a pure diagnostic that made the boot-1 census possible without perturbing behavior.
6. Capsule `next_experiment` replaced: R41 = the section-VM node-list body read at 0x80084dcc + the walker-flags watch (the release signatures: flags 0x1→0x8, progress → 0xFFF38B4A)."""

BODY_10 = f"""## R40 cross-link — knowledge/provenance changes (Issue #5 has the gameplay evidence)

Push [`5b441d9`](https://github.com/Sh-TB/Ps1ai/commit/{PUSH_SHA}) · capsule `data/knowledge/msx/capsule.json` validates (**21 events**, ok).

1. **+6 events appended, each with provenance**:
   - the boot-1 census (the wreck-complex mode thief; fam=0; chopper visible 79/81) — OBSERVED;
   - the boot-2 current-position scatter (0/12) — **CONTRADICTED**;
   - the arrival-band model (T ∈ [11.1,27.8]f, AA_LEAD_T=20; parked ≡ v2.2) — OBSERVED;
   - **the chopper killed in-policy ×4 deterministic (hp_a4 300→0, c421, score 6901)** — VERIFIED;
   - the chopper-last-queue-entity release hypothesis — **CONTRADICTED** (no killable entity remains; the blocker is in the section-VM queue: walker [0xB,0x1], progress → 0xFFFFFFFF, node list pointer 0x80084dcc);
   - the wave-zone stand falsified (the hard barrier at px 1021.8; the verified 992–1016 zone is unreachable from the right once the walker re-latches) — OBSERVED.
2. **`next_experiment` replaced** (R41): read the node-list body at 0x80084dcc (+ the runner id s16 @0x800EB588, the gate @0x800EB5C6), correlate pending nodes with the live entity table; candidates ranked: the RIGHT-side soldier wave (slots 13/16 @ 1285–1310, one flipping to 0x41FC), a non-entity node, the session-3 residual 0x4054 (true HP word still unknown — soft soldiers do not use +0xA4).
3. **Provenance discipline kept**: the kill is keyed on the verified identity (st 0xAA94/0xABDC, airborne, hp_a4); the +0x8E rule untouched; the boot-7 pre-boot abort filings disclosed in the ledger (cap amendments 7→8→9→10, zero emulator boots consumed by them).
4. Internet-first (the golden rule): GameFAQs/IGN/TrueAchievements corroborate the queue-priority strategy ("destroy the red leader first") — recorded as corroboration, not as new mechanical evidence; GitHub has no prior SLUS-01212 automation to reuse."""


def post(issue, body, tag):
    s, c = req(f"/repos/{REPO}/issues/{issue}/comments", method="POST",
               payload={"body": body})
    assert s == 201, (issue, c)
    cid = c["id"]
    # read-back verification
    s, lst = req(f"/repos/{REPO}/issues/{issue}/comments?per_page=5")
    assert s == 200
    ok = any(x["id"] == cid and x["body"] == body for x in lst)
    print(f"issue #{issue}: comment {cid} posted; read-back "
          f"{'VERIFIED' if ok else 'MISMATCH'} ({tag})")
    return cid


def main():
    ids = {}
    ids["5"] = post(5, BODY_5, "gameplay")
    ids["9"] = post(9, BODY_9, "decision-loop")
    ids["10"] = post(10, BODY_10, "knowledge")
    print(json.dumps(ids))
    with open("/home/z/my-project/ps1ai/scratch/r40/issue_comment_ids.json",
              "w") as f:
        json.dump({"push_sha": PUSH_SHA, "comments": ids}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
