#!/usr/bin/env python3
"""poypoy_menu4.py — MODE SELECT confirm discovery, redesigned.

Fixes over the lost menu3 attempt:
  1. Confirm is tried in BOTH cursor states (root + DOWN-highlighted
     EXHIBITION) — menu3 pressed buttons with unknown cursor state.
  2. Fixed-baseline diffs (MODE SELECT baseline, title baseline) instead
     of chained prev-diffs; a chain hides a two-step transition.
  3. LONG observation (up to 420f) after each confirm — a CD load fade
     (166 MB disc) cannot land inside menu3's 40f settle.
  4. Title-bounce detection + verified re-navigation, so the suspected
     attract idle-timeout cannot silently poison later trials.

One beetle boot per process (H5 rule). Evidence: JSON + PNGs under
emu/games_psx/evidence/poypoy_menu4/.
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_menu4"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"

OBS = (60, 180, 420)          # observation points after a confirm press


def diff(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        b = np.array(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def save(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def to_mode_select(p, title):
    """Verified path title -> MODE SELECT (plugin boot_script + START)."""
    for _ in range(40):
        if bytes(p.mem.snapshot()).count(b"\x00\x41\xff\xff") > 0:
            break
        p.wait(30)
    p.core.run(90, {"START"})
    p.core.run(90, set())
    p.core.run(60, {"START"})
    p.core.run(240, set())
    ms = save(p, "ms_base.png")
    return ms


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime()), "trials": []}
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_poypoy_menu4")
    p.boot()
    p.wait(420)
    title = save(p, "title_base.png")
    ms = to_mode_select(p, title)

    for btn in ("X", "O", "SQ", "START"):
        # ---- trial A: cursor ROOT (as menu3 presumably did) --------
        for phase, pre in (("root", None), ("down", ("DOWN", 10))):
            p.core.run(30, set())
            base = p.core.frame_rgb()
            if pre:
                p.core.run(pre[1], {pre[0]})
                p.core.run(30, set())
                base = p.core.frame_rgb()   # baseline = highlighted menu
            trial = {"btn": btn, "phase": phase}
            p.core.run(20, {btn})
            max_ms, max_t = 0.0, 0.0
            for i, f in enumerate(OBS):
                p.core.run(OBS[i] - (OBS[i - 1] if i else 0), set())
                img = p.core.frame_rgb()
                d_ms = diff(ms, img)
                d_t = diff(title, img)
                max_ms, max_t = max(max_ms, d_ms or 0), max(max_t, d_t or 0)
                if d_ms and d_ms > 25:
                    save(p, f"m4_{btn}_{phase}_obs{f}.png")
            trial["max_diff_vs_ms"] = round(max_ms, 1)
            trial["max_diff_vs_title"] = round(max_t, 1)
            bounced = max_t is not None and max_t < 12.0
            trial["bounced_to_title"] = bool(bounced)
            # ---- recovery: if we left MODE SELECT, go back ----------
            now = p.core.frame_rgb()
            left = diff(ms, now) is not None and diff(ms, now) > 25
            if left:
                save(p, f"m4_{btn}_{phase}_left.png")
                if bounced:
                    ms = to_mode_select(p, title)
                    trial["recovered"] = True
                else:
                    # screen changed but NOT to title: candidate
                    # TRANSITION — save and stop everything
                    trial["candidate_transition"] = True
                    out["confirm_found"] = {"btn": btn, "phase": phase}
                    out["trials"].append(trial)
                    _finish(out, p)
                    return 0
            out["trials"].append(trial)
            print(json.dumps(trial))
            # restore root cursor for the next phase
            if pre:
                p.core.run(10, {"UP"})
                p.core.run(30, set())
    _finish(out, p)
    return 0


def _finish(out, p):
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu4_probe.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
