#!/usr/bin/env python3
"""r14_forensic.py — ONE boot of breakout_r14b; after the black screen
settles, deep-scan kernel RAM for the boot story:
  * s_binaryPath string ("cdrom:\\LOADER.EXE;1" = CNF parsed OK;
    "cdrom:PSX.EXE;1" = CNF open failed)
  * "PS-X EXE" header magic locations (readHeader ran?)
  * stage-1 bytes at 0x80180000, payload reach at 0x80010000
  * exception vector bytes
"""
import os
import shutil
import sys

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
    os.path.join(EMU, "patched", "breakout_r14b.cue")
WS = os.path.join(EMU, "ws_r14_forensic")


def main():
    os.makedirs(os.path.join(WS, "system"), exist_ok=True)
    shutil.copyfile(os.path.join(REPO, "third_party", "openbios",
                                 "openbios.bin"),
                    os.path.join(WS, "system", "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=WS)
    p = PS1Play(CUE, workspace=WS, var_overrides=fw["override_vars"])
    p.boot()
    p.wait(1400)
    snap = bytes(p.mem.snapshot())
    fr = p.core.frame_rgb()
    print("frame_mean:", None if fr is None else round(float(fr.mean()), 2))

    for needle, label in ((b"PS-X EXE", "psxexe_magic"),
                           (b"BOOT=", "cnf_boot"),
                           (b"LOADER", "loader_str"),
                           (b"cdrom:", "cdrom_str"),
                           (b"CS50X", "cs50x_str"),
                           (b"SYSTEM.CNF", "systemcnf_str")):
        hits, i = [], snap.find(needle)
        while i >= 0 and len(hits) < 12:
            ctx = snap[max(0, i - 8):i + 64]
            hits.append((hex(i), ctx.split(b"\x00")[0][:60]))
            i = snap.find(needle, i + 1)
        print(f"{label}: {hits}")

    print("stage1@0x80180000:", snap[0x180000:0x180010].hex())
    print("payload first 32B @0x80010000:",
          snap[0x10000:0x10020].hex())
    r = 0
    for blk in range(0, 0x13000, 0x800):
        if any(snap[0x10000 + blk:0x10000 + blk + 0x800]):
            r = blk + 0x800
    print("payload_reach:", hex(r))
    print("exc_vec@0x80:", snap[0x80:0xA0].hex())
    # kernel low RAM strings dump (readable runs >= 8)
    runs, cur = [], bytearray()
    for off, b in enumerate(snap[:0x10000]):
        if 32 <= b < 127:
            cur.append(b)
        else:
            if len(cur) >= 10:
                runs.append((hex(off - len(cur)), cur.decode()))
            cur = bytearray()
    print("kernel strings (last 40):")
    for a, s in runs[-40:]:
        print("  ", a, s[:80])
    if fr is not None:
        Image.fromarray(fr).save(os.path.join(
            REPO, "scratch", "round14_breakout", "forensic_f1400.png"))


if __name__ == "__main__":
    main()
