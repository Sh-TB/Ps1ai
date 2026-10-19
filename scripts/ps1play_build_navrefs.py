#!/usr/bin/env python3
"""Build labeled navigation references from captured screenshots (once)."""
import os
import shutil

SRC = "/home/z/my-project/download/ps1play_v2"
DST = "/home/z/my-project/ps1play/profiles/nav_refs/metal_slug_x"
os.makedirs(DST, exist_ok=True)

pairs = [
    # (source png, state label, tag)
    ("nav/01_after_bootscript.png", "title", "go"),
    ("nav/02_menu.png", "title", "attract1"),
    ("nav/05_cross.png", "demo", "m1a"),
    ("nav/06_circle.png", "demo", "m1b"),
    ("nav/07_start.png", "demo", "m1c"),
    ("nav/08_down_cross.png", "demo", "m1d"),
    ("fail6_small.png", "menu", "no_dialog"),
    ("verify_gameplay_start.png", "dialog", "ok_yes"),
    ("nav/10_run.png", "loading", "now_loading"),
    ("diag_stage1_start.png", "loading", "black"),
]
for src, state, tag in pairs:
    p = os.path.join(SRC, src)
    if not os.path.exists(p):
        print("MISSING:", p)
        continue
    shutil.copy(p, os.path.join(DST, f"{state}__{tag}.png"))
    print("ref:", state, tag)
print("done ->", DST)
