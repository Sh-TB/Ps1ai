#!/usr/bin/env python3
"""post_issue6_round18.py — Round 18 report on Issue #6."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO                                     # noqa: E402

BODY = """## Round 18 — closed-loop playing extends to a retail game (Poy Poy), MSX disc map, old-games boot ladder

Commit `1710b1e`. Three tracks, per the round protocol (2–3 games per round).

### Track A — Poy Poy: vision-only closed-loop agent plays a full match

Round 17 entered a REAL match (census 47,573/48,305). Round 18 makes an agent **play** it:

- **Measured foundations first** (all checkpoint-anchored, PNG evidence):
  - determinism proven: identical schedules give **ambient diff = 0** (`calib2`);
  - **B (CROSS) = grab** — a 2f tap near an orb lifts it overhead at +90f (`btnprobe`);
  - **A ≡ X** — byte-identical RAM effect twice (same action);
  - direction inputs move HARRY on screen (blue-centroid: LEFT −4.4 px, RIGHT +2.4 px per 30f, `calib3`);
  - a short carry auto-drops/lofts the orb within ~90f (`throw2` — ref vs bB branches).
- **Agent** (`poypoy_r18_agent.py`): pure vision, no RAM reads. HARRY = gray-blue
  suit mask; orbs = white blobs; 2P = yellow mask; HUD = heart-pixel counts.
  Policy: approach nearest orb → tap B → while carrying, approach nearest enemy → tap B.
- **Full match run**: 8,200 frames / 410 ticks / 37 s wall. **32 grabs, 40 throw
  attempts, 80 carry-ticks.** Multi-round dynamics observed with screens:
  t060 **"1P RETIRE!"** (round lost), t150 fresh round (02:00, full hearts),
  t300 **HARRY outlives 3P and 4P (both "RETIRE!")** while he shows only "DANGER!".
- **GIF of the real play**: https://n.uguu.se/gRbdOiKc.gif
- Honest verdict: **PLAYING (closed-loop, multi-round)** — not WON. Known gaps
  queued for r19: HARRY-mask miss 38% (screen-edge/spawn states), no charged
  throws (hold-release), no dodge behavior.

### Track B — MSX (main game): disc map + direct mission-select discovery

- 355 files re-extracted from our retail disc with the community `psx_disc.py`
  (same count as r17): `ST01..ST06` stage banks (ST05 has `_1/_2/_3`
  sub-stages), `LD/WAIT_*` load overlays, `MISSION.BIN` data table
  (`docs/msx_disc_map_r18.md`).
- EXE strings: **`MISSION SELECT` + `MISSION 1..6` + `RETRY/CONTINUE`** at
  0x860–0x8c8, plus the full CD path table (`\ST05\_3\SEQ053.BIN;1` …).
  → r19 lever: **direct MISSION 2 entry** from the main menu instead of
  sequencing through M1.

### Track C — old games: honest boot-ladder correction

- Both dumps verified retail (license string + PVD `CD001 PLAYSTATION`).
- Measured boot ladder (ballistic): dark quad → Mitchell "eO" logo →
  **INFOGRAMES publisher screen** (readable in PNG) → long black load.
  Input is inert during these static phases → censuses at f900/f6000 give 0
  diffs. Verdict: **BOOT_SEQUENCE_MEASURED, TITLE_NOT_REACHED**.
  This **corrects r16's "BOOTED"** which was RAM-churn-based, not visual
  (`docs/oldgames_r18.md`).

**Totals:** 15 new scripts, 2 new docs, Addendum 8; no game bytes committed;
framework untouched (562 passed + 1 xfail from r17 stands).

Next (r19): Poy Poy charged throws + dodge + tighter HARRY mask (target: round WIN);
MSX direct Mission 2 via MISSION SELECT; old-games title-frame census."""

s, d = req(f"/repos/{REPO}/issues/6/comments", method="POST",
           payload={"body": BODY})
print("status:", s, "| id:", d.get("id"), "| url:", d.get("html_url"))
