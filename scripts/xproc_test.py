#!/usr/bin/env python3
"""xproc_test.py — do savestates survive across processes?
Phase 1: boot, walk 600f, save 'xproc1', exit.
Phase 2: boot fresh, load 'xproc1', verify control (responsive).
"""
import os
import sys

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mission import responsive, ensure_mission               # noqa: E402
from issue4_controller import boot                           # noqa: E402


def phase(which):
    p, fw = boot()
    print(f"[{which}] booted", flush=True)
    if which == "save":
        p.core.run(600, {"RIGHT"})
        ok, gate = responsive(p)
        p.save_state("xproc1")
        print("[save] saved after 600f walk; responsive:", ok, flush=True)
    else:
        r = p.load_state("xproc1")
        print("[load] load_state ->", r, flush=True)
        ok, gate = responsive(p)
        print("[load] responsive after cross-process load:", ok,
              gate, flush=True)
    del p


if __name__ == "__main__":
    phase(sys.argv[1])
