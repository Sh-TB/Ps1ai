#!/usr/bin/env python3
"""r13_diag_watch.py — catch the exe-load moment (or its absence).

ONE boot; poll RAM every 40 frames for the PS-EXE header signature and
report the first appearance + what happens after (transient load +
reset vs never-loaded)."""
import os
import shutil
import sys

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                               # noqa: E402
from ps1play.api import PS1Play                             # noqa: E402

EMU = "/home/z/my-project/emu/games_homebrew"
CUE = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(EMU, "patched", "breakout_lic.cue")
WS = os.path.join(EMU, "ws_diag_watch")
OUT = os.path.join(REPO, "scratch", "round13_newgames", "diag_watch")

EXE = open(os.path.join(EMU, "cs50x.exe"), "rb").read()
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
    print("boot ok:", boot.get("core", "")[:30], flush=True)
    seen = 0
    for k in range(30):
        p.wait(40)
        snap = bytes(p.mem.snapshot())
        i = snap.find(b"PS-X EXE")
        fr = p.core.frame_rgb()
        mean = None if fr is None else round(float(fr.mean()), 2)
        if i >= 0:
            seen += 1
            if seen <= 3:
                hh = snap[i:i + 0x40]
                ta = int.from_bytes(hh[0x18:0x1C], "little")
                ts = int.from_bytes(hh[0x1C:0x20], "little")
                lo = ta - 0x80000000 if 0x80000000 <= ta < 0x80200000 \
                    else None
                got = snap[lo:lo + 32] if lo is not None else None
                print(f"[{k}] f={p.core.frames_run} sig@{hex(i)} "
                      f"taddr={hex(ta)} tsize={ts} mean={mean} "
                      f"data_match={None if got is None else got == DATA0}",
                      flush=True)
        else:
            if seen and k % 5 == 0:
                print(f"[{k}] f={p.core.frames_run} sig GONE "
                      f"mean={mean}", flush=True)
        if k % 5 == 0 and i < 0:
            print(f"[{k}] f={p.core.frames_run} mean={mean} "
                  f"no-sig", flush=True)
    print("seen_total:", seen, flush=True)


if __name__ == "__main__":
    main()
