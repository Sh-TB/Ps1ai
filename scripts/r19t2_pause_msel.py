#!/usr/bin/env python3
"""r19t2_pause_msel.py — Round 19 T2 step 3: pause-menu MISSION SELECT experiment.

Static evidence (r19t2, capstone on SLUS_012.12):
  - string table VA 0x80082d18: ["PAUSE","    "] / [RETRY,EXIT,CONTINUE] /
    [RETRY,"MISSION SELECT",EXIT] / [MISSION 6..MISSION 1] / [RETRY,EXIT,CONTINUE] / [EXIT]
  - menu objects array @0x800D4A48 (4 items, +0x26 blink), main-menu cursor u8
    @0x800D4A71 (mod-4 wrap), "MISSION n" submenu cursor u8 @0x800D4A70,
    label string ptr u32 @0x800D4A68, mode word s16 @0x800D4210 (label drawn
    only when >= 2), mission index also read from 0x800DAB3C.
Observed live (r19t2_m1_pause): arcade pause shows only blinking PAUSE.

This probe (ONE boot): ladder to M1 live -> dump the words above ->
pause -> dump again -> poke mode word to 2 (then 3) -> does the pause MENU
appear? -> if yes: navigate to MISSION SELECT, pick MISSION 2 via DOWN,
confirm, poll for M2 spawn (expected px ~76.4 php 120).
Honesty: the mode-word poke is a RAM patch, logged as such; everything else
is pure button input.
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

A_MODE = 0xD4210        # s16 mode word (label gate >= 2)
A_ITEMS = 0xD4A48       # 4 u32 menu object ptrs
A_LABEL = 0xD4A68       # u32 label string ptr (MISSION n)
A_MSEL = 0xD4A70        # u8 mission-select cursor
A_CURSOR = 0xD4A71      # u8 menu cursor (mod 4)
A_MVAR = 0xDAB3C        # mission index source (s16)
MISSION_STR = {0x800100c4: "MISSION 1", 0x800100b8: "MISSION 2",
               0x800100ac: "MISSION 3", 0x800100a0: "MISSION 4",
               0x80010094: "MISSION 5", 0x80010088: "MISSION 6"}
PLAYER_X = 0x0CA2E0
PLAYER_HP = 0x0CA2F6
A_SCORE = 0x0EE318
FLAGS = 0x0EE518


def log(*a):
    print("[r19t2-msel]", *a, file=sys.stderr, flush=True)


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
    return {"states": int(m.u8(0x95A7D)), "flags": int(m.u32(FLAGS)),
            "px": px / 65536.0, "php": int(m.u16(PLAYER_HP)),
            "score": int(m.u32(A_SCORE))}


def dump(p, tag):
    m = p.mem
    d = {"mode": m.u16(A_MODE), "items": [hex(m.u32(A_ITEMS + 4 * i))
                                          for i in range(4)],
         "label": MISSION_STR.get(m.u32(A_LABEL), hex(m.u32(A_LABEL))),
         "msel_cursor": m.u8(A_MSEL), "menu_cursor": m.u8(A_CURSOR),
         "mission_var": m.u16(A_MVAR)}
    log(tag, json.dumps(d))
    return d


def wait_live(p, max_f=6000):
    for _ in range(max_f // 300):
        p.core.run(300, set())
        w = words(p)
        if w["px"] > 50:
            return w
    return words(p)


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)
    try:
        log("ram writeable:", p.mem.ram.flags.writeable)
    except Exception as e:
        log("ram flags err:", e)

    # ---- proven ladder to M1 live ----
    p.core.run(4800, set())
    p.core.run(60, {"START"})
    p.core.run(900, set())
    p.save_state("menu3")
    p.core.run(60, {"B"})
    p.core.run(600, set())
    p.core.run(60, {"B"})
    p.core.run(900, set())
    p.save_state("soldier3")
    p.core.run(60, {"B"})
    p.core.run(600, set())
    p.core.run(60, {"B"})
    w = wait_live(p)
    snap(p, "m1_live2.png")
    out["m1_live"] = w
    log("M1 live:", w)
    p.save_state("m1_live2")
    out["live_dump"] = dump(p, "live:")

    # ---- pause ----
    p.core.run(60, {"START"})
    p.core.run(300, set())
    p.save_state("paused2")
    out["pause_dump"] = dump(p, "pause:")
    snap(p, "pause2.png")

    # ---- poke mode word while paused ----
    for mv in (2, 3, 1):
        p.load_state("paused2")
        p.core.run(60, set())
        try:
            p.mem.ram[A_MODE:A_MODE + 2] = int(mv).to_bytes(2, "little")
        except Exception as e:
            log("poke failed:", e)
            break
        p.core.run(300, set())
        snap(p, f"poke_mode{mv}.png")
        out[f"poke{mv}_dump"] = dump(p, f"mode={mv}:")
        w = words(p)
        # quick interaction test: DOWN then CROSS, watch menu cursor
        p.core.run(30, {"DOWN"})
        p.core.run(120, set())
        out[f"poke{mv}_after_down"] = dump(p, f"mode={mv} after DOWN:")

    # ---- full navigation attempt with best mode (recorded honestly) ----
    # try: pause -> poke mode=2 -> DOWN to cursor==2 -> CROSS -> submenu?
    p.load_state("paused2")
    p.core.run(60, set())
    p.mem.ram[A_MODE:A_MODE + 2] = int(2).to_bytes(2, "little")
    p.core.run(180, set())
    for i in range(4):
        c = p.mem.u8(A_CURSOR)
        log(f"nav: menu_cursor={c}")
        if c == 2:
            break
        p.core.run(30, {"DOWN"})
        p.core.run(90, set())
    snap(p, "msel_cursor_at2.png")
    p.core.run(60, {"B"})
    p.core.run(600, set())
    snap(p, "msel_pressed.png")
    out["after_msel_cross"] = dump(p, "after CROSS on MISSION SELECT:")
    # move mission cursor to 1 (MISSION 2) if needed
    for i in range(2):
        c = p.mem.u8(A_MSEL)
        log(f"msel cursor={c}")
        if c >= 1:
            break
        p.core.run(30, {"DOWN"})
        p.core.run(90, set())
    snap(p, "m2_highlighted.png")
    p.core.run(60, {"B"})
    p.core.run(600, set())
    snap(p, "m2_confirmed.png")
    out["after_m2_cross"] = dump(p, "after CROSS on MISSION 2:")
    w = wait_live(p, 7200)
    snap(p, "after_m2_wait.png")
    out["after_m2_wait_words"] = w
    log("after M2 confirm wait:", w)
    p.save_state("after_m2")

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "pause_msel_report.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
