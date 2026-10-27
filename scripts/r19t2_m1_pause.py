#!/usr/bin/env python3
"""r19t2_m1_pause.py — Round 19 T2 step 2: reach live M1, open PAUSE menu.

Findings so far (r19t2):
  main menu = ARCADE MISSION / COMBAT SCHOOL / ART GALLERY / OPTION;
  COMBAT SCHOOL -> OK?YES -> professor "come back when you've seen more
  action" (gated). r18 EXE strings cluster 0x860-0x8c8 = RETRY / MISSION
  SELECT / CONTINUE / MISSION 1..6 -> hypothesis: the PAUSE menu offers
  MISSION SELECT. Probe:
  ladder to M1 spawn (proven r17 chain) -> save "m1_live" -> START(pause)
  -> DOWN census k=0..5 (PNG per k + full-RAM diff + 0x957D8..0x957F8 diff)
  -> hedge: also peek OPTION screen from main menu (OPTION entry) PNG.
ONE process, ONE boot.
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
CUR_LO, CUR_HI = 0x957D8, 0x957F8
PLAYER_X = 0x0CA2E0
PLAYER_HP = 0x0CA2F6
A_SCORE = 0x0EE318
FLAGS = 0x0EE518


def log(*a):
    print("[r19t2-m1pause]", *a, file=sys.stderr, flush=True)


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


def wait_live(p, max_f=6000):
    """poll until player x is a plausible spawn value."""
    best = None
    for _ in range(max_f // 300):
        p.core.run(300, set())
        w = words(p)
        best = w
        if w["px"] > 50:
            return w
    return best


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    # ---- proven ladder: boot -> START -> menu -> ARCADE MISSION -> OK?YES ----
    p.core.run(4800, set())
    p.core.run(60, {"START"})
    p.core.run(900, set())
    p.save_state("menu2")
    p.core.run(60, {"B"})            # CROSS on ARCADE MISSION
    p.core.run(600, set())
    snap(p, "arcade_ok_dialog.png")  # expect OK? YES/NO
    p.core.run(60, {"B"})            # YES
    p.core.run(900, set())
    snap(p, "soldier_select.png")
    p.save_state("soldier")

    # ---- confirm soldier 1 -> OK?YES -> M1 live ----
    p.core.run(60, {"B"})
    p.core.run(600, set())
    snap(p, "soldier_ok_dialog.png")
    p.core.run(60, {"B"})
    w = wait_live(p)
    snap(p, "m1_live.png")
    out["m1_live_words"] = w
    log("M1 live:", w)
    p.save_state("m1_live")

    # ---- PAUSE menu + DOWN census ----
    p.load_state("m1_live")
    p.core.run(120, set())
    p.core.run(60, {"START"})
    p.core.run(600, set())
    snap(p, "pause_k0.png")
    p.save_state("pause")
    out["pause_words"] = words(p)
    log("pause:", out["pause_words"])
    base = ram(p)
    for k in range(1, 6):
        p.load_state("pause")
        p.core.run(60, set())
        for _ in range(k):
            p.core.run(30, {"DOWN"})
            p.core.run(90, set())
        p.core.run(240, set())
        snap(p, f"pause_k{k}.png")
        r = ram(p)
        d = np.count_nonzero(r != base)
        cw = [int.from_bytes(r[a:a + 4], "little")
              for a in range(CUR_LO, CUR_HI + 1, 4)]
        out[f"pause_k{k}"] = {"full_diff": int(d),
                              "cursor": [v for v in cw if v]}
        log(f"pause k={k}: full={d} cursor={[hex(v) if v > 255 else v for v in cw if v]}")

    # ---- unpause check (START again) ----
    p.load_state("pause")
    p.core.run(60, set())
    p.core.run(60, {"START"})
    p.core.run(600, set())
    snap(p, "pause_exit.png")
    out["pause_exit_words"] = words(p)
    log("after START again:", out["pause_exit_words"])

    # ---- hedge: OPTION screen peek ----
    p.load_state("menu2")
    p.core.run(120, set())
    for _ in range(3):
        p.core.run(30, {"DOWN"})
        p.core.run(90, set())
    p.core.run(240, set())
    snap(p, "option_cursor.png")
    p.core.run(60, {"B"})
    p.core.run(600, set())
    snap(p, "option_ok.png")
    p.core.run(60, {"B"})
    p.core.run(900, set())
    snap(p, "option_screen.png")
    out["option_words"] = words(p)

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "m1_pause_report.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
