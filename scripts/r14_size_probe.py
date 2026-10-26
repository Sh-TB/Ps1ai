#!/usr/bin/env python3
"""r14_size_probe.py — ONE boot of one image; verdict: did the shell
actually LOAD the exe body (and does the game run)?

Verdict facts:
  * body_at_taddr: exe body first 32 bytes present at 0x80010000
  * nonzero_bytes in the text window beyond the original 14-sector body
    (proves the PADDED region arrived too, not just the first sectors)
  * screen class via hellopong_r12_lib.classify after settle
  * padbuff signature (game's pad driver alive)
Writes scratch/round14_sizecliff/<tag>.json. One boot per process.
"""
import json
import os
import shutil
import sys

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                          # noqa: E402
from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                             # noqa: E402
from hellopong_r12_lib import classify, padbuff_addrs       # noqa: E402

EMU = "/home/z/my-project/emu/games_homebrew"
OUT = os.path.join(REPO, "scratch", "round14_sizecliff")
EXE = open(os.path.join(EMU, "hellopong_exe.extracted"), "rb").read()
BODY0 = EXE[0x800:0x800 + 32]


def probe(cue, tag):
    ws = os.path.join(EMU, f"ws_r14_sc_{tag}")
    os.makedirs(os.path.join(ws, "system"), exist_ok=True)
    shutil.copyfile(os.path.join(REPO, "third_party", "openbios",
                                 "openbios.bin"),
                    os.path.join(ws, "system", "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=ws)
    p = PS1Play(cue, workspace=ws, var_overrides=fw["override_vars"])
    p.boot()
    p.wait(1500)
    snap = bytes(p.mem.snapshot())
    fr = p.core.frame_rgb()
    cls, facts = classify(fr, 0.0)
    body_match = snap[0x10000:0x10020] == BODY0
    # how far did the load reach? count nonzero 2KB-blocks in 0x80010000..+0x14000
    reach = 0
    for blk in range(0, 0x14000, 0x800):
        w = snap[0x10000 + blk:0x10000 + blk + 0x800]
        if any(w):
            reach = blk + 0x800
    pads = padbuff_addrs(snap)
    from PIL import Image
    Image.fromarray(fr).save(os.path.join(OUT, f"{tag}_f{p.core.frames_run}.png"))
    out = {"tag": tag, "cue": cue, "frames": p.core.frames_run,
           "body_at_taddr": bool(body_match), "load_reach_bytes": reach,
           "screen_class": cls, "frame_mean": facts.get("frame_mean"),
           "padbuffs": len(pads),
           "verdict": "BOOTED" if (body_match and cls in
                                   ("PLAYING", "MENU", "GAME_OVER")
                                   and pads) else "DEAD"}
    with open(os.path.join(OUT, f"{tag}.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out), flush=True)
    p.shutdown() if hasattr(p, "shutdown") else None


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    probe(sys.argv[1], sys.argv[2])
