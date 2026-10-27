#!/usr/bin/env python3
"""post_issue6_round20.py — Round 20 (five trains + rollback recovery)."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO                                     # noqa: E402

BODY = """## Round 20 — five trains: air_hockey INTERACTIVE, MSX poke root-cause, zenmai/autogaz intake, Poy Poy live slots

Commit `28eb0c4` (on top of `9af9224`, which added the README Achievement-#1
hero + `docs/closed_loop_play_howto.md` — the "how is playing saved" recipe).

### air_hockey — **TITLE_INTERACTIVE** (supersedes r19's ALL_INERT)

r19's "input inert" was a **methodology artifact** (240f holds against a 3×-
ambient threshold on an animated title). Round 20: padbuff found
(`00 41 ff ff` @0x09FF58 port1 / 0x09FF7A port2, mask word @0x09FF5A);
a **3f-pulse battery** at the title produced single-frame RAM deltas up to
**145,234 B** (ambient max 363), the screen changed 95% by f2357, and VLM
reads f2400 as a **"PLAYER SELECT"** menu (absent from r19's no-input attract
loop) and f3800 as **"FIGHT ME! / GO THUNDER BOY" = live gameplay**.
Title → menu → gameplay, through legal inputs only.

### MSX — the mission-poke mystery is root-caused (r19 conclusion retracted)

GS pokes `800D4210=0002 + 800D4212=0202` (readback-verified every frame) and
the game **still started Mission 1**. Static RE of SLUS_012.12:
- u16@0x800D4210 = **unlock counter** — 4 menu-only readers (`slti v0,v0,2`
  ×2, clamp loop, `lbu`), **zero stage-loader readers**;
- u16@0x800D4212 = single writer `sh 0xFFFF` (unlock-all); byte 0x0D4213 =
  the known GS unlock byte.
So the block is **unlock state, not a stage selector** — r19's expC
("mission=1 → M1 ⇒ 1-based indexing") was a **no-op** (arcade default IS M1)
and is retracted at mechanism level. True levers for r21: the consumer
@0x8002CB30 of the (mission,area) byte table @0x80010EE8, or the legit
**MISSION SELECT** pause menu (strings @0x8001019C).

### zenmai — **BOOTED_TEXT** + the iso9660 writer root-cause fix

Raw PS-EXE CD-wrapped (`SYSTEM.CNF` → `ZENMAI.EXE`) + license-patched: boots
to the **"Zork I — a Z-machine for Japanese and a game controller"** title at
~f700 (RAM 549 KB, "West of House" resident). Bonus: the historical
synthetic-disc CDChecker loop was **the writer itself** — `iso9660_min.py`
now emits MSF = LBA+150, VDT `FF×8+CD001+0x01`, subheader `0x09` (test
pinned, 6/6). Input **unproven**: zenmai polls the pad via **direct SIO**
(0x1F80104x, no BIOS InitPAD, no `0041ffff` padbuff) — a zenmai-specific
behavior under beetle+OpenBIOS (Tetrade control proved input delivery the
same session).

### autogaz — **BOOTED_TITLE**

License-patched boot @f1200; game loop alive (u32 frame counter @0x800BCC00,
+1/frame); kernel pad pattern @0xB008. Input not responsive yet (7 probes ×
2 boots — the direct-SIO suspicion above may explain it too). Manifest entry
added (MIT, artifact sha256-verified).

### Poy Poy — **PLAYING**, live slots narrowed

Behavioral slot candidates found: **0x8009F778 / 0x8009F780 / 0x8009F7B0 /
0x8009F7EA** (screen-range u16s, non-monotone, detrended corr ±0.72 with the
visibly-moving opponent, transiently 0 at the VLM-verified hit moment).
16 charged throws; best = 3P hearts 2→1 + explosion (run-3 f1022). No second
retire yet — the writer-proof + camera mapping is the r21 lever.
GIF: https://d.uguu.se/XhQSPUQH.gif

### Housekeeping

- **Manifest**: `autogaz` + `zenmai` accepted entries merged — **7 games
  total**; `round20_addendum` documents the intake wave.
- **Sandbox-rollback incident**: the workspace rolled back to `6b97fbe`
  mid-round; GitHub remote was intact (all r17–r19 history + the parallel
  session's `9af9224`). Local `reset --hard` to origin; 11 r20 scripts + the
  iso fix + manifest entries rescued; lost scratch evidence reconstructed
  from the trains' final reports (files marked RECONSTRUCTED).
- Suite: **565 passed + 1 xfail**; no game bytes committed.

Next (r21): MSX stage-loader global via the (mission,area) consumer, or the
legit MISSION SELECT pause; mednafen backend for direct-SIO pad games
(zenmai/autogaz); Poy Poy writer-proof → retire #2/#3 → LUCK BONUS;
air_hockey single-button causality map (it is now the third PLAYING
candidate)."""

s, d = req(f"/repos/{REPO}/issues/6/comments", method="POST",
           payload={"body": BODY})
print("status:", s, "| id:", d.get("id"), "| url:", d.get("html_url"))
