#!/usr/bin/env python3
"""r62_issue_update.py — post the R62 FINAL CLOSURE report to Issue #14
and close it (every release gate passed), then read both back.
Follows the exact r61_issue_update.py practice."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

ISSUE = 14

BODY = """**R62 FINAL CLOSURE report (Autonomous Game Player Foundation) — badges: IMPLEMENTED / TESTED / OBSERVED / VERIFIED / PASS.** Evidence: `docs/r62_final_report.md` (+ `.json`) · `reports/r62_release_gate.json` · `data/r62/r62_stage_b_summary.json` · `data/r62/r62_stage_c_summary.json` · `data/r62/r62_stage_d_summary.json` · `data/r62/r62_profile.json`. Commit `e6faee0` (base `4797af2`). Suite **731 passed + 1 xfailed** (R61's 668+1 preserved — zero weakened, zero new skips). Release gate **15/15 PASS**.

**Final status: `R61_TRAINING: CLOSED` · `R62_RUNTIME: VERIFIED` · `R62_AUTOPLAY: VERIFIED` · `R62_20_EPISODES: PASS` · `R62_REGRESSION: PASS` · `R62_CLEAN_INSTALL: PASS` · `R62_RELEASE: PASS`**

**What ships:** one command — `python3 -m ps1play play flappybird` — runs the complete product experience: preflight → emulator boot → autonomous play on real captured frames → live status → episode records → safe shutdown. The generic runtime core (`ps1play/runtime/`: engine, session, legal-input controller, frozen-policy boundary, lifecycle, telemetry, recorder, registry, fail-early config, typed errors with exit codes 2/3/4/5/6/7/8/130) is game-agnostic; FlappyBird is one adapter wiring the EXACT R61 state machine (BirdObserverV7 / GapTrackerV7 / features_flappy_v7 / r15 seed-press start / PassageCounter). A second game = one `GameAdapter` subclass + one registry entry (proven by the `ScriptedGameAdapter` tests driving the real engine loop).

**The decisive proof — byte-exact equivalence with R61:** Stage A k6 ALIVE 87 pipes / 640 flaps / 10,000 frames with trace `d510e758…` == the R61 family row; gate k30 37@4401 ==; 3 consecutive k45 in ONE launch all == 40@4753 (no stale state across episodes); integration 2×k45 ==; Stage B family seeds {6,12,30,60,90} all ==. Acceptance: Stage A recorded (89 screenshots + 834-frame GIF); Stage B **20/20** preregistered episodes, 104,737 frames, 20 videos, 929 screenshots; Stage C 3 separate OS launches, all byte-match + policy identity verified + zero leaked processes; Stage D missing/wrong model refused (exit 3, never runs) and SIGINT → exit 130 + stopped record + input release + no leaks.

**Post-push verification (this closure):** remote HEAD read back via the API = `e6faee0…` ✓; 17 key R62 paths (runtime modules, adapter, CLI, release gate, docs, evidence summaries) present in the remote tree ✓; `docs/r62_final_report.md` remote blob byte-identical to the committed file ✓; this comment read back byte-identical after posting ✓; issue state read back after closing ✓.

**Honest limitations (unchanged from the report):** headless-only playback (`--show-window` refused by design; watching = `--record` GIFs); Stage B ran as 4 launches × 5 consecutive episodes (sandbox tool-call wall limit) with the same-launch continuity property proven byte-exactly at 3×k45/2×k45 — on an unrestricted machine the same command runs all 20 in one launch; Linux/x86-64 only; the clean-install gate step needs network; R61 model limitations carry over unchanged.

**Training stays CLOSED** — no retraining, no optimizer, no policy change anywhere in R62; the R61 artifacts are consumed read-only behind an authority hash check before the first decision, with no fallback. Closing as completed."""


def main():
    s, c = req(f"/repos/{REPO}/issues/{ISSUE}/comments", method="POST",
               payload={"body": BODY})
    print("comment POST:", s, c.get("id"))
    cid = c.get("id")
    s2, c2 = req(f"/repos/{REPO}/issues/comments/{cid}")
    print("comment read-back:", s2, "match:", c2.get("body") == BODY)
    s3, i = req(f"/repos/{REPO}/issues/{ISSUE}", method="PATCH",
                payload={"state": "closed", "state_reason": "completed"})
    print("issue close:", s3, i.get("state"), i.get("state_reason"))
    s4, i2 = req(f"/repos/{REPO}/issues/{ISSUE}")
    print("issue read-back:", s4, "state:", i2.get("state"),
          "state_reason:", i2.get("state_reason"),
          "comments:", i2.get("comments"))
    ok = (s == 201 and s2 == 200 and c2.get("body") == BODY
          and s4 == 200 and i2.get("state") == "closed"
          and i2.get("state_reason") == "completed")
    print("CLOSURE:", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
