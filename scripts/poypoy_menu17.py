#!/usr/bin/env python3
"""poypoy_menu17.py — confirm-finder via RAM census from ONE menu anchor.

menu16's gate was flaky; fix: retry the gate up to 3x inside one boot
(the splash recurs in the attract cycle), then SAVE THE MENU ANCHOR.
Every candidate confirm is tested FROM THE SAME ANCHOR (reload between
candidates — the core is deterministic, none-arms are the baseline):

  candidates: START | X (hold 60f) | O
  per candidate: press -> 700f -> save sub-state -> arms LEFT/RIGHT/
  none (90f) -> RAM census

Verdict per candidate: left_vs_right byte-diff >> determinism baseline
=> input reaches the match => that candidate CONFIRMED the exhibition.

This is the last Poy Poy discovery run of the session (time budget);
whatever the outcome, the plugin + worklog get the honest status.
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu17"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
M7 = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu7"
F2 = "/home/z/my-project/emu/games_psx/evidence/poypoy_flow2"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu17"
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
    """One gate attempt: wait for splash, double-START, menu check."""
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
        # poll static non-black
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
            return True               # menu reached (1 or 2 STARTs)
        p.core.run(90, {"START"})
    return False


def census_arms(p, tag):
    """From the CURRENT state: 700f, save, LEFT/RIGHT/none arms."""
    p.core.run(700, set())
    ck = os.path.join(WS, f"probe_{tag}.ckpt")
    p.save_state(ck)
    snap(p, f"m17_{tag}_field.png")
    arms = {}
    for name, btns in (("none1", set()), ("none2", set()),
                       ("left", {"LEFT"}), ("right", {"RIGHT"})):
        p.load_state(ck)
        p.core.run(90, btns)
        arms[name] = snap_ram(p)

    def n_diff(a, b):
        return int((arms[a] != arms[b]).sum())

    det = n_diff("none1", "none2")
    lr = n_diff("left", "right")
    ln = n_diff("left", "none1")
    return {"det": det, "left_vs_right": lr, "left_vs_none": ln,
            "verdict": ("REAL_MATCH" if det < 200 and
                        lr > max(500, 5 * det) else "DEMO_or_transition")}


def main():
    os.makedirs(EVID, exist_ok=True)
    os.makedirs(WS, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime()),
           "candidates": {}}
    menu_t = load_base(os.path.join(M7, "m7_04_candidate_menu.png"))
    splash_t = load_base(os.path.join(F2, "f2_45_static.png"))
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(480)
    p.core.run(90, {"START"})
    ok = False
    for attempt in range(3):
        if try_gate(p, menu_t, splash_t):
            ok = True
            break
        out.setdefault("gate_attempts", []).append(attempt)
    if not ok:
        out["error"] = "interactive menu not reached (3 attempts)"
        _finish(out, p)
        return 2
    snap(p, "m17_menu.png")
    p.save_state(MENU_CKPT)
    out["menu_anchor"] = p.core.frames_run
    print(json.dumps({"menu_anchor": out["menu_anchor"]}))

    for tag, press in (("start", ("START", 20)), ("xhold", ("X", 60)),
                       ("o", ("O", 20))):
        p.load_state(MENU_CKPT)
        p.core.run(30, set())
        btn, hold = press
        p.core.run(hold, {btn})
        res = census_arms(p, tag)
        out["candidates"][tag] = res
        print(json.dumps({tag: res}))
        if res["verdict"] == "REAL_MATCH":
            out["confirm_button"] = btn
            break
    _finish(out, p)
    return 0


def _finish(out, p):
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu17.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
