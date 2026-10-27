#!/usr/bin/env python3
"""r15_flappy_inputprobe.py — does the game SEE my X presses?

hello_pong lesson: locate the InitPAD buffer (signature 00 41 FF FF),
read the u16 button mirror at +2 while pulsing X. If the mirror flips,
input delivery works and the bug is game-side; if not, it's the core.
Also logs a full-life servo trace (bird y / gap / flap decision).
"""
import os
import shutil
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                            # noqa: E402
from hellopong_r12_lib import make_jrn, save_png, u32      # noqa: E402
from r15_flappy_play import bird_y, green_mask, gap_target, ground_ok  # noqa

EMU = "/home/z/my-project/emu/games_homebrew"
CUE = os.path.join(EMU, "flappybird.cue")
OPENBIOS_SRC = os.path.join(REPO, "third_party", "openbios", "openbios.bin")
OUT = os.path.join(REPO, "scratch", "round15_flappy", "inputprobe")
WS = "/home/z/my-project/emu/games_homebrew/ws_r15_flappy"
PADSIG = b"\x00\x41\xff\xff"


def find_pads(snap):
    hits, i = [], 0
    while True:
        i = snap.find(PADSIG, i)
        if i < 0:
            break
        hits.append(i)
        i += 1
    return hits


def main():
    os.makedirs(OUT, exist_ok=True)
    jrn = make_jrn(OUT, "[fprobe]")
    os.makedirs(os.path.join(WS, "system"), exist_ok=True)
    shutil.copyfile(OPENBIOS_SRC, os.path.join(WS, "system", "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=WS)
    p = PS1Play(CUE, workspace=WS, var_overrides=fw["override_vars"])
    jrn({"ev": "boot", "core": p.boot()})

    for _ in range(700):
        p.core.run(1, set())
    save_png(OUT, p.core.frame_rgb(), "getready.png")

    s = bytes(p.mem.snapshot())
    pads0 = find_pads(s)
    jrn({"ev": "pads_at_getready", "n": len(pads0),
         "addrs": [hex(a) for a in pads0[:10]]})

    # start
    p.core.run(3, {"X"})
    p.core.run(4, set())
    p.core.run(2, {"X"})
    p.core.run(4, set())

    # hold X for 6 frames -> watch mirror; release 10; hold again
    def mirrors():
        s = bytes(p.mem.snapshot())
        # signature bytes: [status=00][ID=41][btn_lo][btn_hi] -> buttons @+2
        return {hex(a): int.from_bytes(s[a + 2:a + 4], "little")
                for a in pads0[:6]}

    seq = []
    for phase, btns, n in [("hold1", {"X"}, 6), ("rel1", set(), 10),
                           ("hold2", {"X"}, 6), ("rel2", set(), 10),
                           ("idle", set(), 10)]:
        for k in range(n):
            p.core.run(1, btns)
            seq.append({"ph": phase, "k": k, "m": mirrors()})
    jrn({"ev": "mirror_seq", "seq": seq})

    # full servo life trace
    trace = []
    buttons = set()
    press = cool = 0
    by_prev = None
    last_gap = None
    last_age = 999
    for idx in range(1200):
        p.core.run(1, buttons)
        fr = p.core.frame_rgb()
        by, npx = bird_y(fr)
        gt = gap_target(green_mask(fr), by)
        if gt is not None:
            last_gap, last_age = gt, 0
        else:
            last_age += 1
        eff = gt if gt is not None else (last_gap if last_age <= 40 else None)
        vy = None if by is None or by_prev is None else by - by_prev
        by_prev = by
        if press > 0:
            press -= 1
            if press == 0:
                cool = 3
            buttons = {"X"}
        elif cool > 0:
            cool -= 1
            buttons = set()
        elif by is not None:
            ty = eff[0] if eff is not None else 115.0
            if (by > ty + 2 and (vy is None or vy >= -0.5)) or by > ty + 12 or by > 150:
                buttons = {"X"}
                press = 1
            else:
                buttons = set()
        else:
            buttons = set()
        m = mirrors().get(hex(pads0[0])) if pads0 else None
        trace.append({"i": idx, "by": None if by is None else round(by),
                      "gap": None if gt is None else round(gt[0]),
                      "gapx": None if gt is None else round(gt[1]),
                      "vy": None if vy is None else round(vy, 2),
                      "x": "X" if buttons else "",
                      "pad": hex(m) if m is not None else None})
    save_png(OUT, p.core.frame_rgb(), "final.png")
    jrn({"ev": "trace", "trace": trace})
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
