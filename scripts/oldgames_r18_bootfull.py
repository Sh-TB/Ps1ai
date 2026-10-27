#!/usr/bin/env python3
"""oldgames_r18_bootfull.py — full boot ladder + title-gated census.

Ballistic boots through: Mitchell logo (eO) -> Infogrames publisher screen ->
black CD load -> (title?). The r18_probe census hit the static logo region
(input ignored there -> 0 diffs). This ladder: 11000 frames, PNG every 400f,
auto-detect the first stable non-logo state (3 consecutive identical frames
after frame 6000) and run the input census THERE.

Games: ballistic, air_hockey. Honest per-game verdicts only.
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

EVID = "/home/z/my-project/emu/games_small/play_evidence/r18_bootfull"
GAMES = {
    "ballistic": "/home/z/my-project/emu/games_small/extracted/ballistic/Ballistic [U] [SLUS-00966]/Ballistic [U] [SLUS-00966].cue",
    "air_hockey": "/home/z/my-project/emu/games_small/extracted/air_hockey/Air Hockey (USA).cue",
}
RAMSZ = 2 * 1024 * 1024


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def ram(p):
    return np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()


def gray(img):
    arr = img if isinstance(img, np.ndarray) else np.asarray(img)
    return np.asarray(Image.fromarray(arr).convert("L").resize((160, 120)),
                      dtype=np.int16)


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    for gname, cue in GAMES.items():
        g = {}
        try:
            p = PS1Play(cue, workspace=os.path.join(EVID, f"ws_{gname}"))
            p.boot()
            p.wait(120)
            prev = None
            same_run = 0
            stable_at = None
            ladder = []
            for i in range(28):                    # 28 x 400f = 11200f
                p.core.run(400, set())
                img = p.core.frame_rgb()
                if img is None:
                    continue
                a = gray(img)
                Image.fromarray(img).save(os.path.join(EVID, f"{gname}_f{(i + 1) * 400}.png"))
                d = int(np.abs(a - prev).sum()) if prev is not None else -1
                ladder.append({"f": (i + 1) * 400, "delta": d})
                same_run = same_run + 1 if d == 0 else 0
                if same_run >= 2 and stable_at is None and (i + 1) * 400 > 5600:
                    stable_at = (i + 1) * 400
                    break
                prev = a
            g["ladder_tail"] = ladder[-6:]
            g["stable_at"] = stable_at

            # census at the stable state
            ck = os.path.join(EVID, f"{gname}_stable.ckpt")
            p.save_state(ck)
            base = ram(p)
            res = {"none": None}
            for label, btns in (("start", {"START"}), ("cross", {"B"}),
                                ("left", {"LEFT"}), ("right", {"RIGHT"})):
                p.load_state(ck)
                p.core.run(240, btns)
                res[label] = ram(p)
                snap(p, f"{gname}_c_{label}.png")
            p.load_state(ck)
            p.core.run(240, set())
            res["none"] = ram(p)
            g["census"] = {k: int((v[:RAMSZ] != res["none"][:RAMSZ]).sum())
                           for k, v in res.items() if k != "none"}
            g["responsive"] = sorted(k for k, v in g["census"].items() if v > 400)
        except Exception as e:      # noqa
            g["error"] = repr(e)[:300]
        out[gname] = g
        print(gname, json.dumps(g.get("census", g.get("error"))), g.get("responsive"))
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "bootfull.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
