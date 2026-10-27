#!/usr/bin/env python3
"""msx_r17_msel4.py — Round 17 Track C part 4: the complete selection chain.

msel3 finding: CROSS on ARCADE MISSION opens "OK? YES/NO" (YES highlighted).
Chain (fresh boot, one process):
  boot -> 4800f -> START -> menu
  -> CROSS (OK? dialog) -> CROSS (YES) -> observe -> PNG  [mission list]
  -> DOWN x1 (arcade order: entry 1 = Mission 1, so DOWN once = Mission 2)
  -> CROSS (OK?) -> CROSS (YES) -> observe 3,600 f -> PNGs + words
  M2 spawn signature: px 76.4, php 120, MISSION 2 banner, score 0.
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

EVID = "/home/z/my-project/ps1ai/scratch/round17_msx/mselect4"
CUE = "/tmp/my-project/emu/game/Metal Slug X (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/game/Metal Slug X (USA).cue"
WS = "/tmp/my-project/emu/ws_r17_msel"
PLAYER_X = 0x0CA2E0


def log(*a):
    print("[r17-msel4]", *a, file=sys.stderr, flush=True)


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def words(p):
    m = p.mem
    px = int(m.u32(PLAYER_X))
    if px >= 0x80000000:
        px -= 0x100000000
    return {"states": int(m.u8(0x95A7D)), "px": px / 65536.0,
            "php": int(m.u16(0xCA2F6)), "score": int(m.u32(0xEE318))}


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    p.core.run(4800, set())
    p.core.run(60, {"START"})
    p.core.run(900, set())
    p.save_state("msel4_menu")
    log("menu:", words(p))

    # OK? dialog + YES
    p.core.run(60, {"B"})
    p.core.run(600, set())
    p.save_state("msel4_dialog")
    p.core.run(60, {"B"})
    p.core.run(1200, set())
    snap(p, "mission_list.png")
    p.save_state("msel4_list")
    out["list_words"] = words(p)
    log("list:", out["list_words"])

    # DOWN once -> Mission 2 -> OK? -> YES
    p.core.run(120, set())
    p.core.run(30, {"DOWN"})
    p.core.run(240, set())
    snap(p, "m2_cursor.png")
    p.save_state("msel4_m2cursor")
    p.core.run(60, {"B"})
    p.core.run(600, set())
    snap(p, "m2_ok_dialog.png")
    p.save_state("msel4_m2ok")
    p.core.run(60, {"B"})
    p.core.run(1800, set())
    snap(p, "m2_load_1800.png")
    p.core.run(1800, set())
    snap(p, "m2_load_3600.png")
    out["m2_words_3600"] = words(p)
    log("m2 @3600:", out["m2_words_3600"])
    p.save_state("msel4_m2end")

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "msel4_report.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
