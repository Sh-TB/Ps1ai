#!/usr/bin/env python3
"""poypoy_flow1.py — map the EXHIBITION flow from MODE SELECT to the arena.

menu5 established: MODE SELECT + DOWN (highlight EXHIBITION) + X ->
transition (Konami logo load screen). This runner walks the flow:
poll for screen changes, X-confirm defaults, log every distinct screen
with a screenshot; when the arena renders (big 3D field), run an input
causality sweep (LEFT/RIGHT/X/SQ/O) for the battle controls.

One beetle boot per process (H5). Evidence: poypoy_flow1/*.png + JSON.
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_flow1"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"


def diff(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        b = np.array(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def wait_change(p, base, limit, min_d=18.0, poll=15):
    """Poll until the screen differs from `base` by > min_d."""
    acc = 0
    while acc < limit:
        if diff(base, p.core.frame_rgb()) or 0 > min_d:
            return True
        p.core.run(poll, set())
        acc += poll
    return False


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"steps": [], "started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_poypoy_flow1")
    p.boot()
    p.wait(420)
    # title -> MODE SELECT (verified), then the CONFIRMED entry
    p.core.run(90, {"START"})
    p.core.run(30, set())
    p.core.run(60, {"START"})
    p.core.run(240, set())
    ms = p.core.frame_rgb()
    p.core.run(10, {"DOWN"})
    p.core.run(20, set())
    p.core.run(20, {"X"})
    out["steps"].append({"step": 0, "event": "mode_select_down_X",
                         "frame": p.core.frames_run})

    prev = ms
    step = 1
    arena = None
    while step < 25:
        changed = wait_change(p, prev, limit=900)
        if not changed:
            out["steps"].append({"step": step, "event": "no_change_900f"})
            break
        p.core.run(60, set())            # let the screen settle
        img = snap(p, f"flow_{step:02d}.png")
        row = {"step": step, "frame": p.core.frames_run,
               "diff_prev": round(diff(prev, img) or 0, 1)}
        # title bounce check happens implicitly: title is a distinct
        # screen; log everything, classify after the run
        out["steps"].append(row)
        print(json.dumps(row))
        prev = img
        step += 1
        # arena heuristic: a settled screen that then stays stable for
        # 300f while being a NEW screen after >=2 transitions past the
        # logo — try the input sweep there
        if step >= 4:
            p.core.run(300, set())
            if diff(img, p.core.frame_rgb()) or 0 < 6.0:
                stable_for = 300
                row2 = {"step": step, "event": "stable_300f",
                        "frame": p.core.frames_run}
                out["steps"].append(row2)
                print(json.dumps(row2))
                arena = img
                break

    if arena is not None:
        # ---- battle input causality sweep ---------------------------
        sweep = []
        for btn in ("LEFT", "RIGHT", "X", "SQ", "O", "UP"):
            p.core.run(24, {btn})
            p.core.run(60, set())
            img = p.core.frame_rgb()
            d = diff(arena, img)
            sweep.append({"btn": btn, "diff": round(d or 0, 1)})
            if d and d > 8.0:
                snap(p, f"sweep_{btn}.png")
            p.core.run(30, set())
        out["input_sweep"] = sweep
        out["arena_reached"] = True
        print(json.dumps({"input_sweep": sweep}))
    else:
        out["arena_reached"] = False

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "flow1.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
