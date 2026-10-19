#!/usr/bin/env python3
"""flow_probe9.py — isolate the core.reset() effect: same taps+B+START
sequence, WITH and WITHOUT reset. Also check RAM churn on the dialog."""
import os
import sys

sys.path.insert(0, "/home/z/my-project")
import numpy as np
from PIL import Image
from ps1play.api import PS1Play
from ps1play.core.memory import digest

OUT = "/tmp/flow9"
os.makedirs(OUT, exist_ok=True)
GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
MODE = sys.argv[1] if len(sys.argv) > 1 else "noreset"

p = PS1Play(GAME)
p.boot()
if MODE == "reset":
    p.core.reset()
    print("core.reset() done")


def snap(tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).resize((320, 240)).save(f"{OUT}/{MODE}_{tag}.png")


p.core.run(1000, set())
p._advance()
for _t in range(1000, 5300, 300):
    p.core.run(15, {"START"})
    p.core.run(285, set())
    p._advance()
p.core.run(15, {"B"})
p.core.run(600, set())
p._advance()
snap("1_dialog")
d0 = digest(p.mem.snapshot())
# churn idle 60f
s0 = p.mem.snapshot()
p.core.run(60, set())
churn_idle = int(np.count_nonzero(s0 != p.mem.snapshot()))
p._advance()
# START press + churn
p.core.run(15, {"START"})
p.core.run(150, set())
p._advance()
d1 = digest(p.mem.snapshot())
snap("2_after_start")
print(f"[{MODE}] churn_idle60={churn_idle} digest_changed={d0 != d1}")
