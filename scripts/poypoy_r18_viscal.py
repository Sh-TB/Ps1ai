#!/usr/bin/env python3
"""poypoy_r18_viscal.py — Round 18: vision mask calibration for the agent.

Pure-vision closed-loop plan (psxBreakout pattern). Needed masks:
  harry   — P1 blue suit (bright saturated blue, distinct from dark ocean)
  orb     — white ice-block orbs (near-pure white, arena area)
  enemy_y — 2P yellow suit
  hud     — heart panels (bottom bar red-pixel count per quarter)
This tool: restore match ckpt, grab N frames 300f apart, save side-by-side
mask overlays + print per-mask pixel counts and centroids so thresholds can
be tuned from real data before the agent runs.
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_r18_viscal"
CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
MATCH = os.path.join(WS, "r18_match.ckpt")

TH = {
    # saturated bright blue: b high, b >> r, g medium
    "harry":   lambda r, g, b: (b > 150) & (b > r + 60) & (b > g + 40) & (r < 120) & (g > 40),
    # near-pure white boxes
    "orb":     lambda r, g, b: (r > 215) & (g > 215) & (b > 215) & (abs(r - b) < 25),
    # yellow suit
    "enemy_y": lambda r, g, b: (r > 180) & (g > 140) & (b < 110) & (r > b + 80),
    # black bird (4P): dark blob in arena area
    "enemy_b": lambda r, g, b: (r < 70) & (g < 70) & (b < 70),
    # hud full-heart red
    "heart":   lambda r, g, b: (r > 150) & (g < 90) & (b < 90),
}


def masks(frame):
    a = np.asarray(frame, dtype=np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return {k: fn(r, g, b) for k, fn in TH.items()}


def stats(m):
    ys, xs = np.nonzero(m)
    if len(xs) < 10:
        return None
    return {"n": int(len(xs)),
            "cx": round(float(xs.mean()), 1), "cy": round(float(ys.mean()), 1)}


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)
    p.load_state(MATCH)

    for i in range(4):
        p.core.run(120 if i else 60, set())
        img = p.core.frame_rgb()
        if img is None:
            continue
        Image.fromarray(img).save(os.path.join(EVID, f"v_f{i}.png"))
        H, W = img.shape[:2]
        ov = np.asarray(img).copy()
        ms = masks(img)
        row = {"frame": i, "size": [W, H]}
        for k, m in ms.items():
            s = stats(m)
            row[k] = s
            if m is not None and m.any():
                ov[m] = [255, 0, 255] if k == "harry" else (
                    [0, 255, 0] if k == "orb" else (
                        [255, 255, 0] if k == "enemy_y" else (
                            [128, 128, 255] if k == "enemy_b" else [255, 0, 0])))
        # HUD band for hearts: bottom 22%
        hud = np.asarray(img, dtype=np.int16)[int(H * 0.78):, :, :]
        r, g, b = hud[..., 0], hud[..., 1], hud[..., 2]
        hm = TH["heart"](r, g, b)
        colprof = hm.sum(axis=0)
        qw = W // 4
        row["hud_heart_px"] = [int(colprof[q * qw:(q + 1) * qw].sum()) for q in range(4)]
        Image.fromarray(ov).save(os.path.join(EVID, f"v_f{i}_ov.png"))
        row["heart_total"] = int(hm.sum())
        out[f"f{i}"] = row
        print(json.dumps(row))

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "viscal.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
