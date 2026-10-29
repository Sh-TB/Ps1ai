#!/usr/bin/env python3
"""r42_issue_report.py — post the R42 addendum comments to Issues #5,
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

BODY_5 = f"""## R42 addendum — **the R41 restart leak was a HARNESS INPUT LEAK (hypothesis CONFIRMED); the D7 blocker is CLOSED as bypassed-by-mission-end; the post-tally chain is attract/demo-labeled, not an interactive M2 entry**

Commit `{PUSH_SHA[:12]}` · evidence `truck_evidence/r42/` (2 boot reports + 2 jsonl + ledger, cap **2/2**) · suite 611 passed + 1 xfail.

**Premise staleness disclosed first**: the R42 capsule said "restore the post-kill savestate from boot-4" — **`r41_postkill` does not exist** (the boot-4 report records `saved_postkill=false`; `emu/ws/states/` holds no such file). Boot 1 therefore rebuilt the posture from `r38_ckpt` and saved `r42_postkill` at the gate. Recorded in the ledger and the capsule.

**Boot 1 — negative + gate lesson**: the `aa_resolved` gate fired at c441 (px 1357, score 6101) and `r42_postkill` saved; then **24000 frames of HARD zero input produced NO banner and NO restart** — the end sequence is *not an idle timer*, and the attract/demo control took the world over (px moved 1357 → 540 → 993, score climbed 6101 → 13610 **with zero inputs**). The resolved posture the method means is the **mission_end latch posture**, not the aa-resolve posture.

**Boot 2 — the core result**: from `r42_postkill` the shipped policy latched `mission_end` at latch-c24 (px 1562, score 7701), then the harness ran the **HARD hold** (`p.core.run(n, set())` only — the policy is never consulted again):

| hold phase | reading |
|---|---|
| hold c11 | prebanner signature **(state 0, flags 0x8)** — the session-4 pre-banner step |
| hold c11–c360 | tally teardown (px 0.0 + php 0, streak 349) |
| hold c360 | fresh world px 120.1, **score reset 0** |
| hold c472 | teardown begins at **score 7800** — the recorded session-6/7 M1→M2 loading score |
| hold c733 | **M2-spawn-shaped world: px 74.0, php 74, sec (11,1)** (recorded spawn: px 74.6/76.4, php 74/76) |
| hold c845 | teardown at **score 10930** — the session-7 train-ride fade score |
| hold c1488 | further demo scenes (px 87.8, score 2100 …) |

The **2-chunk-persistent restart classifier never fired in 24000 frames** — no restart to the M1 spawn (px ~37, sec 0xB, score kept), the exact R41 leak shape, occurred under a hard zero-input hold.

**Claims, with honest labels**:
1. **CONFIRMED**: the R41 restart leak was a **harness input leak**, not a game-state blocker — with the leak channel removed, the mission-end flow completes with zero input. The **D7 blocker is CLOSED as bypassed-by-mission-end**.
2. **OBSERVED (label kept)**: the banner predicate (0xC × 4 persist) **never fired under zero input** — (0,8) flows straight into the tally teardown; the session-5/6 banner (0xC at px 26.4) is the *input-alive variant* of the same end sequence.
3. **ATTRACT-LABELED, NOT INTERACTIVE**: the post-tally chain matches the attract/demo pipeline (milestone scores 7800/10930, ~28 s scene windows). The M2-load signature is **not** a verified interactive M2 entry — that remains the session-6 ONE START-tap accept path.

**`next_experiment` replaced (R43)**: (a) the **ONE START-tap accept** at the mission_end latch from `r42_postkill` (1 boot) — the demo-vs-live discriminator is the **input-driven px delta**, not the score; success = the runner's own tally (7701 → 7800) continuing into runner-controlled M2 gameplay = `INTERACTIVE_M2_ENTRY`; (b) the deferred **0x4054 soft-soldier HP word** readout (aimed fire at slots 13/16, read +0x8E/+0xA4/+0x9E per tap against verified score gains).

