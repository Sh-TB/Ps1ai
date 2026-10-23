#!/usr/bin/env python3
"""boot_watch_smallgames.py — longer boot watch for the small retail
games: screenshot every 60f up to 1500f, report first non-black frame,
then START-press causality once the title is visible. ONE game/process.
Usage: python boot_watch_smallgames.py <gid> <cue>
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)

from ps1play.api import PS1Play                                  # noqa

EVID = "/home/z/my-project/emu/games_psx/evidence"
os.makedirs(EVID, exist_ok=True)


def main():
    gid, cue = sys.argv[1], sys.argv[2]
    out = {"game": gid, "cue": cue}
    p = PS1Play(cue, workspace=f"/home/z/my-project/emu/games_psx/ws_{gid}")
    info = p.boot()
    out["serial"] = info.get("serial")
    from PIL import Image
    first_nonblack = None
    for f in range(0, 1500, 60):
        p.core.run(60, set())
        img = p.core.frame_rgb()
        mean = float(np.array(img).mean()) if img is not None else 0.0
        if mean > 3.0 and first_nonblack is None:
            first_nonblack = f + 60
            Image.fromarray(img).save(f"{EVID}/{gid}_first@{f+60}.png")
    out["first_nonblack_frame"] = first_nonblack
    # once visible: START causality (title -> menu transition?)
    p.core.run(60, set())
    base = p.core.frame_rgb()
    p.core.run(150, {"START"})
    p.core.run(240, set())
    after = p.core.frame_rgb()
    if base is not None and after is not None:
        ba, aa = np.array(base).astype(np.int16), \
            np.array(after).astype(np.int16)
        if ba.shape != aa.shape:            # mode switch (e.g. wide)
            from PIL import Image
            aa2 = Image.fromarray(aa.astype(np.uint8)).resize(
                (ba.shape[1], ba.shape[0]))
            aa = np.array(aa2).astype(np.int16)
        out["start_diff"] = float(np.abs(ba - aa).mean())
        out["mode_switch"] = True
        Image.fromarray(after).save(f"{EVID}/{gid}_after_start.png")
        Image.fromarray(base).save(f"{EVID}/{gid}_title.png")
    try:
        p.core.close()
    except Exception:
        pass
    rdir = os.path.join(EVID, f"{gid}_boot")
    os.makedirs(rdir, exist_ok=True)
    with open(os.path.join(rdir, "watch.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
