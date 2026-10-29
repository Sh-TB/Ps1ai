#!/usr/bin/env python3
"""r42b_issue_report.py — post the R42-B cross-link comment to Issue #6
and VERIFY via single-GET (the list endpoint has the known R37 caching
quirk)."""
import json
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

PUSH_SHA = "a87750be459720c609b632a4b527be1f7c1133f1"

BODY = f"""## R42-B — BuzzyBee policy-v4 dominance A/B: **hypothesis CONTRADICTED** (2 hits both arms); R43 lever = contact-time trajectory guarantee

Track: the **40% side-train** (the 60/40 focus directive). Push [`a87750b`](https://github.com/Sh-TB/Ps1ai/commit/{PUSH_SHA}) · report **`docs/issue6_r42b_report.md`** · boot ledger `scratch/r42b/boots_used.json` (cap 1, **1 boot**, restores are not boots; one pre-boot abort filing corrected and disclosed).

1. **The lever executed**: the capsule's next_experiment — "policy-v4 (arc-checked below-side taps + fx>0 flower window) reaches dominance (0 hits/1500f)" — A/B **bot-v4 vs bot-A** on one gs1 checkpoint, 1500f/arm. Arm A = the recorded r35 bot-A recipe (`bot_policy2` engage=150/margin=16) **unchanged**; arm B = `bot_policy4` = `bot_policy3` + one targeted fix (the below-side corrective flap arc-checks the **predicted band bottom over the whole 14f tap window**, +4 clearance; engage=200).
2. **Result — CONTRADICTED**: A 2 hits (3/5 dodges, score 1401) · B 2 hits (4/6 dodges, score 1403). The primary oracle (v4 hits == 0) failed on both arms; v4 is not dominant, but not worse than A (+2 score, +1 dodge, +1 pickup) — the predictive arc-check did not hurt, it did not remove the residual hit mode.
3. **Hit forensics (the round's knowledge yield)**: all 4 hits (both arms) share one shape — the wasp **arrives at contact-x (ex ∈ [−36, 32]) while the bee is still inside the 56px band** [ey−13, ey+43] at low altitude (by 24–58) under a high wasp (ey 10–29); arm B's last hit had `side=above` with the bee already falling back in (bvy +1024 at contact). The side commit is right — **nothing guarantees the bee is OUT of the predicted band by ex=32**.
4. **Environment rebuild, sha-verified (disclosed)**: the sandbox cleanup had removed both the r35b savestate and the local disc. `BuzzyBee.ps-exe` re-fetched from upstream `NDR008/BuzzyBee@master` (internet-first rule) — sha256 `9b0bfc08…` **byte-identical** to the r23 reference; the disc rebuilt with the committed wrap script — sha256 `042b94bb…` **byte-identical** to the capsule-recorded artifact. The rebuilt gs1 checkpoint is not frame-identical to r35b's — cross-run comparisons to r35 are qualitative only (the A/B inside this run shares one checkpoint and is exact).
5. **Capsule updated** (`data/knowledge/buzzybee/capsule.json`, 5 events): +2 (rebuild provenance OBSERVED; the dominance CONTRADICTION) · `next_experiment` replaced — **R43**: a contact-time trajectory planner (simulate bee physics × wasp bounce to ex=32, choose the exit + tap schedule that keeps the bee out of the predicted band for the whole contact window, re-plan on vy-flip; bail = maximize band-center distance), plus the pickup-attribution window fix and a per-hit timing metric (B's hp 1790 vs A's 4758 at equal hit count shows timing, not count, drove the difference).
6. Legitimacy: legal inputs only (CROSS taps + one START); no RAM writes; savestates as labeled diagnostic anchors; no copyrighted bytes committed (the image stays local under gitignored `emu/`); upstream is MIT (flagged per the capsule)."""


def main():
    s, c = req(f"/repos/{REPO}/issues/6/comments", method="POST",
               payload={"body": BODY})
    assert s == 201, c
    cid = c["id"]
    s2, c2 = req(f"/repos/{REPO}/issues/comments/{cid}")  # single-GET
    ok = s2 == 200 and c2.get("body") == BODY
    print(f"issue #6: comment {cid} posted; single-GET "
          f"{'VERIFIED' if ok else 'MISMATCH'}")
    json.dump({"push_sha": PUSH_SHA, "comment_id": cid,
               "single_get_verified": bool(ok)},
              open("/home/z/my-project/ps1ai/scratch/r42b/"
                   "issue_comment_id.json", "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
