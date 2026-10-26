#!/usr/bin/env python3
"""post_issue6_round13.py — Round 13 close-out: manifest + docs
addendum + repo worklog + Issue #6 report.

Round 13 = showcase the FINISHED game (hello_pong complete-loop GIF,
uploaded to a public host) + add TWO new games (psxBreakout candidate,
Cave Story PSX accepted) + the PSX-PVD-156 boot-loader finding."""
import json
import os
import shutil
import sys

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO as SLUG                            # noqa: E402

GIF_SRC = "/home/z/my-project/download/hello_pong_complete_gameplay.gif"
GIF_DIR = os.path.join(REPO, "docs", "evidence", "round13")
GIF_URL = "https://h.uguu.se/rcAKDwni.gif"

DOUKUTSU = {
    "id": "doukutsupsx",
    "plugin": None,
    "source": "https://github.com/fgsfdsfgs/doukutsupsx",
    "license": "MIT (port); Cave Story (c) Studio Pixel — freeware",
    "revision": "release v0.7 (2022-10-13)",
    "artifacts": [
        {"name": "doukutsu_r7_us.iso",
         "url": "https://github.com/fgsfdsfgs/doukutsupsx/releases/"
                "download/v0.7/doukutsu_r7_us.iso",
         "bytes": 32565792,
         "sha256": "bf15559eef20cded0d728e4c97da6830a1d4f7bb83a5c1e5d"
                   "ffb5fc755c27554"},
        {"name": "doukutsu_lic.bin",
         "url": None,
         "note": "local MODE2/2352 copy of the release iso; the release "
                 "already carries the standard US 'Sony Computer "
                 "Entertainment' license block (byte-identical to the "
                 "local retail license patch — overwrite was a no-op, "
                 "same sha256); cue generated locally",
         "bytes": 32565792,
         "sha256": "bf15559eef20cded0d728e4c97da6830a1d4f7bb83a5c1e5d"
                   "ffb5fc755c27554"}],
    "boot_exe": "doukutsu.ps-exe",
    "status": "BOOTED_TITLE — round 13: beetle-psx + OpenBIOS, one boot; "
              "shell cube -> LOADING (f~720) -> Studio Pixel intro -> "
              "'Cave Story' title menu New/Load/Options @ f1740 (mean "
              "26.84, anim madiff 15.14), 2 pad buffers detected; PNG "
              "evidence scratch/round13_newgames/doukutsu_long/ "
              "(report.json + 9 PNGs + long timeline jsonl). Next "
              "finish-target.",
}

PSXBREAKOUT = {
    "id": "psxbreakout",
    "plugin": None,
    "source": "https://github.com/NDR008/psxBreakout",
    "license": "unspecified public release (CS50 final project)",
    "revision": "release v1.0 (cs50x.exe, 79,872 B)",
    "artifacts": [
        {"name": "cs50x.exe",
         "url": "https://github.com/NDR008/psxBreakout/releases/"
                "download/v1.0/cs50x.exe",
         "bytes": 79872,
         "sha256": "822a50e6fe77e5c43caef377acf4363d5f9da35cbd4ef0b8be"
                   "bbc408d3cc2425"}],
    "boot_exe": "cs50x.exe",
    "status": "CANDIDATE — honest boot gate: exe header loads (RAM sig "
              "@f440) then boot-loop wipe by f640; user RAM all zero at "
              "f900; verdict EXE_LOAD_CRASH under OpenBIOS. Two image "
              "routes tried: (a) hand-rolled strict-ECMA ISO9660 -> "
              "shell cube loop (BIOS never left the shell), (b) "
              "hello_pong-container payload swap (dirent size patched "
              "LE+BE, verified readback) -> load+crash. Suspects: "
              "OpenBIOS A0-table gap vs PSYQ expectations, or exe "
              "targets retail BIOS/emulator loaders (ePSXe runs bare "
              "exe). Next lever: retry under a retail-BIOS profile or "
              "rebuild from source against psn00bsdk.",
}


