#!/usr/bin/env python3
"""r35c_win_probe.py — R35-C phase 3: win-state forensics (no new boots).

1. Restore pre-win checkpoint (REVT=157): MINC/flagged/ctrl_dis before win.
2. Restore post-win checkpoint (REVT=160): verify flagged set == mine set,
   revealed set == safe set (auto-flag on win, not manual).
3. Visual forensics on the win screen PNGs (diff bboxes).
4. Behavior probes on a disposable copy of the win state: stability watch,
   START-after-win (restart?), dpad ignored (ctrl_dis=1).
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import r35c_lib as L  # noqa: E402
from ps1play.core.host import LibretroCore  # noqa: E402

os.makedirs(os.path.join(L.WS, "system"), exist_ok=True)
if not os.path.exists(os.path.join(L.WS, "system", "openbios.bin")):
    import shutil
    shutil.copyfile(L.BIOS, os.path.join(L.WS, "system", "openbios.bin"))
core = LibretroCore(L.CORE, os.path.join(L.WS, "system"),
                    os.path.join(L.WS, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
L.core = core
core.load_game(L.CONTENT)  # mechanical substrate of restore (not a boot)
led = json.load(open(L.LEDDER))
led["log"].append({"boot": None, "kind": "restore_not_counted",
                   "script": "r35c_win_probe.py",
                   "t": time.strftime("%FT%TZ", time.gmtime())})
json.dump(led, open(L.LEDDER, "w"), indent=1)


def restore(name):
    core.unserialize(open(os.path.join(L.WS, name), "rb").read())
    for _ in range(2):  # render one frame so frame_rgb() is valid
        core.run_frame()
    L.jlog("restore", checkpoint=name, sym=L.sym())


def board_sets():
    cells = L.decode()
    mines = {k for k, v in cells.items() if v["mine"]}
    revealed = {k for k, v in cells.items() if v["revealed"]}
    flagged = {k for k, v in cells.items() if v["flagged"]}
    safe = {k for k, v in cells.items() if v["active"] and not v["mine"]}
    return cells, mines, revealed, flagged, safe


# ---- 1: pre-win bracket ------------------------------------------------------
restore("ck_reveal_0013108.bin")  # REVT=157
pre = {"stats": L.stats(L.decode()), "sym": L.sym()}
L.snap(core, "prewin_revt157")

# ---- 2: post-win verification -------------------------------------------------
restore("ck_reveal_0014665.bin")  # REVT=160 post-win
cells, mines, revealed, flagged, safe = board_sets()
post = {"stats": L.stats(cells), "sym": L.sym(),
        "flagged_eq_mines": flagged == mines,
        "revealed_eq_safe": revealed == safe,
        "n_flag_on_nonmine": len(flagged - mines),
        "n_unflagged_mine": len(mines - flagged)}
L.jlog("win_state_verify", **post)
assert post["flagged_eq_mines"] and post["revealed_eq_safe"], post

# ---- 3: visual forensics ------------------------------------------------------
def arr_of(tag):
    fs = sorted(f for f in os.listdir(L.SHOTS) if f.startswith(tag))
    return np.asarray(Image.open(os.path.join(L.SHOTS, fs[-1])).convert("RGB"))

a_pre = arr_of("prewin_revt157")        # REVT=157 board
a_clr = arr_of("full_clear")            # click+settle after final reveal
a_180 = arr_of("full_clear_plus180f")   # +180f settled
for nm, a, b in (("prewin_vs_clear", a_pre, a_clr),
                 ("clear_vs_180f", a_clr, a_180),
                 ("prewin_vs_180f", a_pre, a_180)):
    d = np.abs(a.astype(int) - b.astype(int)).sum(2)
    ys, xs = np.nonzero(d > 30)
    bb = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()),
          int((d > 30).sum())] if len(xs) else None
    L.jlog("visual_diff", pair=nm, bbox_x0y0x1y1_npx=bb,
           mean=round(float(d.mean()), 3))
# crop the top-right text zone used by loss ("GAME OVER." at ~200,4)
crop = Image.fromarray(a_180[0:24, 150:320])
crop.save(os.path.join(L.SHOTS, "win_text_zone.png"))
crop2 = Image.fromarray(a_180[0:40, 0:320])
crop2.save(os.path.join(L.SHOTS, "win_top_zone.png"))

# ---- 4: behavior probes on disposable win state --------------------------------
b0 = bytes(core.ram[L.BOARD:L.BOARD + 4608])
# 4a: stability 240f
base = core.frame_rgb()
md = 0.0
for _ in range(4):
    for _ in range(60):
        core.run_frame()
    arr = core.frame_rgb()
    if arr is not None:
        md = max(md, float(np.abs(arr.astype(int) - base.astype(int)).mean()))
L.snap(core, "win_stable_240f")
L.jlog("win_stability", watch=240, max_frame_diff=round(md, 3), sym=L.sym())

# 4b: dpad with ctrl_dis=1 -> cursor should not move
L.pulse(core, "RIGHT", hold=2, settle=45)
L.jlog("dpad_after_win", cursor=[L.i32(L.CURX), L.i32(L.CURY)],
       note="expect (0,11) unchanged if controls disabled", sym=L.sym())

# 4c: START after win -> restart or ignore?
L.pulse(core, "START", hold=2, settle=90)
b1 = bytes(core.ram[L.BOARD:L.BOARD + 4608])
L.snap(core, "after_start_on_win")
L.jlog("start_after_win", board_changed=b0 != b1,
       stats=L.stats(L.decode()), sym=L.sym())

print("[r35c] WIN PROBE DONE", flush=True)
