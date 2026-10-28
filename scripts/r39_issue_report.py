#!/usr/bin/env python3
"""r39_issue_report.py — post the R39 addendum comments to Issues #5,
#9 and #10 and VERIFY each via the list endpoint (never claim a post
without a read-back)."""
import json
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

PUSH_SHA = "72ead8c16178c78e8a74d9159f0f8f39bc832203"

BODY_5 = f"""## R39 addendum — the anti-air connect rate root-caused (delivery fidelity); the v2.2 atomic+anchor rule connects in-policy; the R38 "restart" outcomes corrected to deaths

Base `1fa362b0` (R38 close-out) → push [`72ead8c`](https://github.com/Sh-TB/Ps1ai/commit/{PUSH_SHA}) · suite **600 passed + 1 xfailed** (was 594+1) · full report: `docs/issue10_r39_addendum.md` · boot ledger `scratch/r39/boots_used.json` (6 boots, every cap amendment disclosed pre-run) · evidence bundle `data/games/SLUS-01212/truck_evidence/r39/r39_boot_reports.json`.

### 1. The R38 baseline is real (reproduced first, unchanged policy)

The shipped policy from `r38_ckpt` reproduced R38 trialAA1 **exactly** (aa_kill 56 / aa_miss 10 / aa_connect 1 / aa_bail 1, end c227, score 4100, deterministic). No regression: the two-boot R37 menu detour never invalidated the D7 gameplay results.

### 2. The connect-rate cause — matched-anchor A/B (one boot)

From ONE in-run anchor (the first aa_kill chunk with the chopper inside 160 px), two diagnostic arms, matched 2400-frame budget:

| arm | delivery | throws | verified hp_a4 drops |
|---|---|---|---|
| DIAG-CHUNK | in-policy 15f-chunked J1 | 8 | **0** |
| DIAG-ATOMIC | session-3 `chopper_kill.py` J1 verbatim | 12 | **2** (300→200, 200→100) |

**The delivery mechanism is the first-order connect-rate factor** — not geometry alone. Frame-level capture (44 f, read-only): the grenade releases on the FIRST `UP+A+aim` frame; the hop apex is ~f20-24; the player drifts ~−35 px from bomb-blast knockback; the chopper patrols at |v|≈0.3-0.8 px/f and **hovers at x 1132-1155 near the clamp wall** (frozen at 1132.3; census: x=1155.1 held across 75 f).

### 3. The verified connect band (revised, release-frame evidence)

Every verified connect sits at cycle-start |dx| **13.7-29** (session-3 4×, boot-1 2×, boot-4 1×). The close hovers at |dx| 3-8.6 missed **4/4** (the UP-lob arcs over a too-close target) and throws beyond 30 never connected (0/5+ across arms). The shipped rule now throws only inside **[10, 35]**.

### 4. v2.2 (shipped) — the proven recipe + only the additions the evidence supports

Session-3 J1 at its proven 76 f cadence + **atomic delivery** (the lob aim locked at cycle start; the 19 f window finishes once the grenade is out) + the band gate + **anchor positioning** (walk back to px ≥ 1140 — the chopper hovers at the clamp) + the R38 cooldown rain-hop + queue discipline / bounded bail / quiet resolution unchanged. Design-iteration failures are recorded in-code (v2.0 96 f grid starvation → 2 throws/run; v2.1 grounded-guard self-block → 12 chunks of perfect dx −8.7..−27 geometry with zero throws; walk-toward-the-chopper dragged the player into the wave zone).

**Live result**: verified in-policy connects in two independent boots (boot-4 c143 and boot-6 c271: hp_a4 300→200 with the score event). Boot 6 ran the full 300-chunk campaign through 1 death + 1 continue screen (issue-4 `recover_v2` START tap, counted + disclosed) — 13 throws, 1 connect.

### 5. Harness correction — the R38 "restart" outcomes were deaths

Every `banner_expired_restart` recorded by the trial harnesses (R38 trialA1/A2 c268, trialAA1/AA2 c227, R39 BASE) was a **mid-chunk death** (`RESTART_SEEN px=0.0, sec [0,0]`; the chunk-end restart check fired before the death handler). Those trials measured **time-to-first-death**; no mission-timer wall at c227/c268 is evidenced. Fixed in R39: the outcome checks require `alive()`; deaths wait out the respawn and pass the game's own continue screen legally.

### 6. Where the chopper kill stands

2 of 3 connects landed in-policy. **Remaining causal gap (quantified)**: throw-opportunity share × connect rate — `aa_kill` held only 76/300 chunks while `engage` held 118 (the policy locks non-queue enemies while the chopper, the last queue blocker, waits). The capsule's `next_experiment` records the R40 lever: census who `engage` locks onto during the pin, rank queue entities above non-queue enemies (or verify whether the wall mortarman is itself a queue entity), then the existing atomic cadence should land the remaining 2 connects → queue clear → pin release → the proven mission-end chain.

### 7. Status labels

| item | status |
|---|---|
| R38 baseline | **REPRODUCED** (exact, deterministic) |
| delivery-fidelity cause + v2.2 rule | **IMPLEMENTED**, TESTED (15 unit tests, negative controls included) |
| in-policy atomic connects | **OBSERVED** (×2 boots, hp_a4 + score agree) |
| connect band / hover-anchor facts | **OBSERVED** (7 connects across 3 deliveries) |
| R38 "restart" reading | **CONTRADICTED** (corrected: they were deaths) |
| chopper killed in-policy | **PARTIAL** (2/3 connects) |
| D7 section release | **BLOCKED** (unchanged until the chopper dies) |

Legitimacy: legal inputs only; savestates used as labeled diagnostic anchors, never inside a claimed fresh-boot run; the continue screen is the game's own mechanic (counted, disclosed); `+0x8E` never in any oracle; no game bytes committed."""

