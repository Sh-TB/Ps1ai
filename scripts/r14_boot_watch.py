#!/usr/bin/env python3
"""r14_boot_watch.py — fine-grained watch of the cs50x container boot.

ONE boot. Poll every ~8 frames for 1600 frames; persist a full timeline:
  * every "PS-X EXE" signature address in RAM
  * body-at-t_addr match (exe[0x800:0x820] at snapshot 0x10000)
  * BSS-clear signature (the crt0 writes zeros 0x80023000..0x80029894)
  * nonzero word counts in 3 RAM windows
  * screen mean + PNG at key transitions
  * exception-vector bytes (0x80) for crash forensics
Verdict data -> scratch/round14_breakout/watch.json
"""
import json
import os
import shutil
import sys
import time

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                          # noqa: E402
from PIL import Image                                       # noqa: E402
from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                             # noqa: E402

EMU = "/home/z/my-project/emu/games_homebrew"
CUE = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(EMU, "patched", "breakout_lic.cue")
TAG = sys.argv[2] if len(sys.argv) > 2 else "container"
WS = os.path.join(EMU, f"ws_r14_watch_{TAG}")
OUT = os.path.join(REPO, "scratch", "round14_breakout")
EXE = open(os.path.join(EMU, "cs50x.exe"), "rb").read()
BODY0 = EXE[0x800:0x800 + 32]
HDR = EXE[:0x800]
T_ADDR = 0x80010000
BSS_START, BSS_END = 0x80023000, 0x80029894


def nz(snap, lo, hi):
    w = np.frombuffer(snap[lo:hi], dtype="<u4")
    return int((w != 0).sum())


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(WS, "system"), exist_ok=True)
    shutil.copyfile(os.path.join(REPO, "third_party", "openbios",
                                 "openbios.bin"),
                    os.path.join(WS, "system", "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=WS)
    p = PS1Play(CUE, workspace=WS, var_overrides=fw["override_vars"])
    boot = p.boot()
    tl = []
    prev_key = None
    for step in range(200):
        p.wait(8)
        snap = bytes(p.mem.snapshot())
        fr = p.core.frame_rgb()
        mean = None if fr is None else round(float(fr.mean()), 2)
        hits = []
        i = snap.find(b"PS-X EXE")
        while i >= 0 and len(hits) < 6:
            hits.append(i)
            i = snap.find(b"PS-X EXE", i + 1)
        body_match = snap[0x10000:0x10020] == BODY0
        bss_zero = not any(snap[BSS_START - 0x80000000:
                                BSS_END - 0x80000000])
        key = (tuple(hits), body_match, mean is not None and mean > 0.5)
        rec = {"f": p.core.frames_run, "mean": mean,
               "hdr_hits": [hex(h) for h in hits],
               "body_at_taddr": bool(body_match),
               "nz_kernel": nz(snap, 0, 0x10000),
               "nz_text": nz(snap, 0x10000, 0x30000),
               "nz_user": nz(snap, 0x30000, 0x1F0000),
               "exc_vec": snap[0x80:0x90].hex()}
        tl.append(rec)
        if key != prev_key or step % 10 == 0:
            print(json.dumps(rec), flush=True)
            if fr is not None and len(tl) % 3 == 0:
                Image.fromarray(fr).save(
                    os.path.join(OUT, f"watch_{TAG}_f{rec['f']:05d}.png"))
        prev_key = key
    with open(os.path.join(OUT, f"watch_{TAG}.json"), "w") as f:
        json.dump({"cue": CUE, "boot": str(boot), "timeline": tl}, f,
                  indent=1)
    print("WROTE", os.path.join(OUT, f"watch_{TAG}.json"))


if __name__ == "__main__":
    main()
