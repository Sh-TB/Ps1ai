#!/usr/bin/env python3
"""oldgames_r18_probe.py — Track C: boot + input census for air_hockey, ballistic.

Round-16 ingested both discs (route 1 direct boot); air_hockey's old PNG was
blank, so this re-probe gathers fresh evidence in one pass per game:
  boot -> 900f settle -> PNG
  census: none / START / LEFT / RIGHT / CROSS (200f each, fresh restore)
  verdict BOOTED+INPUT_RESPONSIVE iff any input changes RAM decisively.
No gameplay claims beyond the census.
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

EVID = "/home/z/my-project/emu/games_small/play_evidence/r18_probe"
GAMES = {
    "air_hockey": "/home/z/my-project/emu/games_small/extracted/air_hockey/Air Hockey (USA).cue",
    "ballistic": "/home/z/my-project/emu/games_small/extracted/ballistic/Ballistic [U] [SLUS-00966]/Ballistic [U] [SLUS-00966].cue",
}
RAMSZ = 2 * 1024 * 1024


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def ram(p):
    return np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()


def census(p, name):
    p.core.run(120, set())
    ck = os.path.join(EVID, f"{name}_census.ckpt")
    p.save_state(ck)
    base_png = snap(p, f"{name}_census_base.png")
    out = {"size": list(base_png.shape[:2]) if base_png is not None else None}
    res = {}
    for label, btns in (("none", set()), ("start", {"START"}), ("left", {"LEFT"}),
                        ("right", {"RIGHT"}), ("cross", {"B"})):
        p.load_state(ck)
        p.core.run(200, btns)
        res[label] = ram(p)
        snap(p, f"{name}_{label}.png")
    out["diffs"] = {k: int((v[:RAMSZ] != res["none"][:RAMSZ]).sum())
                    for k, v in res.items() if k != "none"}
    resp = {k: v for k, v in out["diffs"].items() if v > 400}
    out["input_responsive"] = bool(resp)
    out["responsive_buttons"] = sorted(resp)
    return out


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    for name, cue in GAMES.items():
        if not os.path.exists(cue):
            out[name] = {"error": f"cue missing: {cue}"}
            continue
        try:
            p = PS1Play(cue, workspace=os.path.join(EVID, f"ws_{name}"))
            p.boot()
            p.wait(120)
            p.core.run(780, set())
            snap(p, f"{name}_boot.png")
            out[name] = census(p, name)
            out[name]["cue"] = cue
        except Exception as e:      # noqa
            out[name] = {"error": repr(e)[:300]}
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "probe.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
