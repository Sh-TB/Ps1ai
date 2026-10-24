#!/usr/bin/env python3
"""poypoy_menu16.py — RAM-differential verdict + player-state mapping.

The screenshot arms are ambiguous (the splash blinks -> template false
negatives; demo matches look identical to real matches). RAM does not
lie:

  real match: LEFT vs RIGHT produce DIFFERENT player-state bytes
              (opposite displacement) and both differ from none
  demo:       input only sets a skip flag; left/right/none RAMs are
              near-identical until the transition

Arms from one savestate (deterministic core):
  none1, none2 (determinism baseline), LEFT 90f, RIGHT 90f
  -> 2 MB RAM snapshots -> numpy byte-diff census.

Outputs: verdict + top differing address ranges (the FIRST entity /
player RAM-mapping candidates for the plugin contract).
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu16"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
M7 = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu7"
F2 = "/home/z/my-project/emu/games_psx/evidence/poypoy_flow2"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu16"
CKPT = os.path.join(WS, "probe.ckpt")


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


def reach_menu_interactive(p, menu_t, splash_t):
    p.wait(480)
    p.core.run(90, {"START"})
    # splash
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
    s1 = None
    t0 = p.core.frames_run
    while p.core.frames_run - t0 < 5000:
        p.core.run(100, set())
        s0 = p.core.frame_rgb()
        if s0 is None or float(np.asarray(s0).mean()) < 25.0:
            continue
        p.core.run(60, set())
        if diff(s0, p.core.frame_rgb()) or 0 < 6.0:
            s1 = s0
            break
    if s1 is None:
        return False
    p.core.run(90, {"START"})
    s2 = None
    t0 = p.core.frames_run
    while p.core.frames_run - t0 < 5000:
        p.core.run(100, set())
        s0 = p.core.frame_rgb()
        if s0 is None or float(np.asarray(s0).mean()) < 25.0:
            continue
        p.core.run(60, set())
        if diff(s0, p.core.frame_rgb()) or 0 < 6.0:
            s2 = s0
            break
    return s2 is not None and (diff(menu_t, s2) or 999) < 15.0


def snap_ram(p):
    return np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()


def ranges(mask, min_run=4):
    """Byte-diff mask -> list of (start, end) runs >= min_run."""
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return []
    runs = []
    s = p = idx[0]
    for i in idx[1:]:
        if i == p + 1:
            p = i
            continue
        if p - s + 1 >= min_run:
            runs.append((int(s), int(p)))
        s = p = i
    if p - s + 1 >= min_run:
        runs.append((int(s), int(p)))
    return runs


def main():
    os.makedirs(EVID, exist_ok=True)
    os.makedirs(WS, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    menu_t = load_base(os.path.join(M7, "m7_04_candidate_menu.png"))
    splash_t = load_base(os.path.join(F2, "f2_45_static.png"))
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    if not reach_menu_interactive(p, menu_t, splash_t):
        out["error"] = "interactive menu not reached"
        _finish(out, p)
        return 2
    p.core.run(20, {"X"})                    # confirm EXHIBITION
    p.core.run(700, set())                   # into the match/wheel
    p.save_state(CKPT)
    out["anchor"] = p.core.frames_run
    snap(p, "m16_anchor.png")
    Image.fromarray(p.core.frame_rgb()).save(
        os.path.join(EVID, "m16_anchor.png"))

    arms = {}
    for name, btns in (("none1", set()), ("none2", set()),
                       ("left", {"LEFT"}), ("right", {"RIGHT"})):
        p.load_state(CKPT)
        p.core.run(90, btns)
        arms[name] = snap_ram(p)
        Image.fromarray(p.core.frame_rgb()).save(
            os.path.join(EVID, f"m16_{name}.png"))

    def census(a, b):
        d = arms[a] != arms[b]
        n = int(d.sum())
        return n, ranges(d)[:12]

    out["census"] = {
        "none1_vs_none2": census("none1", "none2"),
        "left_vs_right": census("left", "right"),
        "left_vs_none1": census("left", "none1"),
        "right_vs_none1": census("right", "none1")}
    c = out["census"]
    det = c["none1_vs_none2"][0]
    lr = c["left_vs_right"][0]
    out["determinism_diff_bytes"] = det
    out["verdict"] = (
        "REAL_MATCH_input_in_RAM" if det < 200 and lr > max(500, 5 * det)
        else "DEMO_or_transition")
    print(json.dumps({k: (v[0], v[1][:4]) for k, v in c.items()},
                     default=str))
    print(json.dumps({"verdict": out["verdict"]}))
    _finish(out, p)
    return 0


def _finish(out, p):
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu16.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
