#!/usr/bin/env python3
"""msx_r17_msel2.py — Round 17 Track C part 2: enter ARCADE MISSION, find the
cursor word by full-RAM diff, select Mission 2.

msx_r17_msel proved: fresh boot -> START -> main menu (ARCADE MISSION /
COMBAT SCHOOL / SETTINGS / OPTION), states byte 0x9, and DOWN moves the
highlight (COMBAT SCHOOL png). The cursor word sits outside the 18 tracked
table words. This probe, in ONE fresh boot process:

  1. Re-run the boot->START path, checkpoint the menu state (fresh boot
     instead of checkpoint restore so the whole path is reproducible).
  2. Confirm ARCADE MISSION (START hold, then CROSS hold as fallback), PNG.
  3. FULL-RAM (2 MB) census: none vs UP vs DOWN — list every changed
     4-byte window (the cursor word + any echo), so the selector is pinned
     for future rounds.
  4. Cursor DOWN x1 (Mission 2 in arcade order), PNG, confirm with START,
     observe 3,600 f: PNGs + px/php/score — M2 spawn signature = px 76.4,
     php 120, "MISSION 2" banner.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.api import PS1Play                                   # noqa: E402

EVID = "/home/z/my-project/ps1ai/scratch/round17_msx/mselect2"
CUE = "/tmp/my-project/emu/game/Metal Slug X (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/game/Metal Slug X (USA).cue"
WS = "/tmp/my-project/emu/ws_r17_msel"

STATES_BYTE = 0x00095A7D
PLAYER_X = 0x0CA2E0
PLAYER_HP = 0x0CA2F6
A_SCORE = 0x0EE318


def log(*a):
    print("[r17-msel2]", *a, file=sys.stderr, flush=True)


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def ram(p):
    return np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()


def words(p):
    m = p.mem
    px = int(m.u32(PLAYER_X))
    if px >= 0x80000000:
        px -= 0x100000000
    return {"states_byte": int(m.u8(STATES_BYTE)), "px": px / 65536.0,
            "php": int(m.u16(PLAYER_HP)), "score": int(m.u32(A_SCORE))}


def changed_windows(a, b, width=4):
    """Index ranges (u32 words) where a and b differ, merged+counted."""
    d = np.flatnonzero(a.view(np.uint32) != b.view(np.uint32))
    if len(d) == 0:
        return 0, []
    runs = []
    start = prev = int(d[0])
    for i in d[1:]:
        i = int(i)
        if i == prev + 1:
            prev = i
        else:
            runs.append((start, prev))
            start = prev = i
    runs.append((start, prev))
    return len(d), [(s, e) for s, e in runs[:24]]


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    # ---- boot to the main menu (r17_msel path: idle 4800 + START) ----
    p.core.run(4800, set())
    p.core.run(60, {"START"})
    p.core.run(900, set())
    snap(p, "menu.png")
    p.save_state("msel2_menu")
    out["menu_words"] = words(p)
    log("menu:", out["menu_words"])

    # ---- confirm ARCADE MISSION (cursor default on entry 1) ----
    p.core.run(60, {"START"})
    p.core.run(1200, set())
    snap(p, "arcade_entered.png")
    p.save_state("msel2_arcade")
    out["arcade_words"] = words(p)
    log("arcade:", out["arcade_words"])

    # ---- full-RAM cursor census ----
    base = ram(p)
    p.save_state("msel2_censbase")
    probes = {}
    for name, btns in (("none", set()), ("up", {"UP"}), ("down", {"DOWN"})):
        p.load_state("msel2_censbase")
        p.core.run(120, set())
        p.core.run(30, btns)
        p.core.run(240, set())
        snap(p, f"cens_{name}.png")
        probes[name] = ram(p)
    n_none, run_none = changed_windows(base, probes["none"])
    n_up, run_up = changed_windows(probes["none"], probes["up"])
    n_dn, run_dn = changed_windows(probes["none"], probes["down"])
    out["census"] = {"none_vs_base_windows": run_none, "n_none": n_none,
                     "up_vs_none_n": n_up, "up_vs_none_windows": run_up,
                     "down_vs_none_n": n_dn, "down_vs_none_windows": run_dn}
    log("census:", json.dumps(out["census"]))

    # ---- select Mission 2: DOWN once from the arcade list base, confirm ----
    p.load_state("msel2_censbase")
    p.core.run(120, set())
    p.core.run(30, {"DOWN"})
    p.core.run(240, set())
    snap(p, "mission2_cursor.png")
    p.save_state("msel2_m2cursor")
    p.core.run(60, {"START"})
    p.core.run(3600, set())
    snap(p, "after_confirm_3600.png")
    out["after_confirm"] = words(p)
    log("after confirm:", out["after_confirm"])

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "msel2_report.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
