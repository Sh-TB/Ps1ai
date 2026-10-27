#!/usr/bin/env python3
"""post_issue6_round17.py — the round-17 report comment on Issue #6."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO                                     # noqa: E402

BODY = """## Round 17 — helper tools first + old games + the main game (2 of 2 games closed, 1 opened wide)

**TL;DR:** Poy Poy's real match is finally ENTERED (the r16 tail is closed —
the door was in r16's own screenshots). The farming game's (HM:BTN) GitHub
community toolchain is now PROVEN runnable here, disc-free — including
**building the matching decompilation to byte-identical binaries**. And on
the main game, the MSX menu system turns out to be **navigable end to end
by pure input** (fresh boot → live Mission 1 with zero plugin policy).

### 1. Poy Poy (old game) — REAL_MATCH_ENTERED ✅

* START-exit from the PRACTICE arena **aborts to the boot logo** (logo →
  title → attract demo). The match never starts that way — the r16
  "PRESS THE START BUTTON TO EXIT PRACTICE" banner was a red herring.
* The real door was in r16's own evidence all along: `m23_b0` = **STAGE
  SELECT** (3 arena thumbnails + a red PRACTICE label — our earlier
  B-confirm had been selecting PRACTICE itself).
* From STAGE SELECT: UP×2 + CROSS → **live 4-player exhibition match** in
  the penguin arena. Direction census: left_vs_right **47,573 / 50,049**
  differing bytes, det_none **0** → REAL_MATCH at two probe states.
* The match then plays on by itself: 1P/2P/3P **RETIRE!** (hearts drain on
  the HUD), a **LUCK BONUS** scoring screen (PTS 0/5/4/7), and the series
  rolls into the **next arena** (timer reset 02:00, everyone re-spawned) —
  exhibition is a multi-arena series.
* Honest status: REAL_MATCH_ENTERED + first scripted touches (11 PNGs).
  The closed-loop WIN agent (protect HARRY, pickup+throw servo) is the
  round-18 target. Tools: `poypoy_r17_{realmatch,stageselect,firsttouch}`.

### 2. HM:BTN (the farming game) — community tools 4/4 PASS + decomp builds byte-identically ✅

Round 16 audited 5 repos; round 17 **executes** them
(`scripts/r17_hmbtn_tooltest.py`, report = facts only, no game bytes):

| tool (coalslav/hmbtn-decomp, CC0) | test | verdict |
|---|---|---|
| `afile.py` | synthetic A_FILE.BIN/HDT unpack + pack | **bit-exact both ways** |
| `psx_disc.py extract` | OUR OWN Metal Slug X disc | 355 files + SYSTEM.CNF + license + EXE |
| `PsxExeHeader.parse` | extracted MSX EXE | pc0 `0x80082A44` / t_size 620,544 / NA marker — **cross-checks our independent `disc_intake` anchor exactly** |
| `psx_disc.py build` | synthetic mini layout | **bit-exact round-trip** |

**The centerpiece:** `hmbtn-decomp`'s disc-free mode builds and checks the
14 code binaries with GCC 2.95.2-psx + PSY-Q 4.7 + maspsx + mips binutils:

```
SLUS_011.15: OK   11_GF_FARM.bin: OK   27_GF_TITLE.Bin: OK   …
→ "all 14 files match the original"
```

The EXE **and all 13 overlays** compile from the community C source to
SHA-1-verified byte-identical binaries. Three sandbox adaptations were
needed and are documented (none touch the decomp source):

1. **qemu-i386 wrappers** — the 1999 i386 static binaries die with seccomp
   `SIGSYS` when run natively; qemu translates their old syscalls.
2. **tmpfs source tree** — cpp 2.95.2's `stat()` gets `EOVERFLOW` on the
   overlayfs 64-bit inodes; sources + headers live on `/dev/shm`.
3. **local `psx_cc.py` depfile synthesis** — cpp `-M/-MD` modes are
   seccomp-blocked natively (backup `.orig` kept).

Still disc-gated (honest list): the actual dialogue/story extraction
(needs the disc's A_FILE.BIN → `messege0..4.bin`), the real disc-image
build, the recomp runtime, modkit `hm.py build <mod> <base>`.
Writeup: `docs/hmbtn_tools_round17.md`.

### 3. MSX (main game) — the menus are navigable by pure input ✅

Four probes, one boot each (`msx_r17_msel{,2,3,4}`):

* boot idle strip: states byte `0x95A7D` walks `0x0 → 0x6 → 0x9`.
* START → **main menu** (ARCADE MISSION / COMBAT SCHOOL / SETTINGS /
  OPTION). DOWN moves the highlight (COMBAT SCHOOL PNG); the cursor word
  is NOT in the r12 table window — full-RAM diff pins it at u32 run
  `0x957D8–0x957F8`.
* **START does not confirm; CROSS does** — CROSS opens the arcade-style
  `OK? YES/NO` dialog.
* The full confirmed chain: boot → 4800f → START → CROSS → OK?YES →
  **SOLDIER SELECT** (Marco/Eri/Tarma/Fio) → select → OK?YES →
  **LIVE MISSION 1 GAMEPLAY** (night desert, HUD: credits 3, 1UP=2,
  score 48, px 116.15, php 116).
* The whole ladder is checkpointed (`ws_r17_msel/msel4_*`). The
  deterministic per-mission entry (MISS01..MISS16.BIN sequencer path) is
  now a ladder-discipline problem, not an attract-mode mystery.

### Suite

562 passed + 1 xfailed (baseline intact; all new scripts additive).
No game bytes committed. Evidence: `scratch/round17_msx/` + local emulator
evidence dirs; reports are facts-only JSON."""

s, d = req(f"/repos/{REPO}/issues/6/comments", method="POST",
           payload={"body": BODY})
print("status:", s, "id:", d.get("id") if isinstance(d, dict) else d)
print("url:", d.get("html_url") if isinstance(d, dict) else "")
