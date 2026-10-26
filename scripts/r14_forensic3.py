#!/usr/bin/env python3
"""r14_forensic3.py — dump the shell's m_buffer region (around the
GAMEPS1 hit) from emulator RAM and byte-compare with the on-disc root
sector of test123.bin / hello_pong_lic.bin."""
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
CUE = sys.argv[1]
RAW, DATA_OFF, SEC = 2352, 24, 2048


def main():
    WS = os.path.join(EMU, "ws_r14_forensic3")
    os.makedirs(os.path.join(WS, "system"), exist_ok=True)
    shutil.copyfile(os.path.join(REPO, "third_party", "openbios",
                                 "openbios.bin"),
                    os.path.join(WS, "system", "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=WS)
    p = PS1Play(CUE, workspace=WS, var_overrides=fw["override_vars"])
    p.boot()
    p.wait(500)
    snap = bytes(p.mem.snapshot())
    # find GAMEPS1/GAMEPS2 in RAM
    for needle in (b"GAMEPS1", b"GAMEPS2"):
        i = snap.find(needle)
        while i >= 0:
            print(f"{needle} @ {hex(i)}: "
                  f"{snap[i-40:i+40].split(chr(0).encode())[0][:80]}")
            i = snap.find(needle, i + 1)
    # dump the 2KB around the first GAMEPS1 hit in the shell zone
    i = snap.find(b"GAMEPS1")
    if i > 0:
        base = (i // SEC) * SEC
        buf = snap[base:base + SEC]
        print(f"\\nbuffer sector base={hex(base)}")
        # compare with on-disc root sectors
        for tag, path in (("test123", "test123.bin"),
                          ("hello_pong", "hello_pong_lic.bin")):
            d = open(os.path.join(EMU, "patched", path), "rb").read()
            root = d[22 * RAW + DATA_OFF:22 * RAW + DATA_OFF + SEC]
            same = sum(1 for a, b in zip(buf, root) if a == b)
            print(f"match vs {tag} root sector: {same}/{SEC} bytes")
        print("buffer[96:180]:", buf[96:180].hex())
        print("test123 root[96:180]:",
              open(os.path.join(EMU, "patched", "test123.bin"), "rb")
              .read()[22 * RAW + DATA_OFF + 96:22 * RAW + DATA_OFF + 180].hex())


if __name__ == "__main__":
    main()
