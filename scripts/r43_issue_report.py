#!/usr/bin/env python3
"""r43_issue_report.py — post the R43 addendum comments to Issues #5,
#9 and #10 and VERIFY each via the list endpoint (never claim a post
that isn't read back)."""
import json
import subprocess
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO                     # noqa: E402

PUSH_SHA = subprocess.run(
    ["git", "-C", "/home/z/my-project/ps1ai", "rev-parse", "HEAD"],
    capture_output=True, text=True).stdout.strip()

BODY_5 = f"""## R43 addendum — **the stale-stat gate root-caused (the r42t1 resolve gate is unsafe across mission restarts); the from-start village capability CONFIRMED for the current policy; the INTERACTIVE M2 entry NOT claimable from a post-restart posture (primary negative)**

Commit `{PUSH_SHA[:12]}` · evidence `truck_evidence/r43/` (ledger cap **7/7** + 4 boot reports + 3 jsonl) · suite 611 passed + 1 xfailed.

**Premise staleness disclosed first**: `r38_ckpt` AND `r42_postkill` are **absent** from `emu/ws/states/` (a filesystem rollback — only Oct-20 states survived; the same class as the documented mspsx_lic rollback). The round rebuilt from the surviving session-5 anchor `issue5_m1_start` (M1 start px~26). Ledger corrected filings disclosed (the R40 precedent): entries 1+2 = the r42t1 deep-posture guard (`px<700`) copied verbatim onto a shallow anchor — two real boots aborted at rebuild c3; entry 3 filed-but-died (external kill pre-boot); entry 4 killed mid-campaign.

**Boot 5 — the root cause (VERIFIED)**: the r42t1 resolve gate (`aa_resolved>=1`) is **stale-stat-UNSAFE across mission restarts**. After 2 deaths the mission restarted (px back to ~24) and the gate fired on the policy's surviving stat, saving a **RESTART posture** as the postkill: `RESOLVED at c167 with px=24.5, flags=75, score 4501`. r42t1 itself was safe only because its rebuild never died (`deaths=0`). **Also revised**: the boot-4 "village stall" was the silent aa campaign — the current (queue_priority) policy **passes the village from-start TWICE** (boot-5 rebuild c0–167 + the boot-5 latch replay score 4501→9403).

**Boots 6+7 — two-stage split** (the cross-process savestate restore is the R42-proven pattern):

| stage | result |
|---|---|
| stage 1 (boot 6) | the depth-conditional gate (`aa_resolved>=1 AND px>700`) saved `r43_postkill` at c172, **px=992, flags=0x4B** (the R41 RELEASE_SIGNATURE), score 4501 — but that posture is **post-restart + checkpoint-respawn**: the c164 chopper resolve was followed by a silent timer-expiry-style mission restart (px 1150→25, **no death event** — the shallow-anchor rebuild ran with the restart guard permanently off), then the checkpoint reload back to 992 |
| stage 2 (boot 7) | 900 latch chunks: **8 deaths** (all continue-rescued, counted + disclosed), score 4501→**13704**, px pushed to **1378** (PAST the 1285–1310 soldier wave — new territory) but held at the 1272 clamp; **mission_end NEVER latched** (0 latches); the R41 partial-F1 gap (flags partial, prog 0xffffffff unmoved) + re-armed section-VM nodes persist across restarts |

**The primary negative**: the INTERACTIVE M2 entry is **not claimable from a post-restart posture**; the clean (deaths=0) R42-style resolve posture remains the requirement — and its savestate was lost to the rollback.

**Reusable harness lessons** (each rooted in a measured failure): (1) policy stats survive deaths/restarts — **any stat-gated save needs a world-depth condition**; (2) the restart-leak guard must be **dynamic** (max_px>700 then px<700 = leak), not phase-open-state; (3) **frontier postures must be saved** (the px-1378 posture of boot 7 was lost to exit-without-save).

**R44 lever recorded**: the clean-resolve chain — dynamic restart guard + deaths=0 validity requirement + frontier saves (px>1200), then the latch (900 bound) + the session-6 accept ladder + the M2 input-delta discriminator (INTERACTIVE iff dR≥30 and dR−dL≥60 at the spawn fingerprint px 70–80/php 70–80/gren≥9/score≤200). Fallbacks: the deferred 0x4054 soft-soldier HP-word readout; the px-1272 clamp push. Capsule +4 events with provenance; `next_experiment` replaced; oracle unchanged (walker words + verified score gains + alive 0x0EE518; never +0x8E); no game bytes."""

