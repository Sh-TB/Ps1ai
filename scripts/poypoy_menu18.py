#!/usr/bin/env python3
"""poypoy_menu18.py — X-hold follow-through: does control arrive?

menu17: X-hold (60f) on the interactive menu = a 131K-byte state
transition (20f taps never registered — likely the whole reason every
earlier confirm attempt looked inert). The +700f state ignores
direction keys (left==right), consistent with a match INTRO (wheel /
READY countdown) that hands control to the player later.

This run: menu anchor -> X-hold 60f -> screenshots at
+700/1000/1400/1800/2200 -> direction census at +2200f and +3000f.
REAL_MATCH at either census = the agent is playing Poy Poy.
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu18"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
M7 = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu7"
F2 = "/home/z/my-project/emu/games_psx/evidence/poypoy_flow2"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu18"
MENU_CKPT = os.path.join(WS, "menu_anchor.ckpt")


def diff(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        b = np.array(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def load_base(path):
    try:
        return np.array(Image.open(path).convert("RGB"))
    except Exception:
        return None


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def snap_ram(p):
    return np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()


def try_gate(p, menu_t, splash_t):
    t0 = p.core.frames_run
    while p.core.frames_run - t0 < 12000:
        img = p.core.frame_rgb()
        if img is not None and float(np.asarray(img).mean()) >= 25.0:
            if (diff(splash_t, img) or 999) < 15.0:
                break
        p.core.run(100, set())
    else:
        return False
    p.core.run(90, {"START"})
    for _ in range(2):
        s = None
        t0 = p.core.frames_run
        while p.core.frames_run - t0 < 5000:
            p.core.run(100, set())
            s0 = p.core.frame_rgb()
            if s0 is None or float(np.asarray(s0).mean()) < 25.0:
                continue
            p.core.run(60, set())
            if diff(s0, p.core.frame_rgb()) or 0 < 6.0:
                s = s0
                break
        if s is None:
            return False
        if (diff(menu_t, s) or 999) < 15.0:
            return True
        p.core.run(90, {"START"})
    return False


def census(p, ck):
    arms = {}
    for name, btns in (("none1", set()), ("none2", set()),
                       ("left", {"LEFT"}), ("right", {"RIGHT"})):
        p.load_state(ck)
        p.core.run(90, btns)
        arms[name] = snap_ram(p)

    def n(a, b):
        return int((arms[a] != arms[b]).sum())

    det, lr, ln = n("none1", "none2"), n("left", "right"), \
        n("left", "none1")
    return {"det": det, "left_vs_right": lr, "left_vs_none": ln,
            "verdict": ("REAL_MATCH" if det < 200 and
                        lr > max(500, 5 * det) else "not_yet")}


def main():
    os.makedirs(EVID, exist_ok=True)
    os.makedirs(WS, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    menu_t = load_base(os.path.join(M7, "m7_04_candidate_menu.png"))
    splash_t = load_base(os.path.join(F2, "f2_45_static.png"))
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(480)
    p.core.run(90, {"START"})
    ok = False
    for attempt in range(4):
        if try_gate(p, menu_t, splash_t):
            ok = True
            break
    if not ok:
        out["error"] = "gate failed"
        _finish(out, p)
        return 2
    p.save_state(MENU_CKPT)
    out["menu_anchor"] = p.core.frames_run
    p.core.run(30, set())
    p.core.run(60, {"X"})                    # the SUSTAINED confirm
    for f in (700, 1000, 1400, 1800, 2200):
        while p.core.frames_run - out["menu_anchor"] < f:
            p.core.run(50, set())
        snap(p, f"m18_f{f}.png")
    for f in (2200, 3000):
        ck = os.path.join(WS, f"late{f}.ckpt")
        # rewind to the anchor, re-walk, save at f, census
        p.load_state(MENU_CKPT)
        p.core.run(90, {"X"})
        while p.core.frames_run - out["menu_anchor"] < f:
            p.core.run(50, set())
        p.save_state(ck)
        res = census(p, ck)
        out[f"census_f{f}"] = res
        print(json.dumps({f"census_f{f}": res}))
        if res["verdict"] == "REAL_MATCH":
            out["confirm_button"] = "X-hold-60f"
            out["playing"] = True
            break
    _finish(out, p)
    return 0


def _finish(out, p):
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu18.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
