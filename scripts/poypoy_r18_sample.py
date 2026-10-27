#!/usr/bin/env python3
"""poypoy_r18_sample.py — sample exact RGB at known scene points (512x232)."""
import os
import sys

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
MATCH = os.path.join(WS, "r18_match.ckpt")

p = PS1Play(CUE, workspace=WS)
p.boot()
p.wait(120)
p.load_state(MATCH)
p.core.run(180, set())
img = p.core.frame_rgb()
a = np.asarray(img)
print("size", a.shape)
pts = {
    "harry_suit_torso": (130, 100), "harry_suit2": (127, 108),
    "harry_hair": (128, 88),
    "ocean_top": (60, 60), "ocean_mid": (60, 100), "ocean_horizon": (460, 68),
    "sky": (256, 12),
    "floor_center": (256, 140), "floor_left": (100, 150), "floor_edge": (70, 130),
    "orb_box": (75, 122), "orb_box2": (170, 90),
    "p2_yellow": (215, 103), "p3_blond": (330, 95), "p4_bird": (395, 130),
    "hud_bar": (256, 215), "hud_heart2p": (150, 210),
}
for k, (x, y) in pts.items():
    if y < a.shape[0] and x < a.shape[1]:
        print(f"{k:18s} ({x:3d},{y:3d}) RGB={tuple(int(v) for v in a[y, x])}")
Image.fromarray(img).save("/home/z/my-project/emu/games_psx/evidence/poypoy_r18_viscal/sample_frame.png")
