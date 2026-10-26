#!/usr/bin/env python3
"""r13_diag_cs50x.py — why does the cs50x container black-screen?

ONE boot. After settle: scan RAM for the PS-EXE header signature,
report load state (header found? pc/taddr sane? first instructions?),
kernel exception vectors, and screenshot. Facts only."""
import os
import shutil
import sys

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                          # noqa: E402
from ps1play import labconfig                               # noqa: E402
from ps1play.api import PS1Play                             # noqa: E402

EMU = "/home/z/my-project/emu/games_homebrew"
CUE = os.path.join(EMU, "patched", "v1_nosize.cue")
WS = os.path.join(EMU, "ws_cs50x_diag")
OUT = os.path.join(REPO, "scratch", "round13_newgames", "cs50x_diag")

EXE = open(os.path.join(EMU, "cs50x.exe"), "rb").read()
HDR = EXE[:2048]
DATA0 = EXE[2048:2048 + 32]


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(WS, "system"), exist_ok=True)
    shutil.copyfile(os.path.join(REPO, "third_party", "openbios",
                                 "openbios.bin"),
                    os.path.join(WS, "system", "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=WS)
    p = PS1Play(CUE, workspace=WS, var_overrides=fw["override_vars"])
    boot = p.boot()
    print("boot:", boot, flush=True)
    p.wait(900)
    snap = bytes(p.mem.snapshot())
    fr = p.core.frame_rgb()
    if fr is not None:
        from PIL import Image
        Image.fromarray(fr).save(os.path.join(OUT, "diag_frame.png"))
        print("frame_mean:", float(fr.mean()), flush=True)

    # where did the header land?
    hits = []
    i = snap.find(b"PS-X EXE")
    while i >= 0 and len(hits) < 8:
        hits.append(i)
        i = snap.find(b"PS-X EXE", i + 1)
    print("header hits:", [hex(h) for h in hits], flush=True)
    for h in hits:
        hh = snap[h:h + 0x40]
        pc = int.from_bytes(hh[0x10:0x14], "little")
        ta = int.from_bytes(hh[0x18:0x1C], "little")
        ts = int.from_bytes(hh[0x1C:0x20], "little")
        print(f"  @ {hex(h)}: pc={hex(pc)} taddr={hex(ta)} "
              f"tsize={ts}", flush=True)
        if 0x80000000 <= ta < 0x80200000 and ta + ts <= 0x80200000:
            lo = ta - 0x80000000
            got = snap[lo:lo + 32]
            print("   loaded[0:32]:", got.hex(), flush=True)
            print("   expect     :", DATA0.hex(), flush=True)
            print("   match      :", got == DATA0, flush=True)

    # kernel vectors / current state
    for name, a in (("exc_vector_0x80", 0x80), ("a0_table", 0x200),
                    ("kstack_top", 0x7FFF0)):
        print(f"  {name}: {snap[a:a+16].hex()}", flush=True)

    # RAM-wide: any nonzero activity outside kernel zones?
    body = np.frombuffer(snap[0x10000:0x1F0000], dtype="<u4")
    print("nonzero words in 0x10000..0x1F0000:",
          int((body != 0).sum()), "/", len(body), flush=True)


if __name__ == "__main__":
    main()
