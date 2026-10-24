#!/usr/bin/env python3
"""boot_test_psx_smallgames.py — boot + input-causality probe for the
two small retail games fetched from the owner-supplied source (Task:
"test the other small games too"). One game per PROCESS (H5: a second
in-process boot returns stale state).

Usage: python boot_test_psx_smallgames.py <gid> <cue>
Evidence: /home/z/my-project/emu/games_psx/evidence/<gid>_*/
Local only — the disc images are never committed.
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)

from ps1play.api import PS1Play                                  # noqa
from ps1play.core.inputmap import parse_buttons                  # noqa

EVID = "/home/z/my-project/emu/games_psx/evidence"
os.makedirs(EVID, exist_ok=True)


def frame_diff(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        from PIL import Image
        b = np.array(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def mirrors(mem):
    snap = bytes(mem.snapshot())
    return {"run_of_ff16": snap.count(b"\xff" * 16),
            "pad_id41_ok": snap.count(b"\x00\x41\xff\xff")}


def main():
    gid, cue = sys.argv[1], sys.argv[2]
    out = {"game": gid, "cue": cue, "started": time.strftime("%H:%M:%S")}
    try:
        p = PS1Play(cue, workspace=f"/home/z/my-project/emu/games_psx/ws_{gid}")
        info = p.boot()
        out["boot"] = {k: info.get(k) for k in
                       ("plugin", "ram_bytes", "booted", "boot_exe",
                        "serial", "firmware_mode", "title") if k in info}
        p.wait(420)
        # Adaptive settle: the game finishes kernel/pad init at wildly
        # different times per disc (fast core => hundreds of frames).
        # Wait until the pad driver mirror is live, then give the title
        # screen time to render (H5-conservative, one process per game).
        for _ in range(60):                      # up to ~60x30f = 30 s
            if mirrors(p.mem)["pad_id41_ok"] > 0:
                break
            p.wait(30)
        p.wait(120)                              # title render tail
        base = p.core.frame_rgb()
        out["mirrors"] = mirrors(p.mem)
        shots = {}
        for label, btns in (("start", {"START"}), ("x", {"X"}),
                            ("left", {"LEFT"})):
            p.core.run(120, btns)
            shots[label] = p.core.frame_rgb()
        out["diffs_vs_settle"] = {k: frame_diff(base, v)
                                  for k, v in shots.items()}
        out["mirrors_after_input"] = mirrors(p.mem)
        if base is not None:
            from PIL import Image
            Image.fromarray(base).save(f"{EVID}/{gid}_settle.png")
            for k, v in shots.items():
                if v is not None:
                    from PIL import Image
                    Image.fromarray(v).save(f"{EVID}/{gid}_{k}.png")
            out["screenshots_saved"] = True
        try:
            p.core.close()
        except Exception:
            pass
        out["verdict"] = "BOOTED"
    except Exception:
        import traceback
        out["error"] = traceback.format_exc()[-600:]
        out["verdict"] = "ERROR"
    out["finished"] = time.strftime("%H:%M:%S")
    rdir = os.path.join(EVID, f"{gid}_boot")
    os.makedirs(rdir, exist_ok=True)
    with open(os.path.join(rdir, "report.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(out, indent=1, default=str)[:1500])


if __name__ == "__main__":
    main()