Internet-first (the golden rule): DuckStation/PCSX-R deterministic-playback docs and Metal Slug attract-mode prior art reviewed — **no prior SLUS-01212 banner-hold automation exists to reuse**; the R41 addendum's divergence-point methodology stands."""

BODY_9 = f"""## R42 addendum (decision loop) — **the harness must hard-hold: the policy's own mission_end hold is not leak-proof**

Commit `{PUSH_SHA[:12]}` · full gameplay evidence in #5 (gameplay tag).

1. **The R41 leak mechanism named**: in the R41 boot-4 run the policy latched `mission_end` (prebanner) and emitted only **2 of 4** hold chunks (`mission_end_hold=2`) before the restart — the policy's unlatch/resume channel (the `mission_end_restart_resume` rule) is a live input source during the banner window. R42's **hard hold** (the harness emits `p.core.run(n, set())` and never consults the policy after the latch) ran **24000 frames with zero restart** — the decision-loop lesson is: **once the end sequence latches, the policy layer is bypassed entirely, not trusted to hold**.
2. **The gate lesson recorded**: the R42 boot-1 resolve gate (`aa_resolved`) was **premature** — the end sequence never triggers from that posture under idle (24000f, no banner, no restart; the attract/demo control took over instead). The correct gate is the **mission_end latch** (prebanner (0,8)+d7_zone or the 0xC ×2 confirm) — the same latch the policy already computes.
3. **R43 lever for this loop**: at the mission_end latch, ONE disclosed START tap (the session-6 recipe) then the endzone walk — the discriminator for `INTERACTIVE_M2_ENTRY` is the **input-driven px delta**, and the policy's own stats remain the provenance of any claimed kill/tally.

Capsule +3 events with provenance; `next_experiment` replaced; no game bytes; `+0x8E` never in any oracle."""

BODY_10 = f"""## R42 addendum (knowledge/provenance) — **attract/demo mode identified live; the end-sequence map updated**

Commit `{PUSH_SHA[:12]}` · evidence `truck_evidence/r42/`; capsule +3 events.

1. **New memory-behaviour fact**: under a hard zero-input hold the game **takes control itself** (attract/demo): from the aa-resolve posture the player world moved (px 1357 → 540 → 993) and the score climbed (6101 → 13610) with **zero inputs** — any future idle-window experiment must classify the demo takeover before trusting its readings (the demo replays M1/M2 scenes with milestone scores matching the recorded transitions: 7800 loading, 10930 train-fade).
2. **The end-sequence map** (zero-input variant): mission_end latch (px ~1562, score 7701) → prebanner **(0,8)** ~165f → tally teardown ~5235f (px 0.0 + php 0) → score-reset world (px 120) → **7800 loading teardown** → M2-spawn-shaped world (px 74.0/php 74/sec (11,1)) → **10930 teardown** → demo cycle. The section-VM F1 release signature stays absent throughout (prog unmoved) — consistent with R41's decoupling finding.
3. **Premise staleness recorded**: `r41_postkill` absent (boot-4 `saved_postkill=false`) — the capsule's restore premise was stale; boot 1 rebuilt `r42_postkill` from `r38_ckpt` with the deviation disclosed in the ledger. Boot cap 2/2 used, disclosed pre-run.
4. **Oracle discipline kept**: the banner predicate + the walker words + verified score gains only; `+0x8E` never in any oracle; the attract-vs-interactive labels carried into every event.
5. Internet-first (the golden rule): PS1 emulator deterministic-playback documentation (DuckStation/PCSX-R families) and Metal Slug attract-mode references reviewed — no prior SLUS-01212 automation to reuse; the demo-takeover classification is new recorded knowledge."""


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
    with open("/home/z/my-project/ps1ai/scratch/r42/"
              "issue_comment_ids.json", "w") as f:
        json.dump({"push_sha": PUSH_SHA, "comments": ids}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
