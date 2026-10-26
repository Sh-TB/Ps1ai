#!/usr/bin/env python3
"""r14_forensic2.py — fine timeline + beetle boot log. ONE boot of the
given cue; poll every 4 frames logging:
  mean, PS-X EXE magic offsets, 'LOADER'/'GAMEPS1' string offsets,
  stage1 area nonzero, payload reach. Then dump beetle log_history."""
import os
import shutil
import sys

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                             # noqa: E402

EMU = "/home/z/my-project/emu/games_homebrew"
CUE = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(EMU, "patched", "breakout_r14b.cue")
WS = os.path.join(EMU, "ws_r14_forensic2")


def reach(snap):
    r = 0
    for blk in range(0, 0x13000, 0x800):
        if any(snap[0x10000 + blk:0x10000 + blk + 0x800]):
            r = blk + 0x800
    return r


def find_all(snap, needle, cap=6):
    out, i = [], snap.find(needle)
    while i >= 0 and len(out) < cap:
        out.append(hex(i))
        i = snap.find(needle, i + 1)
    return out


def main():
    os.makedirs(os.path.join(WS, "system"), exist_ok=True)
    shutil.copyfile(os.path.join(REPO, "third_party", "openbios",
                                 "openbios.bin"),
                    os.path.join(WS, "system", "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=WS)
    p = PS1Play(CUE, workspace=WS, var_overrides=fw["override_vars"])
    boot = p.boot()
    print("BOOT INFO:", boot, flush=True)
    prev = None
    for step in range(160):
        p.wait(4)
        snap = bytes(p.mem.snapshot())
        fr = p.core.frame_rgb()
        mean = None if fr is None else round(float(fr.mean()), 1)
        key = (mean is not None and mean > 0.5,
               snap[0x180000:0x180008] != b"\x00" * 8,
               reach(snap) > 0)
        if key != prev or step % 8 == 0:
            print({"f": p.core.frames_run, "mean": mean,
                   "psxexe": find_all(snap, b"PS-X EXE"),
                   "loader": find_all(snap, b"LOADER", 3),
                   "gameps1": find_all(snap, b"GAMEPS1", 3),
                   "cs50x": find_all(snap, b"CS50X", 3),
                   "stage1": key[1], "reach": hex(reach(snap))},
                  flush=True)
        prev = key
    print("---beetle log_history (first 25)---")
    for line in (getattr(p.core, "log_history", None) or [])[:25]:
        print("  ", line)


if __name__ == "__main__":
    main()