BODY_9 = f"""## R43 addendum (decision loop) — **stat-gated saves need world-depth conditions; the restart guard must be dynamic**

Commit `{PUSH_SHA[:12]}` · evidence `truck_evidence/r43/`; capsule +4 events.

1. **The decision-loop defect named**: the policy's `aa_resolved` stat is *not world state* — it survives deaths and mission restarts, so a gate keyed on it alone saved a RESTART posture as the resolve postkill (boot 5: `RESOLVED c167 px=24.5`). The loop rule going forward: **every stat-gated save carries a world-depth condition** (px>700 for the D7/aa zone) or reads the section-VM words directly.
2. **The guard lesson**: the rebuild's restart-leak detector was armed from the *phase-open* posture — a shallow-anchor rebuild disabled it for the whole phase, and the mid-phase mission restart (px 1150→25, no death event — the timer-expiry path reads as alive-at-25) went undetected. The rule: **max_px>700 then px<700 = leak**, evaluated per chunk.
3. **Boot economics**: 7 ledger entries for 5 real boots, every filing disclosed (the corrected-filings precedent held under 3 distinct failure classes: guard misfire, external kill, mid-campaign kill). The two-stage split (rebuild | latch+accept) exists because one foreground window cannot hold the whole chain.
4. **R44 lever for this loop**: the clean-resolve chain with a deaths=0 validity requirement; abort honestly on the first death — a post-restart posture is now a MEASURED dead end for the end chain (900 latch chunks, 0 latches)."""

BODY_10 = f"""## R43 addendum (knowledge/provenance) — **the end-chain requirement sharpened: clean resolve posture or nothing; village capability recorded**

Commit `{PUSH_SHA[:12]}` · evidence `truck_evidence/r43/`; capsule +4 events.

1. **New capability fact (VERIFIED)**: the current (queue_priority) policy passes the Mission-1 village armored-truck section **from a mission-start anchor** — twice in one sandbox (boot-5 rebuild + boot-5 latch replay). The R4x-era rebuilds always started deep (r38_ckpt); the from-start path is now proven for the shipped policy.
2. **The end-chain map extended**: a post-restart + checkpoint-respawn posture (px 992, flags 0x4B, prog unmoved) does **not** reach the end chain even with 900 policy chunks, +9203 score and 8 continue-rescued deaths — the section-VM nodes **re-arm across mission restarts**, and the R41 partial-F1 signature (flags partial, prog 0xffffffff) persisted at the save AND at the final. The clean-resolve posture requirement is now a measured rule, not an assumption.
3. **New territory reached**: px **1378** (score 13704) — past the 1285–1310 soldier wave, held at the 1272 clamp by the policy's clamp_clear loop. The posture was not saved (the frontier-save lesson is recorded in the capsule).
4. **Shipped-validator defect fixed in passing**: the capsule carried status `CONFIRMED` (events[26], the R42 update) outside the allowed vocabulary — normalized to `VERIFIED` (×2), suite green again (611 + 1 xfail).
5. **Oracle discipline kept**: walker words + verified score gains + alive 0x0EE518; `+0x8E` never in any oracle; no game bytes committed; boot ledger cap 7/7 with every corrected filing disclosed.
6. Internet-first (the golden rule): the round opened with searches (PS1 deterministic input replay frameworks, Mednafen/Beetle determinism, MSX speedrun routes, retro emulator AI-agent E2E testing) — no prior SLUS-01212 automation found; the stale-stat-gate and dynamic-restart-guard lessons are new recorded knowledge."""


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
    ids["5"] = post(5, BODY_5, "gameplay")
    ids["9"] = post(9, BODY_9, "decision-loop")
    ids["10"] = post(10, BODY_10, "knowledge")
    print(json.dumps(ids))
    with open("/home/z/my-project/ps1ai/scratch/r43/"
              "issue_comment_ids.json", "w") as f:
        json.dump({"push_sha": PUSH_SHA, "comments": ids}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
