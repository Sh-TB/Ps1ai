#!/usr/bin/env python3
"""post_issue6_round16.py — Issue #6 round-16 report."""
import sys
sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO

BODY = """## Round 16 — helper-tools priority: two new reusable tools, the old-games queue intake (10 discs), and Poy Poy's match-entry blocker BROKEN (REAL_MATCH)

Per the round protocol (2–3 games): **Harvest Moon: Back to Nature** (the farming game on the list — tools track), **Poy Poy** (old game — gameplay track), MSX main-game queue continues next round.

### 1. `scripts/disc_intake.py` — one-shot local-disc intake tool ([docs/old_games_intake.md](../blob/main/docs/old_games_intake.md))

License/region + PSX-flavored PVD + full directory walk + SYSTEM.CNF + PS-EXE inventory + ASCII/SJIS census + boot-route verdict for any local `.cue`/`.bin`. New reusable dump-geometry facts encoded: **sync-measured sector stride** (our games_small dumps are 2448 B = 2352 + 96 subchannel while their cues claim MODE2/2352), **PVD-offset calibration** (cues disagree on the 150-sector pregap), MODE2 user data at raw +24, root record at 156 with ECMA-168 fallback. **10/10 local retail discs intake'd — every one ships license sectors (route 1)**; the MSX anchor reproduces the canonical EXE identity (t_size 620,544, pc0 0x80082A44). Tests run on a self-generated disc (iso9660_min) — zero game bytes in CI.

| game | serial | exe | t_size | license | route |
|---|---|---|---|---|---|
| FFT6 - World of Ruin | SCUS-94221 | SCUS_942.21 | 354,304 | YES | route 1 |
| Poy Poy (USA) | SLUS-00486 | SLUS_004.86 | 581,632 | YES | route 1 |
| Trap Gunner (USA) | SLUS-00679 | SLUS_006.79 | 1,021,952 | YES | route 1 |
| Air Hockey (USA) | SLUS-01467 | MAIN.EXE | 688,128 | YES | route 1 |
| Ballistic | SLUS-00966 | SLUS_009.66 | 1,357,824 | YES | route 1 |
| Buster Bros. Collection | (volume) | CAPCOM.EXE | 186,368 | YES | route 1 |
| Crossroad Crisis | SLUS-01342 | SLUS_013.42 | 638,976 | YES | route 1 |
| Power Play Sports Trivia | SLUS-01445 | SLUS_014.45 | 280,576 | YES | route 1 |
| XS Junior League Football | SLUS-01554 | SLUS_015.54 | 28,672 | YES | route 1 |
| Metal Slug X (USA) | SLUS-01212 | SLUS_012.12 | 620,544 | YES | route 1 |

### 2. The farming game = Harvest Moon: Back to Nature (SLUS-01115) — 5-repo tools audit + our decorpus tool ([docs/hmbtn_tools_audit.md](../blob/main/docs/hmbtn_tools_audit.md))

Audited: **hmbtn-decomp** (CC0, 53★ — matching decomp, documents the text charset + the A_FILE.BIN map where members 02..06 = `messege0..4.bin` dialogue banks, ships `afile.py`), **backtonature-decompiled** (Unlicense, 461-func EXE decomp), **HarvestMoonBTN-Recomp** (MIT, static-recompilation native port), **hmbtn-modkit** (MIT, one-command mod discs), EVENT-EDITOR (MIT). Every runnable path is bring-your-own-disc.

Built **`scripts/hmbtn_text.py`** (8 synthetic tests): the game's u16 glyph text system — documented charset + control codes, a **glyph learner** that discovered the punctuation set from the decomp's own comment↔array pairs (**353 pairs, 4,098 chars, 0 mismatches**; `'?'` 17 votes, `'.'` 39, `'!'` 4, `','` 2, `'-'` 1), evidence-recorded contraction glyphs (`0x0050='` 0x0051=`'s` 0x0054=`'m` 0x0066=`:` 0x0071=`/`), corpus extractor **310/353 (87.8%) byte-exact**, and an A_FILE.BIN container parser. Honest status: **tooling READY — boot + dialogue extraction BLOCKED_PENDING_DISC** (no SLUS-01115 disc locally; when provided: intake → afile unpack → decode → full dialogue corpus, then route-1 boot).

### 3. Poy Poy — the match-entry blocker (open since session 4) is BROKEN

New ground truth that reframes four sessions of probes: the arena scene everyone chased **is the attract demo** — it auto-starts by ~f3000 with zero input (menu11's passive timeline proves it), and the old gate-walk's "interactive menu" was the input-disabled showcase (its template was the title itself). X-hold in the demo only skips back to the title (menu19: X-hold and START-hold produce byte-identical transitions).

The verified ladder (menu20→23, checkpoint at every rung):

```
title (f2350 window) --START-hold-60f--> MODE SELECT
  (EXHIBITION / POYPOY CUP / OPTIONS, ticker "Press the X button")
  --B-hold-60f (PSX CROSS)--> PLAYER SET UP (1P human + 3 CPU, OK preselected)
  --B-hold--> PLAYER ENTRY (HARRY default 1P)
  --B-hold--> GLOVE SET UP (per-player glove list)
  --B-hold--> PRACTICE ARENA: "PRESS THE START BUTTON TO EXIT PRACTICE"
              + full control legend (X=THROW, O=SUPLEX, sq=SLAM, R1=SPECIAL,
              X=PICKUP/DUCK, O+dir=JUMP, dir+O=DIVE)
```

**Census at the practice arena: LEFT vs RIGHT = 54,357 differing bytes with det_none = 0 (fully deterministic baseline) → verdict REAL_MATCH — player input control is causal.** PoyPoyPlugin's docstring + boot_script are rewritten to the verified path (both myths corrected in-source), plugins tests green.

Method lesson recorded for the playbook: `load_state` does **not** restore `frames_run` — after every rewind, step RELATIVELY via `p.core.run(n)` (menu19's first run silently mis-aligned all windows until this was verified empirically).

### 4. Next

- Poy Poy: START exits practice → real exhibition match → closed-loop player agent (the RAM-causality discriminator stays).
- MSX (main game, Issue #7/#5): mission-select menu navigation — the r12 lever, now armed with the pulse/hold discipline measured on Poy Poy and Tetrade.
- HMBTN: awaiting the user's disc — every non-disc step is already tested.

Suite 562 passed + 1 xfail (14 new tests). No game bytes committed; corpus/text outputs stay local."""

s, d = req(f"/repos/{REPO}/issues/6/comments", method="POST", payload={"body": BODY})
print(s, d.get("html_url", d))
