#!/usr/bin/env python3
"""r14_screens.py — dump screenshots at fixed frames from a boot, to
identify what the shell is actually showing (cube? splash? checker?)."""
import os
import shutil
import sys

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PIL import Image                                       # noqa: E402
from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                             # noqa: E402

EMU = "/home/z/my-project/emu/games_homebrew"
OUT = os.path.join(REPO, "scratch", "round14_breakout")


def shoot(cue, tag, frames=(150, 400, 800, 1400)):
    ws = os.path.join(EMU, f"ws_r14_scr_{tag}")
    os.makedirs(os.path.join(ws, "system"), exist_ok=True)
    shutil.copyfile(os.path.join(REPO, "third_party", "openbios",
                                 "openbios.bin"),
                    os.path.join(ws, "system", "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=ws)
    p = PS1Play(cue, workspace=ws, var_overrides=fw["override_vars"])
    p.boot()
    last = 0
    for f in frames:
        p.wait(f - last)
        last = f
        fr = p.core.frame_rgb()
        Image.fromarray(fr).save(os.path.join(OUT, f"{tag}_f{f}.png"))
        print(tag, f, "mean", round(float(fr.mean()), 2), flush=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    shoot(sys.argv[1], sys.argv[2])
