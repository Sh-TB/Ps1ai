#!/usr/bin/env python3
"""msx_r17_msel3.py — Round 17 Track C part 3: CROSS confirms the menu entry.

msel2 finding: START-hold on the main menu does nothing (arcade_entered.png
= unchanged menu). Arcade convention: the FIRE button (PSX CROSS) selects.
This probe (fresh boot, one process):
  boot -> 4800f -> START -> menu (checkpoint msel2_menu exists from msel2;
  re-created here for reproducibility) -> CROSS-hold60 -> observe 1200 ->
  PNG (mission list expected: 17 entries) -> full-RAM UP/DOWN census ->
  DOWN x1 (Mission 2, arcade order) -> CROSS confirm -> observe 3,600 f
  (M2 banner / px 76.4 spawn signature).
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

EVID = "/home/z/my-project/ps1ai/scratch/round17_msx/mselect3"
CUE = "/tmp/my-project/emu/game/Metal Slug X (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/game/Metal Slug X (USA).cue"
WS = "/tmp/my-project/emu/ws_r17_msel"

PLAYER_X = 0x0CA2E0
PLAYER_HP = 0x0CA2F6
A_SCORE = 0x0EE318


def log(*a):
    print("[r17-msel3]", *a, file=sys.stderr, flush=True)


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
    return {"states": int(m.u8(0x95A7D)), "px": px / 65536.0,
            "php": int(m.u16(PLAYER_HP)), "score": int(m.u32(A_SCORE))}


def changed_words(a, b, max_list=30):
    d = np.flatnonzero(a.view(np.uint32) != b.view(np.uint32))
    return int(len(d)), [int(i) * 4 for i in d[:max_list]]


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    p.core.run(4800, set())
    p.core.run(60, {"START"})
    p.core.run(900, set())
    p.save_state("msel3_menu")
    snap(p, "menu.png")

    # ---- CROSS confirms ARCADE MISSION ----
    p.core.run(60, {"B"})            # B = PSX CROSS
    p.core.run(1200, set())
    snap(p, "cross_entered.png")
    out["after_cross"] = words(p)
    p.save_state("msel3_list")
    log("after cross:", out["after_cross"])

    # ---- cursor census on the mission list ----
    p.load_state("msel3_list")
    p.core.run(120, set())
    base = ram(p)
    p.save_state("msel3_censbase")
    probes = {}
    for name, btns in (("none", set()), ("up", {"UP"}), ("down", {"DOWN"}),
                       ("down3", {"DOWN"}) ):
        p.load_state("msel3_censbase")
        p.core.run(120, set())
        n = 3 if name == "down3" else 1
        for _ in range(n):
            p.core.run(30, btns)
            p.core.run(60, set())
        p.core.run(240, set())
        snap(p, f"cens_{name}.png")
        probes[name] = ram(p)
    n_up, w_up = changed_words(probes["none"], probes["up"])
    n_dn, w_dn = changed_words(probes["none"], probes["down"])
    n_d3, w_d3 = changed_words(probes["down"], probes["down3"])
    out["census"] = {"up_n": n_up, "up_words": w_up,
                     "down_n": n_dn, "down_words": w_dn,
                     "down3_extra_n": n_d3, "down3_extra_words": w_d3}
    log("census:", json.dumps(out["census"]))

    # ---- Mission 2: DOWN once, CROSS confirm, long observe ----
    p.load_state("msel3_censbase")
    p.core.run(120, set())
    p.core.run(30, {"DOWN"})
    p.core.run(240, set())
    snap(p, "m2_cursor.png")
    p.save_state("msel3_m2cursor")
    p.core.run(60, {"B"})
    p.core.run(3600, set())
    snap(p, "m2_after_confirm_3600.png")
    out["m2_after"] = words(p)
    log("m2 after:", out["m2_after"])
    p.save_state("msel3_m2end")

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "msel3_report.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