BODY_9 = f"""## R39 cross-link — decision-loop changes (Issue #5 has the gameplay evidence)

Push [`72ead8c`](https://github.com/Sh-TB/Ps1ai/commit/{PUSH_SHA}) · suite 600+1xfail.

1. **Harness truthfulness (decision-loop input quality)**: the trial harness's chunk-end outcome check fired before the death handler, so every R38/R39 "banner_expired_restart" was actually a mid-chunk death (`RESTART_SEEN px=0.0`). The decision loop was consuming a fictional "mission-timer wall". Fixed: outcome checks require `alive()`; deaths wait out the respawn; the game's continue screen is passed with the established `recover_v2` START tap, **counted and disclosed separately from deaths**.
2. **Delivery atomicity as a policy principle**: the matched-anchor A/B (chunked 0/8 vs atomic 2/12) shows a proven frame-recipe must be delivered as one committed unit — aim locked at cycle start, the release window immune to chunk-boundary re-decision, soldier-appears flicker, and dodge overrides before the press frame. The committed-window guard is bounded (19 f) and regression-tested (aim-lock vs sign flips, committed window vs soldiers, dodge suppression before the press).
3. **Self-block lesson**: v2.1's grounded-start guard interacted with the hold plan's own rain-hop and blocked every re-lock (12 chunks of perfect geometry, zero throws). Guards must be checked against ALL the B sources they gate — recorded in-code and in the capsule.
4. **Per-throw telemetry** (Task 2): every throw now records dx/state/hp/grenade/plan/aim at the chunk boundary plus hp_a4 drops — the connect oracle stays `hp_a4` on the verified identity (`st 0xAA94/0xABDC`, airborne), never `+0x8E`.
5. Capsule `next_experiment` replaced: the blocker moved from "the delivery" to "the throw-opportunity share" (engage 118/300 chunks on non-queue enemies while the chopper is the queue blocker)."""

BODY_10 = f"""## R39 cross-link — knowledge/provenance changes (Issue #5 has the gameplay evidence)

Push [`72ead8c`](https://github.com/Sh-TB/Ps1ai/commit/{PUSH_SHA}) · capsule `data/knowledge/msx/capsule.json` validates (15 events, 2 artifacts hash-verified).

1. **+5 events appended, each with provenance** (evidence paths + boot source):
   - the matched-anchor delivery A/B (chunked 0/8 vs atomic 2/12) — OBSERVED;
   - the connect-band revision (connects 13.7-29; close hovers 3-8.6 missed 4/4; 0/5+ beyond 30) — OBSERVED;
   - the hover/anchor fact (the chopper hovers at x 1132-1155 near the clamp; st 0xAA94→0xABDC at the stop) — OBSERVED;
   - **the death-misreport correction — CONTRADICTED**: every R38/R39 `banner_expired_restart` was a mid-chunk death (px=0.0); the mission-timer-restart reading is superseded;
   - the in-policy atomic connects (boot-4 c143, boot-6 c271, hp_a4 300→200) — OBSERVED.
2. **`next_experiment` replaced**: the R39 evidence moved the blocker from the delivery mechanism to the throw-opportunity share (aa_kill 76/300 chunks vs engage 118; queue-priority question, mortarman-queue identity question). The R37-era guidance (menu-ladder cursor polling) and the R38-era guidance (positioning sub-rule) are superseded by the recorded boot evidence.
3. **Provenance discipline kept**: no claim promoted beyond its evidence; the +0x8E rule untouched (never HP, never in an oracle); the +0xA4 chopper HP stays keyed on the verified identity; artifact paths repo-relative with hash re-verification; machine-specific absolute paths avoided.
4. Internet-first (the golden rule): GameFAQs' walkthrough corroborates the truck+helicopter double-kill requirement — recorded as corroboration, not as new mechanical evidence."""

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
          f"{'VERIFIED' if ok else 'MISMATCH'}")
    return cid


def main():
    ids = {}
    ids["5"] = post(5, BODY_5, "gameplay")
    ids["9"] = post(9, BODY_9, "decision-loop")
    ids["10"] = post(10, BODY_10, "knowledge")
    print(json.dumps(ids))
    with open("/home/z/my-project/ps1ai/scratch/r39/issue_comment_ids.json",
              "w") as f:
        json.dump({"push_sha": PUSH_SHA, "comments": ids}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