def update_manifest():
    path = os.path.join(REPO, "data", "homebrew", "manifest.json")
    m = json.load(open(path))
    if not any(a.get("id") == "doukutsupsx" for a in m["accepted"]):
        m["accepted"].append(DOUKUTSU)
    if not any(c.get("id") == "psxbreakout"
               for c in m["candidates_pending"]):
        m["candidates_pending"].append(PSXBREAKOUT)
    m["round13_addendum"] = {
        "date": "2026-10-26",
        "gif_deliverable": {
            "game": "hello_pong", "verdict": "GIF_COMPLETE_LOOP",
            "frames_captured": 1171, "gif_frames": 390, "fps": 20,
            "bytes": 72594,
            "sha256": "7fa336065761af992bdce41bba0f2e489ecaa45f4de91bda"
                      "6fa9570fbdc1de3c",
            "public_url": GIF_URL,
            "committed": "docs/evidence/round13/"
                         "hello_pong_complete_gameplay.gif",
            "loop": "menu-X -> game1 natural 5-x WIN -> GAME_OVER -> "
                    "X -> menu -> X -> game2 natural 5-x WIN -> "
                    "GAME_OVER -> X -> menu; score word 0x1ffeb4 "
                    "read 2..5 per game; paddle wiggle visible"},
        "new_games": ["doukutsupsx (accepted, BOOTED_TITLE)",
                      "psxbreakout (candidate, EXE_LOAD_CRASH)"],
        "finding_pvd156": "hello_pong's PSX-flavored PVD puts the root "
                          "dir record at offset 156 (not ECMA-119's "
                          "168) — and a strict-ECMA hand-rolled ISO "
                          "falls back to the shell cube under the PSX "
                          "BIOS, consistent with the BIOS reading the "
                          "root record at 156. Encoded in "
                          "r13_breakout_container.find_root_record().",
        "tools": ["hellopong_r13_gif", "r13_gh_check", "r13_new_games",
                  "r13_breakout_container", "r13_boot_new",
                  "r13_diag_cs50x", "r13_diag_watch", "r13_diag_v1",
                  "r13_doukutsu_long"],
    }
    json.dump(m, open(path, "w"), indent=2)
    print("manifest updated:",
          [a["id"] for a in m["accepted"]],
          [c["id"] for c in m["candidates_pending"]])


DOCS_ADDENDUM = """
## Addendum 5 (2026-10-26) — round 13: finished-game showcase + two new games

- **hello_pong complete-gameplay GIF** (the round-12 WIN_CAUSAL game):
  1,171 emulated frames captured (every frame), ffmpeg palettegen
  fps=20 -> 390-frame GIF, 72,594 B,
  sha256 7fa33606...c1de3c. Loop: menu -(X)-> game 1 natural play
  (paddle wiggle visible, score word 0x1ffeb4 reads 2..5) -> 5-x
  GAME_OVER -(X)-> menu -(X)-> fresh game 2 -> 5-x GAME_OVER -(X)->
  menu. Verdict **GIF_COMPLETE_LOOP**. Public upload
  <https://h.uguu.se/rcAKDwni.gif> + committed at
  `docs/evidence/round13/hello_pong_complete_gameplay.gif`.
- **Cave Story PSX added (accepted)** — doukutsupsx v0.7 release iso
  (31,802 KB, sha-verified): license block already standard US, boot
  under beetle+OpenBIOS reaches the real title menu (New/Load/Options)
  at f1740. Becomes the next finish-target.
- **psxBreakout added (candidate)** — bare PS-EXE: locally built
  ISO9660 + license patch; honest boot gate EXE_LOAD_CRASH (header in
  RAM @f440, boot-loop wipe @f640, user RAM zero @f900).
- **New finding (PSX boot loader)**: hello_pong's PVD carries the root
  directory record at offset **156**, not ECMA-119's 168; a
  strict-ECMA image drops to the shell cube loop — consistent with the
  BIOS reading the root record at 156 on PSX-flavored images.
"""


def update_docs():
    path = os.path.join(REPO, "docs", "tools_matrix_issue6.md")
    with open(path, "a") as f:
        f.write(DOCS_ADDENDUM)
    print("docs addendum 5 appended")


