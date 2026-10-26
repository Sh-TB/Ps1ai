#!/usr/bin/env python3
"""post_issue6_round6.py — Issue #6 round-6 report + Issue #5 session-9 note."""
import json
import sys

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, "/home/z/my-project/scripts")  # gh_api helper lives in the outer lab scripts dir
from gh_api import req, REPO  # noqa: E402

BODY6 = """**Round 6 (50/50 + tools) — Nortis line-clear causality CLOSED, MSX M2 terminus characterized, reusable playloop tool landed.** Commit `5ee659b`, suite **482 passed + 1 xfailed**.

## Nortis — the round-5 honest gap is closed: LINE CLEARS + complete played game x2 cycles

The campaign was calibration-heavy by design; six probes (`nortis_calib{,2..6}.py`, dead ends preserved) pinned the **release binary's** true memory layout (which differs from today's master):

- `GameState` @ `0x15FB0` (block/rot/clearedLines/points/positionX/positionY/playState) — verified behaviorally (x ±1 on taps, y ticks with falls)
- **settled field** @ `0x1615C`: 26×10 u32s, stride 40, `row = positionY − 2`; a second identical copy @ `+0x410`
- a **render array** @ `0x15FCC` that contains the active piece — *not* the collision field (three probes burned before the changes-only-at-commit behavioral isolate)
- **the game starts with terrain**: title-screen leftover pieces (S+T, field rows 10-13, cols 4-6) that `game_actionRestart` never clears in the binary — every round-5 PNG-policy iteration was silently stacking on this
- input: 1 cell per press-edge (2f press), ROTATE=CIRCLE→libretro **A**, HARD DROP=CROSS→libretro **B**, one action/frame, gravity 20 f/row (source flipped-args bug: level pinned to 20)

`nortis_lineclear.py` (RAM-truth greedy, **clear-first** scoring, per-piece plan verification `landed == planned`) — **run lc10: 62 pieces, 50/62 plan-perfect, 5 LINE CLEARS**:
- cycle 1: `clearedLines` 0→1→2→3 (clears at pieces 3/10/17) → natural game over (31 pieces)
- START restart (lines reset to 0) → cycle 2: 0→1→2 (clears at 36/56) → natural game over

`points` stays 0 — the source never increments it (honest note). Verdict: **GAMEPLAY_CONFIRMED + CAUSAL (lines counter)**. Evidence: `scratch/issue6_round6_nortis/` (per-piece JSONLs, CLEAR PNGs, FIELD_DUMPs, reports).

## MSX (issue #5 session 9) — the M2 terminus, 6 honest variants

All from a freshly regenerated `m2_train` anchor (chain fresh-boot→M1 banner c=107→M2 spawn px 76.4 php 76 reproduced in 72 s):

- **v1**: faithful ride reproduces **px 76.4 → 822.4** (score 10930, php 121 — not a death) → S6-F1 teardown; the fine 15f ladder (3600f) shows **no (11,1) countdown**; score holds 10930 to f≈3135 then resets; flags→255 at f3480
- **v3** long watch: the teardown screen **is NOW LOADING**; the attract-logo cinematic hijacks at f≈1200-2400; at **f4020 a WINTER world spawns** (px 120.3, php 120, score 0 — a fresh run state!)
- **v4** input battery on that world: RIGHT probe → the demo's own player self-moved **−35.7 px** while taking damage (php 119→84, score 0→500) = **input-dead ATTRACT DEMO** — session-8's verdict now proven for the post-loading instance too
- **v5** (SELECT-feed through loading) and **v6** (early START taps f300/900/1500): honest negatives
- Web ground truth (Metal Slug Wiki): MS2/X arcade missions = Drifting in Desert / Monument of Depression / Madrigal of Wind / Return to Hong-Kong / Kiss in the Dark / I Wish to Believe in Love — **no train mission in the arcade order** → the SLUS train section is Arrange-mode-specific (numbering question recorded)

Net: ride → scripted crash → 52 s loading → attract hijack; the **M2→M3 gameplay gate stays OPEN**; recorded next lever = attract-flag RAM hunt around the loading window. Evidence: `scratch/issue6_round6_msx/` (6 variant reports + ladders + watch PNGs).

## New auxiliary tool: `scripts/playloop.py` (+5 mock tests)

The reusable game-loop driver factored out of the per-round probes: one-boot-per-process, `Observation` bundle (frame + madiff + padbuff), pluggable policies, honest-verdict composition, JSONL + report.

**hello_pong dogfood**: artifact **refetched** through the documented API procedure (zip sha256 `51321870…` == manifest digest; bin sha256 `a592f7ed…` == manifest), license-patched image rebuilt locally, loop run **through the tool**: boot (padbuff `00 41 ff ff`) → natural game over (madiff 5.61 burst → 0.0 static) → X restart → transition **madiff 4.223 — the round-5 causal signature reproduced exactly**. Score-region causality stays INCONCLUSIVE (the brightness-blob steering detector found no ball — threshold tuning pending; paddle control dy −90/+169 was round-5-proven). Evidence: `scratch/issue6_round6_pong_tools/`.

No game bytes committed; patched images local-only; suite 482+1xfail."""

BODY5 = """**Session 9 (round 6, the 50% main-game share) — M2 terminus characterized.** Cross-ref: full report on issue #6 (round-6 comment), commit `5ee659b`.

- Fresh anchor regeneration: `m2t7` reproduced the full chain (fresh boot → M1 banner c=107 → M2 spawn px 76.4 php 76) in 72 s; `m2_train` anchor saved.
- The deterministic RIGHT-hold ride reproduces **px 76.4 → 822.4** (score 10930, php 121 — not a death) and ends in a scripted crash teardown (S6-F1 signature).
- The teardown screen is **NOW LOADING** (~52 s, f0→f3135); the attract-logo cinematic hijacks at f≈1200-2400; at **f4020 a WINTER world spawns** (px 120.3, php 120, score 0 — fresh run state) that is **input-dead**: RIGHT probe self-moved −35.7 px while the demo's own player fought (php 119→84, score 0→500). Session-8's ATTRACT_DEMO verdict now covers the post-loading instance with sharper numbers.
- Honest negatives: SELECT-feed through the loading window (v5); early START taps at f300/900/1500 (v6). No (11,1) countdown signature exists anywhere in the 3600f ladder (v1).
- Arcade-order ground truth (Metal Slug Wiki): MS2/X missions 1-6 contain **no train mission** — the SLUS train section is Arrange-mode-specific (numbering question recorded).
- **M2→M3 gameplay gate: OPEN.** Recorded next lever: attract-flag RAM hunt around the loading window (compare RAM at demo-start vs gameplay-start).

Evidence: `scratch/issue6_round6_msx/` (6 variant reports, teardown ladders, watch PNG sequences)."""

s, d = req(f"/repos/{REPO}/issues/6/comments", method="POST",
           payload={"body": BODY6})
print("issue6:", d.get("html_url", s))
s, d = req(f"/repos/{REPO}/issues/5/comments", method="POST",
           payload={"body": BODY5})
print("issue5:", d.get("html_url", s))
