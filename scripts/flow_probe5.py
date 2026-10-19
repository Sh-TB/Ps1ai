#!/usr/bin/env python3
"""flow_probe5.py — ISOLATION TEST: identical to flow_probe3 but WITHOUT
the retro_set_controller_port_device call. If the menu now appears at
~3400 like Task-2, the controller-device call was shifting the boot."""
import os
import sys

sys.path.insert(0, "/home/z/my-project")
from PIL import Image
from ps1play.core.host import LibretroCore
from ps1play.api import DEFAULT_WORKSPACE
import ps1play.api as api
from ps1play.plugins.base import detect_plugin, parse_serial

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
OUT = "/tmp/flow5"
os.makedirs(OUT, exist_ok=True)

# monkey-patch: disable the controller port call
orig = LibretroCore.load_game


def load_game_no_pad(self, path):
    import ctypes as _c
    from ps1play.core.host import retro_game_info, _av_info
    gi = retro_game_info()
    gi.path = os.fsencode(os.path.abspath(path))
    ok = self.lib.retro_load_game(_c.byref(gi))
    if not ok:
        raise RuntimeError("load failed")
    av = _av_info()
    self.lib.retro_get_system_av_info(_c.byref(av))
    self.av_info = {"w": av.geometry.base_width, "h": av.geometry.base_height,
                    "fps": av.timing.fps, "audio": av.timing.sample_rate}
    # *** NO retro_set_controller_port_device ***
    self._map_memories()
    return self.av_info


LibretroCore.load_game = load_game_no_pad

p = api.PS1Play(GAME)
p.boot()


def snap(t):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).resize((320, 240)).save(f"{OUT}/t{t:06d}.png")


p.core.run(1000, set())
p._advance()
for _t in range(1000, 5300, 300):
    p.core.run(15, {"START"})
    p.core.run(285, set())
    p._advance()
    if _t >= 3000:
        snap(_t + 300)
for t in range(5450, 8000, 250):
    snap(t)
    p.core.run(250, set())
    p._advance()
print("done ->", OUT)