WORKLOG = """
## 2026-10-26 — Issue #6 round 13 (showcase + 2 new games)

**hello_pong (finished) showcase**: hellopong_r13_gif.py — ONE boot,
1,171 frames captured (every frame) through the complete loop
(menu->game1 5-x WIN->GAME_OVER->X->menu->game2 5-x WIN->GAME_OVER->
X->menu), ffmpeg palettegen GIF 390 f @20 fps, 72,594 B, uploaded to
uguu.se + committed to docs/evidence/round13/. Score sensor (0x1ffeb4)
read live 1..5 per game; X-release transitions verified per leg
(mirror-held reads 0x168b4=49151). Verdict GIF_COMPLETE_LOOP.

**New game 1 — Cave Story PSX (accepted)**: r13_new_games.py fetched
fgsfdsfgs/doukutsupsx v0.7 US iso (sha256 verified; license block
byte-identical to the standard US retail license -> local patch
no-op). r13_doukutsu_long.py (one boot): shell cube -> LOADING ->
Studio Pixel intro -> title menu (New/Load/Options) @f1740, 2 pad
buffers, PNG evidence. Next finish-target.

**New game 2 — psxBreakout (candidate, honest)**: bare PS-EXE from
NDR008/psxBreakout v1.0. Route A: hand-rolled strict-ECMA ISO9660
(PVD+path tables+root) -> shell cube loop. **Finding**: hello_pong's
PVD deviates from ECMA-119 — root dir record at offset 156; the PSX
BIOS likely reads it there. Route B (container): swapped cs50x.exe
into the proven-bootable hello_pong image at the GAMEPS1.EXE dirent
(extent 24, size patched LE+BE, verified): exe header lands in RAM
@f440, wiped by f640 (boot loop), user RAM zero @f900 ->
EXE_LOAD_CRASH under OpenBIOS; candidate recorded with next levers.

Suite untouched this round (no core changes; all new scripts are
additive tools). No game bytes committed.
"""


def update_worklog():
    with open(os.path.join(REPO, "worklog.md"), "a") as f:
        f.write(WORKLOG)
    print("repo worklog appended")


def commit_gif():
    os.makedirs(GIF_DIR, exist_ok=True)
    dst = os.path.join(GIF_DIR, "hello_pong_complete_gameplay.gif")
    shutil.copyfile(GIF_SRC, dst)
    print("gif copied to", dst)


BODY = """**Round 13 — showcase the finished game + add two new games
(2-game round per the round protocol).**

## hello_pong (finished, WIN_CAUSAL r12) — complete-gameplay GIF

`hellopong_r13_gif.py`, ONE boot, **every emulated frame captured
(1,171)** through the complete loop: menu -(X rel)-> game 1 natural
play (visible paddle wiggle; score word 0x1ffeb4 read live 2..5) ->
**5-x WIN -> GAME_OVER** -(X rel)-> menu -(X rel)-> fresh game 2 ->
**5-x WIN -> GAME_OVER** -(X rel)-> menu. Verdict
**GIF_COMPLETE_LOOP**. ffmpeg palettegen, 390 frames @20 fps,
72,594 B: **<https://h.uguu.se/rcAKDwni.gif>** (also committed:
`docs/evidence/round13/hello_pong_complete_gameplay.gif`).

## Cave Story PSX — ADDED and ACCEPTED (next finish-target)

doukutsupsx **v0.7** release iso (fgsfdsfgs/doukutsupsx, 31,802 KB,
sha256-verified). The release carries the standard US license block
(byte-identical to our local retail patch — the patch was a no-op).
One boot, beetle + OpenBIOS: shell cube -> LOADING (f~720) -> "Studio
Pixel presents" intro -> **"Cave Story" title menu (New / Load /
Options) at f1740** (mean 26.84, anim madiff 15.14, 2 pad buffers).
PNG evidence `scratch/round13_newgames/doukutsu_long/`. Manifest:
accepted (4th game).

## psxBreakout — ADDED as candidate (honest boot gate)

NDR008/psxBreakout v1.0 ships a bare PS-EXE (`cs50x.exe`, 79,872 B).
Two local image routes, both documented: (a) hand-rolled strict-ECMA
ISO9660 -> shell cube loop; (b) payload swap into the proven-bootable
hello_pong container (dirent size patched, readback-verified) ->
**exe header lands in RAM @f440, boot-loop wipe by f640, user RAM
zero @f900** = EXE_LOAD_CRASH under OpenBIOS (suspect: PSYQ-vs-A0
expectations / retail-BIOS target). Next levers recorded in the
manifest candidate entry.

## New boot-loader finding (PSX-flavored PVD)

hello_pong's PVD puts the root directory record at offset **156**
(not ECMA-119's 168); the strict-ECMA hand-rolled image falls back to
the shell cube loop — consistent with the PSX BIOS reading the root
record at 156. Encoded as `find_root_record()` in
`scripts/r13_breakout_container.py`.

Suite untouched this round (additive tools only, no core edits). No
game bytes committed."""


def post_issue():
    s, d = req(f"/repos/{SLUG}/issues/6/comments", method="POST",
               payload={"body": BODY})
    print("issue #6 comment:", s, d.get("id"), d.get("html_url"))


if __name__ == "__main__":
    update_manifest()
    update_docs()
    update_worklog()
    commit_gif()
    post_issue()
