#!/usr/bin/env python3
"""poypoy_menu5.py — MODE SELECT confirm, beat-the-clock edition.

menu4 findings driving this redesign:
  - X at MODE SELECT root did nothing within 180f (no item
    highlighted) and the ATTRACT DEMO started 180-420f later (its
    screenshot is now a classification baseline).
  - => the lost menu3 probe tested its late buttons INSIDE the demo:
    "no forward transition" conclusions for O/X are void.

Protocol per candidate button (X, O, SQ, START):
  1. FAST path to MODE SELECT: poll for menu arrival (diff vs
     ms_base < 15) instead of fixed 240f idle, then act immediately.
  2. DOWN-highlight EXHIBITION (record cursor-move diff), press the
     candidate, observe 90/240/480f vs fixed baselines (ms, demo,
     title).
  3. Classify: transition (diff vs ms > 25, not demo/title) |
     demo-hit (diff vs demo < 12) | no-effect. Demo-hit -> wait for
     the attract loop to return to title, re-navigate, retry.
One beetle boot per process (H5).
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu5"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
M4 = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu4"

OBS = (90, 240, 480)


def diff(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        b = np.array(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def snap(p, name=None):
    img = p.core.frame_rgb()
    if img is not None and name:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def load_base(path):
    try:
        return np.array(Image.open(path).convert("RGB"))
    except Exception:
        return None


def poll_menu(p, ms, limit=600):
    """Poll until the screen matches the MODE SELECT baseline."""
    for _ in range(limit // 15):
        if diff(ms, p.core.frame_rgb()) is not None and \
                diff(ms, p.core.frame_rgb()) < 15.0:
            return True
        p.core.run(15, set())
    return False


def wait_title(p, title, limit=4500):
    for _ in range(limit // 30):
        d = diff(title, p.core.frame_rgb())
        if d is not None and d < 12.0:
            return True
        p.core.run(30, set())
    return False


def goto_ms(p, ms):
    p.core.run(90, {"START"})
    p.core.run(30, set())
    p.core.run(60, {"START"})
    return poll_menu(p, ms)


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime()),
           "trials": [], "boot_frames": None}
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_poypoy_menu5")
    p.boot()
    p.wait(420)
    title = snap(p, "title_base.png")
    # verified menu path once to get the pristine ms_base
    p.core.run(90, {"START"})
    p.core.run(30, set())
    p.core.run(60, {"START"})
    p.core.run(240, set())
    ms = snap(p, "ms_base.png")
    demo = load_base(os.path.join(M4, "m4_X_root_obs420.png"))
    out["boot_frames"] = p.core.frames_run

    pending = ["X", "O", "SQ", "START"]
    tries_left = 8                    # hard cap on menu re-entries
    while pending and tries_left > 0:
        tries_left -= 1
        btn = pending[0]
        if not poll_menu(p, ms, limit=300):
            out["trials"].append({"btn": btn, "error": "no mode-select"})
            break
        row = {"btn": btn, "frame": p.core.frames_run}
        pre = p.core.frame_rgb()
        p.core.run(10, {"DOWN"})
        p.core.run(20, set())
        row["cursor_move_diff"] = round(diff(pre, p.core.frame_rgb()) or 0, 2)
        p.core.run(20, {btn})
        d_ms = d_dm = d_t = 0.0
        for i, f in enumerate(OBS):
            p.core.run(OBS[i] - (OBS[i - 1] if i else 0), set())
            img = p.core.frame_rgb()
            d_ms = max(d_ms, diff(ms, img) or 0)
            d_dm = max(d_dm, diff(demo, img) or 0) if demo is not None else 0
            d_t = max(d_t, diff(title, img) or 0)
        row.update({"max_vs_ms": round(d_ms, 1),
                    "max_vs_demo": round(d_dm, 1),
                    "max_vs_title": round(d_t, 1)})
        if d_ms > 25 and d_dm > 15 and d_t > 15:
            row["verdict"] = "TRANSITION"
            snap(p, f"m5_{btn}_transition.png")
            out["confirm_found"] = row
            out["trials"].append(row)
            print(json.dumps(row))
            break
        if d_dm < 12:
            row["verdict"] = "demo_hit"
            # wait for the attract loop to come back to title
            back = wait_title(p, title)
            row["title_returned"] = bool(back)
            if back:
                p.core.run(60, set())
            # btn NOT consumed (untested inside the menu) — keep pending
        else:
            row["verdict"] = "no_effect"
            pending.pop(0)            # tested inside the menu: consumed
            p.core.run(10, {"UP"})    # restore root cursor
            p.core.run(30, set())
        out["trials"].append(row)
        print(json.dumps(row))

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu5_probe.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
