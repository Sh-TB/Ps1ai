#!/usr/bin/env python3
"""Visualize the blind-navigation problem: PNG after each START tap."""
import sys
sys.path.insert(0, "/home/z/my-project")
from ps1play.api import PS1Play  # noqa: E402
from PIL import Image

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
p = PS1Play(GAME)
print("boot:", p.boot())
p.run_steps(p.plugin.boot_script())
print("t after boot script:", p.t)
for i in range(14):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(f"/tmp/tap_{i:02d}_before.png")
    p.core.run(15, {"START"})
    p.core.run(285)
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(f"/tmp/tap_{i:02d}_after.png")
    pr = p.disc.correlate("RIGHT", window=30, reps=1) if hasattr(p.disc, 'x') else None
    probe = p.disc.correlate("RIGHT", window=30, reps=2)
    top = probe[0] if probe else None
    print(f"tap {i}: top={top}")
    if top and top["dir"] == "+" and top["score"] >= 8:
        print("IN GAME at tap", i)
        rgb = p.core.frame_rgb()
        Image.fromarray(rgb).save("/tmp/tap_in_game.png")
        break
p.core.shutdown()
