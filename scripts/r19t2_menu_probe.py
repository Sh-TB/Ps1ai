#!/usr/bin/env python3
"""r19t2_menu_probe.py — Round 19 T2 step 1: main-menu inspection + cursor diff.

r17 ladder (proven): boot -> 4800f -> START -> main menu; CROSS on entry 1
(ARCADE MISSION) -> OK? YES -> SOLDIER SELECT -> M1 gameplay.
r18 finding: TITLE.BIN strings = OPTION / ANOTHER MISSION / COMBAT SCHOOL /
ARCADE MISSION (+ key config); EXE has "MISSION SELECT" + "MISSION 1..6".
z-ai vision on the r17 menu.png: visible entries ARCADE MISSION / MISSION
BRIEFING / ARMORY / OPTION, entry 1 highlighted -> "MISSION BRIEFING" is the
mission-select lever (internal string ANOTHER MISSION), one DOWN from top.

This probe (ONE process, ONE boot, fresh boot for reproducibility):
  boot -> 4800f -> START(60) -> 900f -> PNG menu_dn0 + save_state("menu")
  for k in 0..5:  load "menu"; k x (DOWN 30f + settle 90f); settle 240f
      -> PNG menu_dn{k}; record cursor-struct words 0x957D8..0x957F8 (u32)
         and full-RAM diff vs k=0
  then: load "menu"; DOWN x1 (MISSION BRIEFING); PNG; CROSS -> 600f
      -> PNG (expect OK? dialog); save "am_dialog";
      CROSS (YES) -> 1200f -> PNG am_next.png; save "am_next"; words()
Evidence: scratch/r19t2_msx/
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

EVID = "/home/z/my-project/ps1ai/scratch/r19t2_msx"
CUE = "/home/z/my-project/emu/game/Metal Slug X (USA).cue"
WS = "/home/z/my-project/emu/ws_r19t2"
CUR_LO, CUR_HI = 0x957D8, 0x957F8          # r17-pinned menu cursor struct
PLAYER_X = 0x0CA2E0
PLAYER_HP = 0x0CA2F6
A_SCORE = 0x0EE318
FLAGS = 0x0EE518                            # u32: 0xFF game active (issue5)


def log(*a):
    print("[r19t2-menu]", *a, file=sys.stderr, flush=True)


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
    return {"states": int(m.u8(0x95A7D)), "flags": int(m.u32(FLAGS)),
            "px": px / 65536.0, "php": int(m.u16(PLAYER_HP)),
            "score": int(m.u32(A_SCORE))}


def cursor_words(r):
    return [int.from_bytes(r[a:a + 4], "little")
            for a in range(CUR_LO, CUR_HI + 1, 4)]


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime()),
           "cue": CUE, "ws": WS}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    # ---- proven ladder to the main menu ----
    p.core.run(4800, set())
    p.core.run(60, {"START"})
    p.core.run(900, set())
    p.save_state("menu")
    snap(p, "menu_dn0.png")
    out["menu_words"] = words(p)
    log("menu:", out["menu_words"])

    # ---- DOWN census: k presses, cursor struct + PNG per position ----
    base = None
    census = {}
    for k in range(6):
        p.load_state("menu")
        p.core.run(120, set())
        for _ in range(k):
            p.core.run(30, {"DOWN"})
            p.core.run(90, set())
        p.core.run(240, set())
        snap(p, f"menu_dn{k}.png")
        r = ram(p)
        if k == 0:
            base = r
        full = int(np.count_nonzero(r != base))
        cw = cursor_words(r)
        nz = [f"{hex(CUR_LO + 4 * i)}={v}" for i, v in enumerate(cw) if v]
        census[f"dn{k}"] = {"full_ram_diff_bytes": full, "cursor_nonzero": nz}
        log(f"dn{k}: full={full} cursor={nz[:8]}")
    out["census"] = census

    # ---- enter MISSION BRIEFING (DOWN once from top) ----
    p.load_state("menu")
    p.core.run(120, set())
    p.core.run(30, {"DOWN"})
    p.core.run(240, set())
    snap(p, "mission_briefing_cursor.png")
    p.core.run(60, {"B"})
    p.core.run(600, set())
    snap(p, "mb_after_cross.png")
    p.save_state("mb_dialog")
    out["mb_after_cross_words"] = words(p)
    log("mb after CROSS:", out["mb_after_cross_words"])
    p.core.run(60, {"B"})           # OK? -> YES
    p.core.run(1200, set())
    snap(p, "mb_next.png")
    p.save_state("mb_next")
    out["mb_next_words"] = words(p)
    log("mb next:", out["mb_next_words"])

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu_probe_report.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
