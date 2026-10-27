#!/usr/bin/env python3
"""poypoy_r18_sample2.py — sample colors from the SAVED v_f1.png (known layout)."""
import numpy as np
from PIL import Image

a = np.asarray(Image.open("/home/z/my-project/emu/games_psx/evidence/poypoy_r18_viscal/v_f1.png"))
print("size", a.shape)
pts = {
    "harry_suit_a": (130, 102), "harry_suit_b": (126, 106), "harry_suit_c": (134, 98),
    "harry_head": (130, 90),
    "orb_next_harry": (75, 122), "orb2": (78, 118),
    "iceblock_upleft": (60, 80),
    "p2_yellow_a": (212, 103), "p2_yellow_b": (216, 98),
    "p3_blond": (333, 98),
    "p4_bird": (390, 128),
    "mountain": (390, 80),
    "ocean_top": (60, 60), "ocean_left": (40, 100),
    "horizon": (470, 66), "sky": (256, 12),
    "floor_mid": (256, 145), "floor_low": (256, 165),
    "hud_1p_heart": (60, 208), "hud_2p_heart": (170, 208), "hud_4p_heart": (425, 208),
}
for k, (x, y) in pts.items():
    print(f"{k:16s} ({x:3d},{y:3d}) RGB={tuple(int(v) for v in a[y, x])}")
